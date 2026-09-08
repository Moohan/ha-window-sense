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
    DEFAULT_MAX_SENSOR_STALE_SEC,
    INFERENCE_STATUS_VALID,
    INFERENCE_STATUS_DEGRADED,
    INFERENCE_STATUS_INSUFFICIENT_DATA,
    QUALITY_EXCELLENT,
    QUALITY_GOOD,
    QUALITY_FAIR,
    QUALITY_DEGRADED,
    QUALITY_INSUFFICIENT,
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
        abs_res = abs(residual)
        if abs_res < 0.2:
            self.sum_val = max(0.0, self.sum_val - self.alpha)
            if self.sum_val < self.min_val:
                self.min_val = self.sum_val
            self.is_triggered = False
            return False

        self.sum_val += abs_res - self.alpha
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
    inference_status: str             # "valid" | "degraded" | "insufficient_data"
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

    def _determine_status_and_quality(
        self, reading: SensorReading, features: ExtractedFeatures
    ) -> tuple[str, str, Optional[str]]:
        """Evaluates data readiness and quality."""
        if reading.indoor_temp is None or math.isnan(reading.indoor_temp) or math.isinf(reading.indoor_temp):
            return INFERENCE_STATUS_INSUFFICIENT_DATA, QUALITY_INSUFFICIENT, "Indoor temperature sensor value unavailable or non-numeric."

        if features.indoor_stale_sec > DEFAULT_MAX_SENSOR_STALE_SEC:
            return INFERENCE_STATUS_INSUFFICIENT_DATA, QUALITY_INSUFFICIENT, f"Indoor temperature sensor stale ({int(features.indoor_stale_sec / 60)}m since last update)."

        if reading.outdoor_temp is None or math.isnan(reading.outdoor_temp) or math.isinf(reading.outdoor_temp):
            return INFERENCE_STATUS_INSUFFICIENT_DATA, QUALITY_INSUFFICIENT, "Outdoor temperature sensor value unavailable or non-numeric."

        if features.outdoor_stale_sec > DEFAULT_MAX_SENSOR_STALE_SEC:
            return INFERENCE_STATUS_INSUFFICIENT_DATA, QUALITY_INSUFFICIENT, f"Outdoor temperature sensor stale ({int(features.outdoor_stale_sec / 60)}m since last update)."

        if features.sample_count < 3:
            return INFERENCE_STATUS_INSUFFICIENT_DATA, QUALITY_INSUFFICIENT, f"Insufficient history samples ({features.sample_count}/3 required)."

        if features.post_outage_suppressed:
            return INFERENCE_STATUS_DEGRADED, QUALITY_DEGRADED, "Recent sensor outage/gap detected; rate derivatives temporarily suppressed."

        has_humidity = (
            reading.indoor_humidity is not None
            and not math.isnan(reading.indoor_humidity)
            and reading.outdoor_humidity is not None
            and not math.isnan(reading.outdoor_humidity)
        )
        has_ref = (
            reading.reference_temp is not None
            and not math.isnan(reading.reference_temp)
        )

        if has_humidity and has_ref:
            return INFERENCE_STATUS_VALID, QUALITY_EXCELLENT, None
        elif has_humidity or has_ref:
            return INFERENCE_STATUS_VALID, QUALITY_GOOD, None

        return INFERENCE_STATUS_VALID, QUALITY_FAIR, None

    def process_reading(self, reading: SensorReading) -> WindowState:
        """Processes an incoming sensor reading and updates the inferred state machine."""
        self.feature_extractor.add_reading(reading)

        if not self.baseline_model.initialized and reading.indoor_temp is not None and not math.isnan(reading.indoor_temp):
            outdoor = reading.outdoor_temp if (reading.outdoor_temp is not None and not math.isnan(reading.outdoor_temp)) else reading.indoor_temp
            self.baseline_model.update(
                reading.indoor_temp, outdoor, reading.hvac_state or "idle"
            )

        features = self.feature_extractor.extract(self.baseline_model.expected_temp)

        inf_status, quality, deficiency_reason = self._determine_status_and_quality(reading, features)

        if inf_status == INFERENCE_STATUS_INSUFFICIENT_DATA:
            cp_active = False
            evidence = EvidenceScore(primary_reason=f"Insufficient data: {deficiency_reason}")

            trust_state = BaselineTrustEvaluator.evaluate(
                reading=reading,
                features=features,
                evidence=evidence,
                is_open=self.is_open,
                in_recovery_quarantine=self.baseline_model.in_recovery_quarantine,
                change_point_active=False,
                last_change_point_time=self.last_change_point_time,
                last_reading_time=self.last_reading_time,
                open_persistence_counter=self.open_persistence_counter,
                base_learning_rate=self.baseline_model.learning_rate,
                policy=self.baseline_model.policy,
            )

            current_state = WindowState(
                is_open=self.is_open,
                confidence=0.0,
                detection_quality=quality,
                inference_status=inf_status,
                thermal_residual=features.thermal_residual,
                temperature_rate=0.0,
                temperature_diff=features.temp_diff,
                evidence=evidence,
                features=features,
                primary_reason=evidence.primary_reason,
                open_persistence_counter=self.open_persistence_counter,
                close_persistence_counter=self.close_persistence_counter,
                state_changed=False,
                baseline_trust=trust_state,
            )
            self.last_reading_time = reading.timestamp if (reading.timestamp is not None and not math.isnan(reading.timestamp)) else self.last_reading_time
            self.last_state = current_state
            return current_state

        if abs(features.temp_rate) >= 0.3 or features.temp_diff < 0:
            cp_active = self.change_point.update(-features.thermal_residual)
        else:
            self.change_point.reset()
            cp_active = False

        if cp_active:
            self.last_change_point_time = reading.timestamp

        evidence = EvidenceScorer.evaluate(
            features=features,
            change_point_active=cp_active,
            min_gradient=self.min_gradient,
            is_currently_open=self.is_open,
        )

        prev_is_open = self.is_open

        if not self.is_open:
            if evidence.final_confidence >= self.open_threshold:
                self.open_persistence_counter += 1
                if self.open_persistence_counter >= self.open_persistence_min:
                    self.is_open = True
                    self.open_persistence_counter = 0
            else:
                self.open_persistence_counter = max(0, self.open_persistence_counter - 1)
        else:
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

        if state_changed and self.is_open:
            self.baseline_model.on_window_open_onset()
        elif state_changed and not self.is_open:
            self.baseline_model.on_window_close()
            self.change_point.reset()
            self.last_change_point_time = None
        elif not self.is_open and self.baseline_model.in_recovery_quarantine:
            still_quarantined = self.baseline_model.update_recovery_quarantine(reading.indoor_temp, features.temp_rate)
            if not still_quarantined:
                self.change_point.reset()
                self.last_change_point_time = None

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
            inference_status=inf_status,
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
