"""Window Sense: Pure Python thermodynamic inference, feature extraction, and baseline modeling."""
from __future__ import annotations

from .const import (
    DOMAIN,
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
    QUALITY_INSUFFICIENT,
)
from .features import (
    SensorReading,
    ExtractedFeatures,
    FeatureExtractor,
    calc_saturation_vapor_pressure,
    calc_actual_vapor_pressure,
    calc_absolute_humidity,
    calc_dew_point,
)
from .evidence import EvidenceScore, EvidenceScorer
from .inference import (
    AdaptiveBaselineModel,
    PageHinkleyChangePoint,
    WindowState,
    WindowInferenceEngine,
)

__all__ = [
    "DOMAIN",
    "DEFAULT_OPEN_THRESHOLD",
    "DEFAULT_CLOSE_THRESHOLD",
    "DEFAULT_OPEN_PERSISTENCE",
    "DEFAULT_CLOSE_PERSISTENCE",
    "DEFAULT_BASELINE_LEARNING_RATE",
    "DEFAULT_CHANGE_POINT_SENSITIVITY",
    "DEFAULT_MIN_GRADIENT",
    "DEFAULT_MAX_BASELINE_SLEW_PER_MIN",
    "QUALITY_EXCELLENT",
    "QUALITY_GOOD",
    "QUALITY_FAIR",
    "QUALITY_DEGRADED",
    "QUALITY_INSUFFICIENT",
    "SensorReading",
    "ExtractedFeatures",
    "FeatureExtractor",
    "calc_saturation_vapor_pressure",
    "calc_actual_vapor_pressure",
    "calc_absolute_humidity",
    "calc_dew_point",
    "EvidenceScore",
    "EvidenceScorer",
    "AdaptiveBaselineModel",
    "PageHinkleyChangePoint",
    "WindowState",
    "WindowInferenceEngine",
]
