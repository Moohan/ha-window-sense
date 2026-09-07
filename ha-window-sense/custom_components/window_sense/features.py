"""Feature extraction module for Window Sense Home Assistant integration."""
from __future__ import annotations

try:
    from window_sense.features import (
        SensorReading,
        ExtractedFeatures,
        FeatureExtractor,
        calc_saturation_vapor_pressure,
        calc_actual_vapor_pressure,
        calc_absolute_humidity,
        calc_dew_point,
    )
except ImportError:
    import sys
    from pathlib import Path
    root_dir = str(Path(__file__).resolve().parents[2])
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from window_sense.features import (
        SensorReading,
        ExtractedFeatures,
        FeatureExtractor,
        calc_saturation_vapor_pressure,
        calc_actual_vapor_pressure,
        calc_absolute_humidity,
        calc_dew_point,
    )

__all__ = [
    "SensorReading",
    "ExtractedFeatures",
    "FeatureExtractor",
    "calc_saturation_vapor_pressure",
    "calc_actual_vapor_pressure",
    "calc_absolute_humidity",
    "calc_dew_point",
]
