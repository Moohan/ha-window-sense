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
    """Internal configuration parameters governing trusted baseline learning.
    
    These parameters control the multi-tier confidence bands, perturbation tolerances,
    and safeguards without exposing unnecessary tuning knobs to standard users.
    """
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
    """Evaluates whether the room environment is trusted for baseline adaptation.
    
    Applies multi-tier confidence bands:
    - 'invalid': Sensor dropouts, stale data, NaN, or physical range violations -> FROZEN (0% rate)
    - 'suspect': Open window, recovery quarantine, active/recent change point,
                 or high confidence ventilation -> FROZEN (0% rate)
    - 'uncertain': Mild thermal perturbation, intermediate confidence, or cooldown -> SLOWED (15-45% rate)
    - 'trusted': Stable equilibrium with low residual and gentle drift -> ACTIVE (100% rate)
    """

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

        # ---------------------------------------------------------------------
        # 1. Sensor Data Validity, Freshness & Dropout Protection
        # ---------------------------------------------------------------------
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
                # Sensor dropout or long outage: environment state during outage is unknown
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
                reason=f"Sensor data invalid, stale, or dropped out ({', '.join(freeze_reasons)}). Baseline learning frozen.",
                freeze_reasons=freeze_reasons,
            )

        # ---------------------------------------------------------------------
        # 2. Confirmed Open Window or Recovery Quarantine
        # ---------------------------------------------------------------------
        if is_open:
            return BaselineTrustState(
                status=BASELINE_TRUST_FROZEN,
                is_trusted=False,
                learning_allowed=False,
                trust_factor=0.0,
                effective_learning_rate=0.0,
                confidence_band=BAND_SUSPECT,
                reason="Window confirmed open. Baseline learning frozen to prevent ventilation contamination.",
                freeze_reasons=["window_open"],
            )

        if in_recovery_quarantine:
            return BaselineTrustState(
                status=BASELINE_TRUST_FROZEN,
                is_trusted=False,
                learning_allowed=False,
                trust_factor=0.0,
                effective_learning_rate=0.0,
                confidence_band=BAND_SUSPECT,
                reason="Post-event thermal recovery quarantine in progress. Baseline learning frozen.",
                freeze_reasons=["recovery_quarantine"],
            )

        # ---------------------------------------------------------------------
        # 3. Change-Point Events & Trajectory Inflection Protection
        # ---------------------------------------------------------------------
        time_since_cp: Optional[float] = None
        if last_change_point_time is not None:
            time_since_cp = reading.timestamp - last_change_point_time

        is_recent_cp = time_since_cp is not None and time_since_cp <= policy.change_point_cooldown_sec

        if change_point_active or is_recent_cp:
            has_anomaly = (
                evidence.final_confidence >= policy.suspect_confidence_threshold
                or open_persistence_counter > 0
                or abs(features.thermal_residual) >= policy.suspect_residual_c
                or abs(features.temp_rate) >= policy.suspect_rate_c_per_h
            )
            if has_anomaly:
                return BaselineTrustState(
                    status=BASELINE_TRUST_FROZEN,
                    is_trusted=False,
                    learning_allowed=False,
                    trust_factor=0.0,
                    effective_learning_rate=0.0,
                    confidence_band=BAND_SUSPECT,
                    reason=f"Change-point inflection accompanied by anomaly ({int(time_since_cp or 0)}s ago). Baseline learning frozen.",
                    freeze_reasons=["change_point_inflection"],
                )
            elif (change_point_active or (time_since_cp is not None and time_since_cp <= 300.0)) and (abs(features.thermal_residual) > 0.25 or abs(features.temp_rate) > 0.4):
                trust_factor = policy.min_slowed_trust_factor
                return BaselineTrustState(
                    status=BASELINE_TRUST_SLOWED,
                    is_trusted=False,
                    learning_allowed=True,
                    trust_factor=trust_factor,
                    effective_learning_rate=base_learning_rate * trust_factor,
                    confidence_band=BAND_UNCERTAIN,
                    reason=f"Recent change-point inflection ({int(time_since_cp or 0)}s ago). Adaptation slowed to observe trajectory.",
                    freeze_reasons=[],
                )

        # ---------------------------------------------------------------------
        # 4. Strongly Suspected Window-Open / Ventilation (Suspect Band)
        # ---------------------------------------------------------------------
        is_suspect = False
        suspect_details: List[str] = []

        if evidence.final_confidence >= policy.suspect_confidence_threshold:
            is_suspect = True
            suspect_details.append(f"high confidence {int(evidence.final_confidence * 100)}%")

        if open_persistence_counter > 0:
            is_suspect = True
            suspect_details.append(f"open persistence {open_persistence_counter}m")

        # Rapid thermal departure towards outdoor air
        is_outdoor_colder = features.temp_diff > 1.5
        is_outdoor_warmer = features.temp_diff < -1.5

        if is_outdoor_colder and features.temp_rate <= -policy.suspect_rate_c_per_h:
            is_suspect = True
            suspect_details.append(f"rapid cooling {features.temp_rate:.1f}°C/h towards cold outdoor")
        elif is_outdoor_warmer and features.temp_rate >= policy.suspect_rate_c_per_h:
            is_suspect = True
            suspect_details.append(f"rapid warming +{features.temp_rate:.1f}°C/h from hot outdoor")

        # Large thermal anomaly
        if abs(features.thermal_residual) >= policy.suspect_residual_c:
            is_suspect = True
            suspect_details.append(f"large thermal residual {features.thermal_residual:+.2f}°C")

        if is_suspect:
            return BaselineTrustState(
                status=BASELINE_TRUST_FROZEN,
                is_trusted=False,
                learning_allowed=False,
                trust_factor=0.0,
                effective_learning_rate=0.0,
                confidence_band=BAND_SUSPECT,
                reason=f"Suspected ventilation / anomaly ({', '.join(suspect_details)}). Baseline learning frozen.",
                freeze_reasons=suspect_details,
            )

        # ---------------------------------------------------------------------
        # 5. Suspected but Uncertain Event (Uncertain Band -> SLOWED)
        # ---------------------------------------------------------------------
        is_uncertain = False
        uncertain_details: List[str] = []

        # Secondary change-point cooldown phase (5 - 10 min)
        if is_recent_cp and time_since_cp is not None and time_since_cp > 300.0:
            is_uncertain = True
            uncertain_details.append(f"post change-point dwell ({int(time_since_cp / 60)}m)")

        if evidence.final_confidence >= policy.uncertain_confidence_threshold:
            is_uncertain = True
            uncertain_details.append(f"moderate confidence {int(evidence.final_confidence * 100)}%")

        if abs(features.thermal_residual) > policy.max_stable_residual_c:
            is_uncertain = True
            uncertain_details.append(f"residual {features.thermal_residual:+.2f}°C")

        if abs(features.temp_rate) > policy.max_stable_rate_c_per_h:
            is_uncertain = True
            uncertain_details.append(f"temperature rate {features.temp_rate:+.1f}°C/h")

        if is_uncertain:
            # Continuous confidence band scaling:
            # As perturbation severity increases within the uncertain band,
            # smoothly scale trust_factor down from max_slowed (0.45) to min_slowed (0.15)
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
                reason=f"Uncertain thermal perturbation ({', '.join(uncertain_details)}). Learning slowed to {int(trust_factor * 100)}%.",
                freeze_reasons=[],
            )

        # ---------------------------------------------------------------------
        # 6. Normal Stable Room Behaviour (Trusted Band -> ACTIVE)
        # ---------------------------------------------------------------------
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
    """Estimates expected room equilibrium and building thermal conductance.
    
    Implements trusted baseline learning with:
    - Multi-tier confidence band trust evaluation (Active, Slowed, Frozen)
    - Anti-contamination snapshot rollback buffer
    - Post-event recovery quarantine
    - Physical building thermal mass slew-rate limiting
    - Envelope conductance learning protected from ventilation distortion
    - Smooth, uninhibited learning of legitimate long-term seasonal drift
    """

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

        # Learned thermal behaviour variables
        self.learned_conductance: float = 0.08  # Heat loss coefficient U (h^-1)
        self.is_frozen: bool = False
        self.initialized: bool = True

        # Explicit trusted baseline learning state
        self.trust_state: BaselineTrustState = BaselineTrustState(
            status=BASELINE_TRUST_ACTIVE,
            is_trusted=True,
            learning_allowed=True,
            trust_factor=1.0,
            effective_learning_rate=learning_rate,
            confidence_band=BAND_TRUSTED,
            reason="Initialized baseline model in stable state.",
        )

        # Anti-contamination snapshot rollback buffer (stores verified clean equilibrium baseline values)
        self.clean_snapshots: List[float] = [initial_temp]
        self.snapshot_history_size: int = snapshot_history_size

        # Pre-event anchor to restore when window opening is confirmed
        self.pre_event_baseline: float = initial_temp

        # Post-event recovery quarantine state
        self.in_recovery_quarantine: bool = False
        self.recovery_sample_count: int = 0

    def record_clean_snapshot(self) -> None:
        """Records the current expected baseline as a verified clean equilibrium point.
        
        CRITICAL: Snapshots are ONLY recorded when the environment is in the ACTIVE (trusted) state.
        Never when slowed or frozen.
        """
        if self.trust_state.status == BASELINE_TRUST_ACTIVE and not self.in_recovery_quarantine:
            self.clean_snapshots.append(self.expected_temp)
            if len(self.clean_snapshots) > self.snapshot_history_size:
                self.clean_snapshots.pop(0)

    def on_window_open_onset(self) -> None:
        """Rolls back baseline to clean snapshot before onset ramp began and freezes adaptation."""
        if self.clean_snapshots:
            # Take a snapshot from prior to the onset ramp (5-10 minutes back)
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
        # Ensure expected baseline remains locked at pre-event clean equilibrium
        self.expected_temp = self.pre_event_baseline

    def update_recovery_quarantine(self, indoor_temp: float, temp_rate: float) -> bool:
        """Evaluates whether post-window recovery quarantine can be safely disengaged.
        
        Returns True if still in quarantine (adaptation blocked), False if recovered.
        """
        if not self.in_recovery_quarantine:
            return False

        self.recovery_sample_count += 1

        # Condition A: Indoor temperature has recovered to near pre-event baseline (within 0.5°C)
        has_thermally_recovered = indoor_temp >= (self.pre_event_baseline - 0.5)

        # Condition B: Extended recovery dwell (at least 35 min) and temperature is stable/warming
        extended_dwell_reached = self.recovery_sample_count >= 35 and temp_rate > -0.2

        if has_thermally_recovered or extended_dwell_reached:
            self.in_recovery_quarantine = False
            self.is_frozen = False
            self.recovery_sample_count = 0
            # Refresh clean snapshot buffer with recovered baseline
            self.clean_snapshots = [self.expected_temp] * 5
            return False

        # Still recovering: keep baseline frozen at pre-event level
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
        dt_sec: float = 60.0,
    ) -> float:
        """Updates baseline model and learned thermal behaviour variables.
        
        Modulated by the evaluated trust_state:
        - When ACTIVE: Full learning rate, snapshots recorded, conductance learned.
        - When SLOWED: Reduced learning rate (15-45%), no snapshots, conductance protected.
        - When FROZEN: 0% learning rate, baseline completely locked against contamination.
        """
        if trust_state is not None:
            self.trust_state = trust_state
            self.is_frozen = (trust_state.status == BASELINE_TRUST_FROZEN)

        if not self.initialized:
            self.expected_temp = indoor_temp
            self.pre_event_baseline = indoor_temp
            self.clean_snapshots = [indoor_temp] * 5
            self.initialized = True
            return self.expected_temp

        # Strict freeze if frozen or in recovery quarantine
        if self.is_frozen or self.in_recovery_quarantine or not self.trust_state.learning_allowed:
            return self.expected_temp

        dt_min = max(0.1, min(15.0, dt_sec / 60.0))

        # Calculate effective adaptation rate using trust factor and interval dt
        effective_lr = self.trust_state.effective_learning_rate
        if hvac_state in ("heating", "cooling"):
            effective_lr *= 1.5

        clamped_effective_lr = min(0.99, max(0.0, effective_lr))
        step_lr = 1.0 - ((1.0 - clamped_effective_lr) ** dt_min)
        target = indoor_temp
        raw_delta = (target - self.expected_temp) * step_lr

        # Physical slew-rate limit: building thermal mass prevents fast baseline collapses
        max_slew = self.max_slew_per_minute * dt_min
        clamped_delta = max(-max_slew, min(max_slew, raw_delta))
        self.expected_temp += clamped_delta

        # Update learned building conductance (U-value) ONLY during active, trusted free-floating periods
        gradient = outdoor_temp - indoor_temp
        if (
            self.trust_state.status == BASELINE_TRUST_ACTIVE
            and abs(gradient) > 2.0
            and hvac_state == "idle"
        ):
            # temp_rate = Conductance * (T_out - T_in)
            measured_conductance = temp_rate / gradient
            if 0.01 <= measured_conductance <= 0.40:
                cond_lr = 0.01 * self.trust_state.trust_factor
                self.learned_conductance = (1.0 - cond_lr) * self.learned_conductance + (cond_lr * measured_conductance)

        # Record clean snapshot if in active state
        if self.trust_state.status == BASELINE_TRUST_ACTIVE:
            self.record_clean_snapshot()

        return self.expected_temp
