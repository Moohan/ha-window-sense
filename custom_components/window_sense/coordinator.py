"""DataUpdateCoordinator for WindowSense integration."""
import logging
import time
from datetime import timedelta
from typing import Optional, Dict, Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    CONF_INDOOR_HUMIDITY,
    CONF_OUTDOOR_HUMIDITY,
    CONF_REFERENCE_TEMP,
    CONF_HVAC,
    CONF_OPEN_THRESHOLD,
    CONF_CLOSE_THRESHOLD,
    CONF_OPEN_PERSISTENCE,
    CONF_CLOSE_PERSISTENCE,
    CONF_BASELINE_LEARNING_RATE,
    CONF_CHANGE_POINT_SENSITIVITY,
    DEFAULT_OPEN_THRESHOLD,
    DEFAULT_CLOSE_THRESHOLD,
    DEFAULT_OPEN_PERSISTENCE,
    DEFAULT_CLOSE_PERSISTENCE,
    DEFAULT_BASELINE_LEARNING_RATE,
    DEFAULT_CHANGE_POINT_SENSITIVITY,
)
from .features import SensorReading
from .inference import WindowInferenceEngine, WindowState

_LOGGER = logging.getLogger(__name__)


class WindowSenseCoordinator(DataUpdateCoordinator[WindowState]):
    """Coordinates sensor data acquisition and runs the WindowSense inference engine."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.title}",
            update_interval=timedelta(seconds=60),
        )
        self.entry = entry

        # Extract config values
        cfg = entry.data
        opts = entry.options

        open_th = opts.get(CONF_OPEN_THRESHOLD, cfg.get(CONF_OPEN_THRESHOLD, DEFAULT_OPEN_THRESHOLD))
        close_th = opts.get(CONF_CLOSE_THRESHOLD, cfg.get(CONF_CLOSE_THRESHOLD, DEFAULT_CLOSE_THRESHOLD))
        open_pers = opts.get(CONF_OPEN_PERSISTENCE, cfg.get(CONF_OPEN_PERSISTENCE, DEFAULT_OPEN_PERSISTENCE))
        close_pers = opts.get(CONF_CLOSE_PERSISTENCE, cfg.get(CONF_CLOSE_PERSISTENCE, DEFAULT_CLOSE_PERSISTENCE))
        learn_rate = opts.get(CONF_BASELINE_LEARNING_RATE, cfg.get(CONF_BASELINE_LEARNING_RATE, DEFAULT_BASELINE_LEARNING_RATE))
        cp_sens = opts.get(CONF_CHANGE_POINT_SENSITIVITY, cfg.get(CONF_CHANGE_POINT_SENSITIVITY, DEFAULT_CHANGE_POINT_SENSITIVITY))

        self.engine = WindowInferenceEngine(
            open_threshold=open_th,
            close_threshold=close_th,
            open_persistence_min=open_pers,
            close_persistence_min=close_pers,
            baseline_learning_rate=learn_rate,
            change_point_sensitivity=cp_sens,
        )

        self.indoor_temp_entity = cfg[CONF_INDOOR_TEMP]
        self.outdoor_temp_entity = cfg[CONF_OUTDOOR_TEMP]
        self.indoor_humidity_entity = cfg.get(CONF_INDOOR_HUMIDITY)
        self.outdoor_humidity_entity = cfg.get(CONF_OUTDOOR_HUMIDITY)
        self.reference_temp_entity = cfg.get(CONF_REFERENCE_TEMP)
        self.hvac_entity = cfg.get(CONF_HVAC)

    def _parse_float(self, entity_id: Optional[str]) -> Optional[float]:
        """Safely parses float from entity state."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_hvac_state(self) -> str:
        """Determines current HVAC state string."""
        if not self.hvac_entity:
            return "idle"
        state = self.hass.states.get(self.hvac_entity)
        if not state or state.state in ("unknown", "unavailable"):
            return "idle"
        return str(state.state).lower()

    async def _async_update_data(self) -> WindowState:
        """Polls current sensors, constructs a SensorReading, and updates engine."""
        indoor_temp = self._parse_float(self.indoor_temp_entity)
        outdoor_temp = self._parse_float(self.outdoor_temp_entity)

        if indoor_temp is None or outdoor_temp is None:
            if self.data is not None:
                return self.data
            raise UpdateFailed("Indoor or outdoor temperature entity unavailable")

        reading = SensorReading(
            timestamp=time.time(),
            indoor_temp=indoor_temp,
            outdoor_temp=outdoor_temp,
            indoor_humidity=self._parse_float(self.indoor_humidity_entity),
            outdoor_humidity=self._parse_float(self.outdoor_humidity_entity),
            reference_temp=self._parse_float(self.reference_temp_entity),
            hvac_state=self._get_hvac_state(),
        )

        try:
            state = self.engine.process_reading(reading)
            return state
        except Exception as err:
            _LOGGER.exception("Error processing window state in WindowSense: %s", err)
            raise UpdateFailed(f"Inference calculation error: {err}") from err
