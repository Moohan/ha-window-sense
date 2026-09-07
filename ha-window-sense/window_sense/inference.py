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
from .baseline import (
    AdaptiveBaselineModel,
    BaselineTrustPolicy,
    BaselineTrustState,
    BaselineTrustEvaluator,
)


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
    baseline_trust: BaselineTrustState


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
        initial_temp: float = 21.0,
        baseline_policy: Optional[BaselineTrustPolicy] = None,
    ):
        self.open_threshold = open_threshold
        self.close_threshold = close_threshold
        self.open_persistence_min = open_persistence_min
        self.close_persistence_min = close_persistence_min
        self.min_gradient = min_gradient

        self.feature_extractor = FeatureExtractor(max_history_minutes=45)
        self.baseline_model = AdaptiveBaselineModel(
            initial_temp=initial_temp,
            learning_rate=baseline_learning_rate,
            policy=baseline_policy,
        )
        self.change_point = PageHinkleyChangePoint(threshold=change_point_sensitivity)

        self.is_open: bool = False
        self.open_persistence_counter: int = 0
        self.close_persistence_counter: int = 0
        self.last_change_point_time: Optional[float] = None
        self.last_reading_time: Optional[float] = None
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
        if cp_active:
            self.last_change_point_time = reading.timestamp

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
                    self.last_change_point_time = None
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
        elif not self.is_open and self.baseline_model.in_recovery_quarantine:
            # Post-close recovery in progress: check if room has reheated to near baseline
            self.baseline_model.update_recovery_quarantine(reading.indoor_temp, features.temp_rate)

        # 7. Evaluate Trusted Baseline Learning (Multi-tier Confidence Bands)
        trust_state = BaselineTrustEvaluator.evaluate(
            reading=reading,
            features=features,
            evidence=evidence,
            is_open=self.is_open,
            in_recovery_quarantine=self.baseline_model.in_recovery_quarantine,
            change_point_active=cp_active,
            last_change_point_time=self.last_change_point_time,
            last_reading_time=self.last_reading_time,
            open_persistence_counter=self.open_persistence_counter,
            base_learning_rate=self.baseline_model.learning_rate,
            policy=self.baseline_model.policy,
        )

        # Update baseline model and learned thermal parameters
        self.baseline_model.update(
            indoor_temp=reading.indoor_temp,
            outdoor_temp=reading.outdoor_temp,
            hvac_state=reading.hvac_state or "idle",
            trust_state=trust_state,
            temp_rate=features.temp_rate,
        )

        self.last_reading_time = reading.timestamp

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
            baseline_trust=trust_state,
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
