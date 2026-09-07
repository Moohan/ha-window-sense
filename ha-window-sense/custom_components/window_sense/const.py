"""Constants for the WindowSense custom integration."""

DOMAIN = "window_sense"

# Required entity keys
CONF_INDOOR_TEMP = "indoor_temp_entity"
CONF_OUTDOOR_TEMP = "outdoor_temp_entity"

# Optional entity keys
CONF_INDOOR_HUMIDITY = "indoor_humidity_entity"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity_entity"
CONF_REFERENCE_TEMP = "reference_temp_entity"
CONF_REFERENCE_HUMIDITY = "reference_humidity_entity"
CONF_HVAC = "hvac_entity"
CONF_CO2 = "co2_entity"
CONF_OCCUPANCY = "occupancy_entity"

# Tuning parameters
CONF_OPEN_THRESHOLD = "open_confidence_threshold"
CONF_CLOSE_THRESHOLD = "close_confidence_threshold"
CONF_OPEN_PERSISTENCE = "open_persistence_min"
CONF_CLOSE_PERSISTENCE = "close_persistence_min"
CONF_BASELINE_LEARNING_RATE = "baseline_learning_rate"
CONF_CHANGE_POINT_SENSITIVITY = "change_point_sensitivity"
CONF_MIN_GRADIENT = "min_indoor_outdoor_gradient"

# Default values
DEFAULT_OPEN_THRESHOLD = 0.80
DEFAULT_CLOSE_THRESHOLD = 0.25
DEFAULT_OPEN_PERSISTENCE = 3
DEFAULT_CLOSE_PERSISTENCE = 10
DEFAULT_BASELINE_LEARNING_RATE = 0.05
DEFAULT_CHANGE_POINT_SENSITIVITY = 1.0
DEFAULT_MIN_GRADIENT = 2.0

# Detection Quality States
QUALITY_EXCELLENT = "excellent"
QUALITY_GOOD = "good"
QUALITY_FAIR = "fair"
QUALITY_DEGRADED = "degraded"
QUALITY_INSUFFICIENT = "insufficient"
