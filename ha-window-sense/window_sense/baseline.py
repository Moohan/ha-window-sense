"""Baseline modeling and trusted learning protection against contamination.

This module implements the "trusted baseline learning" strategy for Window Sense.
It ensures that adaptive equilibrium temperature and building thermal conductance
are only updated when the environment is verified to be trustworthy and stable,
preventing an open window or ventilation event from contaminating the baseline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from .const import (
    DEFAULT_BASELINE_LEARNING_RATE,
    DEFAULT_MAX_BASELINE_SLEW_PER_MIN,
    BASELINE_TRUST_ACTIVE,
    BASELINE_TRUST_SLOWED,
    BASELINE_TRUST_FROZEN,
    BAND_TRUSTED,
    BAND_UNCERTAIN,
    BAND_SUSPECT,
    BAND_INVALID,
    DEFAULT_SUSPECT_CONFIDENCE_THRESHOLD,
    DEFAULT_UNCERTAIN_CONFIDENCE_THRESHOLD,
    DEFAULT_MAX_STABLE_RATE,
    DEFAULT_MAX_STABLE_RESIDUAL,
    DEFAULT_CHANGE_POINT_COOLDOWN_SEC,
    DEFAULT_MAX_SAMPLE_INTERVAL_SEC,
)
from .features import SensorReading, ExtractedFeatures
from .evidence import EvidenceScore


@dataclass
class BaselineTrustPolicy:
    """Internal configuration parameters governing trusted baseline learning."""
    max_reading_interval_sec: float = DEFAULT_MAX_SAMPLE_INTERVAL_SEC  # 15 min max gap before stale
    min_samples_for_active: int = 3                                   # Initial warmup requirement
    change_point_cooldown_sec: float = DEFAULT_CHANGE_POINT_COOLDOWN_SEC  # 10 min freeze/slow after CP
    suspect_confidence_threshold: float = DEFAULT_SUSPECT_CONFIDENCE_THRESHOLD  # Conf >= 0.60 -> Frozen
    uncertain_confidence_threshold: float = DEFAULT_UNCERTAIN_CONFIDENCE_THRESHOLD  # Conf >= 0.20 -> Slowed
    max_stable_rate_c_per_h: float = DEFAULT_MAX_STABLE_RATE         # 0.60 °C/h max stable drift
    max_stable_residual_c: float = DEFAULT_MAX_STABLE_RESIDUAL       # 0.40 °C max stable anomaly
    suspect_rate_c_per_h: float = 1.0                                # >= 1.0 °C/h towards outdoor -> Suspect
    suspect_residual_c: float = 1.2                                  # >= 1.2 °C departure -> Suspect
    min_slowed_trust_factor: float = 0.15                            # Multiplier floor during slowed band
    max_slowed_trust_factor: float = 0.45                            # Multiplier ceiling during slowed band
    temp_valid_min_c: float = -30.0                                  # Reasonable lower bound
    temp_valid_max_c: float = 60.0                                   # Reasonable upper bound


@dataclass
class BaselineTrustState:
    """Explicit state of baseline learning trust and contamination protection."""
    status: str                         # "active" | "slowed" | "frozen"
    is_trusted: bool                    # True when status == "active"
    learning_allowed: bool              # True when status in ("active", "slowed")
    trust_factor: float                 # 0.0 to 1.0 multiplier on base learning rate
    effective_learning_rate: float      # base_learning_rate * trust_factor
    confidence_band: str                # "trusted" | "uncertain" | "suspect" | "invalid"
    reason: str                         # Human-readable diagnostic description
    freeze_reasons: List[str] = field(default_factory=list)


class BaselineTrustEvaluator:
    """Evaluates whether the room environment is trusted for baseline adaptation."""

    @staticmethod
    def evaluate(
        reading: SensorReading,
        features: ExtractedFeatures,
        evidence: EvidenceScore,
        is_open: bool,
        in_recovery_quarantine: bool,
        change_point_active: bool,
        last_change_point_time: Optional[float],
        last_reading_time: Optional[float],
        open_persistence_counter: int,
        base_learning_rate: float,
        policy: BaselineTrustPolicy,
    ) -> BaselineTrustState:
        """Evaluates sensor readings and environment stability to determine trust state."""
        freeze_reasons: List[str] = []

        # 1. Sensor Data Validity, Freshness & Dropout Protection
        if reading.indoor_temp is None or math.isnan(reading.indoor_temp) or math.isinf(reading.indoor_temp):
            freeze_reasons.append("indoor_temp_invalid")
        elif not (policy.temp_valid_min_c <= reading.indoor_temp <= policy.temp_valid_max_c):
            freeze_reasons.append("indoor_temp_out_of_bounds")

        if reading.outdoor_temp is None or math.isnan(reading.outdoor_temp) or math.isinf(reading.outdoor_temp):
            freeze_reasons.append("outdoor_temp_invalid")
        elif not (policy.temp_valid_min_c <= reading.outdoor_temp <= policy.temp_valid_max_c):
            freeze_reasons.append("outdoor_temp_out_of_bounds")

        if last_reading_time is not None:
            dt = reading.timestamp - last_reading_time
            if dt <= 0:
                freeze_reasons.append("timestamp_disordered")
            elif dt > policy.max_reading_interval_sec:
                freeze_reasons.append("sensor_dropout_stale")

        if features.sample_count < policy.min_samples_for_active:
            freeze_reasons.append("insufficient_samples")

        if freeze_reasons:
            return BaselineTrustState(
                status=BASELINE_TRUST_FROZEN,
                is_trusted=False,
                learning_allowed=False,
                trust_factor=0.0,
                effective_learning_rate=0.0,
                confidence_band=BAND_INVALID,
                reason=f"Data quality issue ({', '.join(freeze_reasons)}). Baseline learning frozen.",
                freeze_reasons=freeze_reasons,
            )

        # 2. Open Window, Quarantine, or Onset Ramp Safeguards -> FROZEN
        if is_open:
            freeze_reasons.append("window_is_open")
        if in_recovery_quarantine:
            freeze_reasons.append("post_close_recovery_quarantine")
        if open_persistence_counter > 0:
            freeze_reasons.append("onset_ramp_in_progress")

        if freeze_reasons:
            return BaselineTrustState(
                status=BASELINE_TRUST_FROZEN,
                is_trusted=False,
                learning_allowed=False,
                trust_factor=0.0,
                effective_learning_rate=0.0,
                confidence_band=BAND_SUSPECT,
                reason=f"Active event safeguard ({', '.join(freeze_reasons)}). Baseline learning locked.",
                freeze_reasons=freeze_reasons,
            )

        # 3. High Evidence / Rapid Anomaly Safeguards -> FROZEN
        abs_rate = abs(features.temp_rate)
        abs_res = abs(features.thermal_residual)

        if evidence.final_confidence >= policy.suspect_confidence_threshold:
            freeze_reasons.append(f"high_confidence_open_evidence_{evidence.final_confidence:.2f}")
        if abs_rate >= policy.suspect_rate_c_per_h and features.temp_diff > 1.0 and features.temp_rate < 0:
            freeze_reasons.append(f"suspect_cooling_rate_{features.temp_rate:.1f}C_h")
        if abs_res >= policy.suspect_residual_c and abs_rate >= 0.4:
            freeze_reasons.append(f"suspect_residual_departure_{features.thermal_residual:+.2f}C")

        if freeze_reasons:
            return BaselineTrustState(
                status=BASELINE_TRUST_FROZEN,
                is_trusted=False,
                learning_allowed=False,
                trust_factor=0.0,
                effective_learning_rate=0.0,
                confidence_band=BAND_SUSPECT,
                reason=f"Thermal anomaly detected ({', '.join(freeze_reasons)}). Baseline learning frozen.",
                freeze_reasons=freeze_reasons,
            )

        # 4. Change-Point & Cooldown Handling -> SLOWED
        uncertain_details: List[str] = []
        if change_point_active:
            uncertain_details.append("active_change_point_inflection")

        if last_change_point_time is not None:
            dt_cp = reading.timestamp - last_change_point_time
            if 0 <= dt_cp < policy.change_point_cooldown_sec:
                uncertain_details.append(f"Recent change-point inflection ({int(dt_cp)}s ago)")

        # 5. Mild Thermal Perturbations -> SLOWED
        if evidence.final_confidence >= policy.uncertain_confidence_threshold:
            uncertain_details.append(f"intermediate_confidence_{evidence.final_confidence:.2f}")
        if abs_rate > policy.max_stable_rate_c_per_h:
            uncertain_details.append(f"elevated_rate_{features.temp_rate:+.1f}C_h")
        if abs_res > policy.max_stable_residual_c and abs_rate >= 0.4:
            uncertain_details.append(f"elevated_residual_{features.thermal_residual:+.2f}C")

        if uncertain_details:
            conf_span = policy.suspect_confidence_threshold - policy.uncertain_confidence_threshold
            conf_ratio = max(0.0, min(1.0, (evidence.final_confidence - policy.uncertain_confidence_threshold) / max(0.01, conf_span)))

            res_span = policy.suspect_residual_c - policy.max_stable_residual_c
            res_ratio = max(0.0, min(1.0, (abs(features.thermal_residual) - policy.max_stable_residual_c) / max(0.01, res_span)))

            perturbation = max(conf_ratio, res_ratio)
            trust_factor = policy.max_slowed_trust_factor - (perturbation * (policy.max_slowed_trust_factor - policy.min_slowed_trust_factor))
            trust_factor = max(policy.min_slowed_trust_factor, min(policy.max_slowed_trust_factor, trust_factor))
            trust_factor = round(trust_factor, 3)

            eff_lr = base_learning_rate * trust_factor

            return BaselineTrustState(
                status=BASELINE_TRUST_SLOWED,
                is_trusted=False,
                learning_allowed=True,
                trust_factor=trust_factor,
                effective_learning_rate=eff_lr,
                confidence_band=BAND_UNCERTAIN,
                reason=f"Uncertain thermal perturbation ({', '.join(uncertain_details)}). Adaptation slowed to {int(trust_factor * 100)}%.",
                freeze_reasons=[],
            )

        # 6. Normal Stable Room Behaviour -> ACTIVE
        eff_lr = base_learning_rate * 1.0
        return BaselineTrustState(
            status=BASELINE_TRUST_ACTIVE,
            is_trusted=True,
            learning_allowed=True,
            trust_factor=1.0,
            effective_learning_rate=eff_lr,
            confidence_band=BAND_TRUSTED,
            reason=f"Environment stable and trustworthy (residual {features.thermal_residual:+.2f}°C, rate {features.temp_rate:+.1f}°C/h). Normal baseline learning active.",
            freeze_reasons=[],
        )


class AdaptiveBaselineModel:
    """Estimates expected room equilibrium and building thermal conductance."""

    def __init__(
        self,
        initial_temp: float = 21.0,
        learning_rate: float = DEFAULT_BASELINE_LEARNING_RATE,
        max_slew_per_minute: float = DEFAULT_MAX_BASELINE_SLEW_PER_MIN,
        snapshot_history_size: int = 30,
        policy: Optional[BaselineTrustPolicy] = None,
    ):
        self.expected_temp: float = initial_temp
        self.learning_rate: float = learning_rate
        self.max_slew_per_minute: float = max_slew_per_minute
        self.policy: BaselineTrustPolicy = policy or BaselineTrustPolicy()

        self.learned_conductance: float = 0.08
        self.is_frozen: bool = False
        self.initialized: bool = True

        self.trust_state: BaselineTrustState = BaselineTrustState(
            status=BASELINE_TRUST_ACTIVE,
            is_trusted=True,
            learning_allowed=True,
            trust_factor=1.0,
            effective_learning_rate=learning_rate,
            confidence_band=BAND_TRUSTED,
            reason="Initialized baseline model in stable state.",
        )

        self.clean_snapshots: List[float] = [initial_temp]
        self.snapshot_history_size: int = snapshot_history_size
        self.pre_event_baseline: float = initial_temp
        self.in_recovery_quarantine: bool = False
        self.recovery_sample_count: int = 0

    def record_clean_snapshot(self) -> None:
        """Records current baseline as clean snapshot when active."""
        if self.trust_state.status == BASELINE_TRUST_ACTIVE and not self.in_recovery_quarantine:
            self.clean_snapshots.append(self.expected_temp)
            if len(self.clean_snapshots) > self.snapshot_history_size:
                self.clean_snapshots.pop(0)

    def on_window_open_onset(self) -> None:
        """Rolls back baseline to clean snapshot before onset ramp began and freezes adaptation."""
        if self.clean_snapshots:
            idx = max(0, len(self.clean_snapshots) - 6)
            self.pre_event_baseline = self.clean_snapshots[idx]
        else:
            self.pre_event_baseline = self.expected_temp

        self.expected_temp = self.pre_event_baseline
        self.is_frozen = True
        self.in_recovery_quarantine = False

    def on_window_close(self) -> None:
        """Engages recovery quarantine when window closes to prevent learning the cold room."""
        self.is_frozen = True
        self.in_recovery_quarantine = True
        self.recovery_sample_count = 0
        self.expected_temp = self.pre_event_baseline

    def update_recovery_quarantine(self, indoor_temp: float, temp_rate: float) -> bool:
        """Evaluates whether post-window recovery quarantine can be safely disengaged."""
        if not self.in_recovery_quarantine:
            return False

        self.recovery_sample_count += 1

        has_thermally_recovered = indoor_temp >= (self.pre_event_baseline - 0.5)
        extended_dwell_reached = self.recovery_sample_count >= 35 and temp_rate > -0.2

        if has_thermally_recovered or extended_dwell_reached:
            self.in_recovery_quarantine = False
            self.is_frozen = False
            self.recovery_sample_count = 0
            self.expected_temp = indoor_temp
            self.clean_snapshots = [indoor_temp] * 5
            return False

        self.is_frozen = True
        self.expected_temp = self.pre_event_baseline
        return True

    def update(
        self,
        indoor_temp: float,
        outdoor_temp: float,
        hvac_state: str = "idle",
        trust_state: Optional[BaselineTrustState] = None,
        temp_rate: float = 0.0,
    ) -> float:
        """Updates baseline model and learned thermal behaviour variables."""
        if trust_state is not None:
            self.trust_state = trust_state
            self.is_frozen = (trust_state.status == BASELINE_TRUST_FROZEN)

        if not self.initialized:
            self.expected_temp = indoor_temp
            self.pre_event_baseline = indoor_temp
            self.clean_snapshots = [indoor_temp] * 5
            self.initialized = True
            return self.expected_temp

        if self.is_frozen or self.in_recovery_quarantine or not self.trust_state.learning_allowed:
            return self.expected_temp

        effective_lr = self.trust_state.effective_learning_rate
        if hvac_state in ("heating", "cooling"):
            effective_lr *= 1.5

        target = indoor_temp
        raw_delta = (target - self.expected_temp) * effective_lr

        clamped_delta = max(-self.max_slew_per_minute, min(self.max_slew_per_minute, raw_delta))
        self.expected_temp += clamped_delta

        gradient = outdoor_temp - indoor_temp
        if (
            self.trust_state.status == BASELINE_TRUST_ACTIVE
            and abs(gradient) > 2.0
            and hvac_state == "idle"
        ):
            measured_conductance = temp_rate / gradient
            if 0.01 <= measured_conductance <= 0.40:
                cond_lr = 0.01 * self.trust_state.trust_factor
                self.learned_conductance = (1.0 - cond_lr) * self.learned_conductance + (cond_lr * measured_conductance)

        if self.trust_state.status == BASELINE_TRUST_ACTIVE:
            self.record_clean_snapshot()

        return self.expected_temp
