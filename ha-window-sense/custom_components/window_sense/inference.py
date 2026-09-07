"""Core inference engine, baseline learning, change-point detection, and hysteresis."""
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
    QUALITY_EXCELLENT,
    QUALITY_GOOD,
    QUALITY_FAIR,
    QUALITY_DEGRADED,
)
from .features import SensorReading, ExtractedFeatures, FeatureExtractor
from .evidence import EvidenceScore, EvidenceScorer


class AdaptiveBaselineModel:
    """Estimates expected room temperature equilibrium.
    
    Uses exponential moving average with outdoor gradient compensation.
    CRITICAL: Updates are frozen while window is open to prevent learning the anomaly.
    """

    def __init__(self, initial_temp: float, learning_rate: float = 0.05):
        self.expected_temp = initial_temp
        self.learning_rate = learning_rate
        self.is_frozen = False
        self.initialized = False

    def update(self, indoor_temp: float, outdoor_temp: float, hvac_state: str = "idle") -> float:
        if not self.initialized:
            self.expected_temp = indoor_temp
            self.initialized = True
            return self.expected_temp

        if self.is_frozen:
            return self.expected_temp

        # Weight adaptation based on HVAC state
        rate = self.learning_rate
        if hvac_state in ("heating", "cooling"):
            rate *= 1.5

        # Incorporate normal slow building drift towards outdoor equilibrium
        target = (indoor_temp * 0.92) + (outdoor_temp * 0.08)
        self.expected_temp = (self.expected_temp * (1.0 - rate)) + (target * rate)
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
        # Detect sharp negative deviation
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

        # 1. Update baseline model (frozen if currently open)
        self.baseline_model.is_frozen = self.is_open
        expected_baseline = self.baseline_model.update(
            reading.indoor_temp, reading.outdoor_temp, reading.hvac_state or "idle"
        )

        # 2. Extract rolling temporal and psychrometric features
        features = self.feature_extractor.extract(expected_baseline)

        # 3. Update change-point detector
        cp_active = self.change_point.update(features.thermal_residual)

        # 4. Score positive and negative evidence
        evidence = EvidenceScorer.evaluate(
            features=features,
            change_point_active=cp_active,
            min_gradient=self.min_gradient,
        )

        # 5. Determine detection quality based on sensor availability
        quality = self._assess_quality(reading, features)

        # 6. Evaluate asymmetric hysteresis state machine
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
