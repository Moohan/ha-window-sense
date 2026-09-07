"""Constants for Window Sense pure algorithm library."""

DOMAIN = "window_sense"

# Default algorithm thresholds and parameters
DEFAULT_OPEN_THRESHOLD = 0.80
DEFAULT_CLOSE_THRESHOLD = 0.25
DEFAULT_OPEN_PERSISTENCE = 3
DEFAULT_CLOSE_PERSISTENCE = 10
DEFAULT_BASELINE_LEARNING_RATE = 0.03
DEFAULT_CHANGE_POINT_SENSITIVITY = 1.0
DEFAULT_MIN_GRADIENT = 2.0
DEFAULT_MAX_BASELINE_SLEW_PER_MIN = 0.015  # Max ~0.9°C/h passive drift

# Detection Quality States
QUALITY_EXCELLENT = "excellent"
QUALITY_GOOD = "good"
QUALITY_FAIR = "fair"
QUALITY_DEGRADED = "degraded"
QUALITY_INSUFFICIENT = "insufficient"
