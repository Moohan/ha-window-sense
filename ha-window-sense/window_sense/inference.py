"""Core inference engine, baseline learning, change-point detection, and hysteresis."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from .const import (
    DEFAULT_OPEN_THRESHOLD,
    DEFAULT_CLOSE_THRESHOLD,
    DEFAULT_OPEN_PERSISTENCE,
    DEFAULT_CLOSE_PERSISTENCE,
    DEFAULT_BASELINE_LEARNING_RATE,
    DEFAULT_CHANGE_POINT_SENSITIVITY,
    DEFAULT_MIN_GRADIENT,
    DEFAULT_MAX_BASELINE_SLEW_PER_MIN,
    QUALITY_EXCELLENT,
    QUALITY_GOOD,
    QUALITY_FAIR,
    QUALITY_DEGRADED,
)
from .features import SensorReading, ExtractedFeatures, FeatureExtractor
from .evidence import EvidenceScore, EvidenceScorer


class AdaptiveBaselineModel:
    """Estimates expected room temperature equilibrium.
    
    Uses exponential moving average with outdoor gradient compensation,
    strict physical slew-rate limiting, pre-event snapshot rollback,
    and post-event recovery quarantine to prevent baseline contamination.
    
    CRITICAL DESIGN RULE:
    The baseline must NOT learn that an open-window event is normal room behavior.
    """

    def __init__(
        self,
        initial_temp: float = 21.0,
        learning_rate: float = DEFAULT_BASELINE_LEARNING_RATE,
        max_slew_per_minute: float = DEFAULT_MAX_BASELINE_SLEW_PER_MIN,
        snapshot_history_size: int = 30,
    ):
        self.expected_temp: float = initial_temp
        self.learning_rate: float = learning_rate
        self.max_slew_per_minute: float = max_slew_per_minute
        self.is_frozen: bool = False
        self.initialized: bool = True

        # Anti-contamination snapshot rollback buffer (stores clean equilibrium baseline values)
        self.clean_snapshots: List[float] = [initial_temp]
        self.snapshot_history_size: int = snapshot_history_size

        # Pre-event anchor to restore when window opening is confirmed
        self.pre_event_baseline: float = initial_temp

        # Post-event recovery quarantine state
        self.in_recovery_quarantine: bool = False
        self.recovery_sample_count: int = 0

    def record_clean_snapshot(self) -> None:
        """Records the current expected baseline as a verified clean equilibrium point."""
        if not self.is_frozen and not self.in_recovery_quarantine:
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

    def update(self, indoor_temp: float, outdoor_temp: float, hvac_state: str = "idle") -> float:
        """Updates baseline temperature model with strict anti-contamination safeguards."""
        if not self.initialized:
            self.expected_temp = indoor_temp
            self.pre_event_baseline = indoor_temp
            self.clean_snapshots = [indoor_temp] * 5
            self.initialized = True
            return self.expected_temp

        if self.is_frozen or self.in_recovery_quarantine:
            return self.expected_temp

        # Weight adaptation based on HVAC state
        rate = self.learning_rate
        if hvac_state in ("heating", "cooling"):
            rate *= 1.5

        # Incorporate normal slow building drift towards outdoor equilibrium
        target = (indoor_temp * 0.95) + (outdoor_temp * 0.05)
        raw_delta = (target - self.expected_temp) * rate

        # Physical slew-rate limit: building thermal mass prevents fast baseline collapses
        clamped_delta = max(-self.max_slew_per_minute, min(self.max_slew_per_minute, raw_delta))
        self.expected_temp += clamped_delta

        return self.expected_temp


class PageHinkleyChangePoint:
    """Page-Hinkley cumulative sum algorithm for detecting abrupt trajectory inflections."""

    def __init__(self, threshold: float = 1.0, alpha: float = 0.05):
        self.threshold = threshold
        self.alpha = alpha
        self.sum_val = 0.0
        self.min_val = float("inf")
        self.is_triggered = False

    def reset(self) -> None:
        self.sum_val = 0.0
        self.min_val = float("inf")
        self.is_triggered = False

    def update(self, residual: float) -> bool:
        """Updates cumulative sum and checks if inflection exceeded threshold."""
        self.sum_val += abs(residual) - self.alpha
        if self.sum_val < self.min_val:
            self.min_val = self.sum_val

        if (self.sum_val - self.min_val) > self.threshold:
            self.is_triggered = True
            return True
        self.is_triggered = False
        return False


@dataclass
class WindowState:
    """Current evaluated window state and telemetry."""
    is_open: bool
    confidence: float
    detection_quality: str
    thermal_residual: float
    temperature_rate: float
    temperature_diff: float
    evidence: EvidenceScore
    features: ExtractedFeatures
    primary_reason: str
    open_persistence_counter: int
    close_persistence_counter: int
    state_changed: bool


class WindowInferenceEngine:
    """Orchestrates feature extraction, baseline modeling, evidence scoring, and hysteresis."""

    def __init__(
        self,
        open_threshold: float = DEFAULT_OPEN_THRESHOLD,
        close_threshold: float = DEFAULT_CLOSE_THRESHOLD,
        open_persistence_min: int = DEFAULT_OPEN_PERSISTENCE,
        close_persistence_min: int = DEFAULT_CLOSE_PERSISTENCE,
        baseline_learning_rate: float = DEFAULT_BASELINE_LEARNING_RATE,
        change_point_sensitivity: float = DEFAULT_CHANGE_POINT_SENSITIVITY,
        min_gradient: float = DEFAULT_MIN_GRADIENT,
    ):
        self.open_threshold = open_threshold
        self.close_threshold = close_threshold
        self.open_persistence_min = open_persistence_min
        self.close_persistence_min = close_persistence_min
        self.min_gradient = min_gradient

        self.feature_extractor = FeatureExtractor(max_history_minutes=45)
        self.baseline_model = AdaptiveBaselineModel(
            initial_temp=21.0, learning_rate=baseline_learning_rate
        )
        self.change_point = PageHinkleyChangePoint(threshold=change_point_sensitivity)

        self.is_open: bool = False
        self.open_persistence_counter: int = 0
        self.close_persistence_counter: int = 0
        self.last_state: Optional[WindowState] = None

    def process_reading(self, reading: SensorReading) -> WindowState:
        """Processes an incoming sensor reading and updates the inferred state machine."""
        self.feature_extractor.add_reading(reading)

        # Initialize baseline on very first reading if not yet initialized
        if not self.baseline_model.initialized:
            self.baseline_model.update(
                reading.indoor_temp, reading.outdoor_temp, reading.hvac_state or "idle"
            )

        # 1. Extract rolling temporal and psychrometric features using current expected baseline
        features = self.feature_extractor.extract(self.baseline_model.expected_temp)

        # 2. Update change-point detector
        cp_active = self.change_point.update(features.thermal_residual)

        # 3. Score positive and negative evidence
        evidence = EvidenceScorer.evaluate(
            features=features,
            change_point_active=cp_active,
            min_gradient=self.min_gradient,
            is_currently_open=self.is_open,
        )

        # 4. Determine detection quality based on sensor availability
        quality = self._assess_quality(reading, features)

        # 5. Evaluate asymmetric hysteresis state machine
        prev_is_open = self.is_open

        if not self.is_open:
            # Condition to enter OPEN state
            if evidence.final_confidence >= self.open_threshold:
                self.open_persistence_counter += 1
                if self.open_persistence_counter >= self.open_persistence_min:
                    self.is_open = True
                    self.open_persistence_counter = 0
            else:
                self.open_persistence_counter = max(0, self.open_persistence_counter - 1)
        else:
            # Condition to return to CLOSED state
            if evidence.final_confidence <= self.close_threshold:
                self.close_persistence_counter += 1
                if self.close_persistence_counter >= self.close_persistence_min:
                    self.is_open = False
                    self.close_persistence_counter = 0
                    self.change_point.reset()
            else:
                self.close_persistence_counter = max(0, self.close_persistence_counter - 1)

        state_changed = prev_is_open != self.is_open

        # 6. Anti-Contamination Baseline Lifecycle Management
        if state_changed and self.is_open:
            # Transitioned CLOSED -> OPEN: rollback to clean pre-event baseline and freeze
            self.baseline_model.on_window_open_onset()
        elif state_changed and not self.is_open:
            # Transitioned OPEN -> CLOSED: enter recovery quarantine to prevent learning cold room
            self.baseline_model.on_window_close()
        elif self.is_open:
            # Sustained open window: baseline remains strictly frozen
            self.baseline_model.is_frozen = True
        elif self.baseline_model.in_recovery_quarantine:
            # Post-close recovery in progress: check if room has reheated to near baseline
            self.baseline_model.update_recovery_quarantine(reading.indoor_temp, features.temp_rate)
        else:
            # Window is closed and not in quarantine. Check for suspicious onset conditions:
            is_suspicious = (
                evidence.final_confidence >= 0.30
                or self.open_persistence_counter > 0
                or cp_active
                or (features.temp_diff > 2.0 and features.temp_rate < -0.8)
                or (features.temp_diff < -2.0 and features.temp_rate > 0.8)
            )

            if is_suspicious:
                # Freeze baseline: do not adapt to suspicious rapid temperature departure
                self.baseline_model.is_frozen = True
            else:
                # Clean, unperturbed closed-room equilibrium: allow slow, slew-rate-limited adaptation
                self.baseline_model.is_frozen = False
                self.baseline_model.update(
                    reading.indoor_temp, reading.outdoor_temp, reading.hvac_state or "idle"
                )
                self.baseline_model.record_clean_snapshot()

        current_state = WindowState(
            is_open=self.is_open,
            confidence=evidence.final_confidence,
            detection_quality=quality,
            thermal_residual=features.thermal_residual,
            temperature_rate=features.temp_rate,
            temperature_diff=features.temp_diff,
            evidence=evidence,
            features=features,
            primary_reason=evidence.primary_reason,
            open_persistence_counter=self.open_persistence_counter,
            close_persistence_counter=self.close_persistence_counter,
            state_changed=state_changed,
        )
        self.last_state = current_state
        return current_state

    def _assess_quality(self, reading: SensorReading, features: ExtractedFeatures) -> str:
        """Determines quality rating based on sensor complement and sample health."""
        if features.sample_count < 3:
            return QUALITY_DEGRADED

        has_humidity = (
            reading.indoor_humidity is not None and reading.outdoor_humidity is not None
        )
        has_ref = reading.reference_temp is not None

        if has_humidity and has_ref:
            return QUALITY_EXCELLENT
        elif has_humidity:
            return QUALITY_GOOD
        elif has_ref:
            return QUALITY_GOOD
        return QUALITY_FAIR
