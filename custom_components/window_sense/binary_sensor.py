"""Binary sensor platform for WindowSense."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WindowSenseCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up WindowSense binary sensor from a config entry."""
    coordinator: WindowSenseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WindowSenseBinarySensor(coordinator, entry)])


class WindowSenseBinarySensor(CoordinatorEntity[WindowSenseCoordinator], BinarySensorEntity):
    """Binary sensor representing the inferred open/closed state of a window."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, coordinator: WindowSenseCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Window State"
        self._attr_unique_id = f"{entry.entry_id}_window_state"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Window Sense",
            "manufacturer": "WindowSense Community",
            "model": "Thermodynamic Statistical Inference",
            "sw_version": "1.0.0",
        }

    @property
    def is_on(self) -> Optional[bool]:
        """Returns True if the window is inferred to be open."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.is_open

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Exposes detailed diagnostic attributes for Home Assistant dashboards and automations."""
        data = self.coordinator.data
        if not data:
            return {}

        return {
            "confidence_percent": round(data.confidence * 100),
            "detection_quality": data.detection_quality,
            "primary_reason": data.primary_reason,
            "thermal_residual_c": round(data.thermal_residual, 2),
            "temperature_rate_c_per_h": round(data.temperature_rate, 2),
            "indoor_outdoor_diff_c": round(data.temperature_diff, 1),
            "open_persistence_count": data.open_persistence_counter,
            "close_persistence_count": data.close_persistence_counter,
            "raw_positive_score": round(data.evidence.raw_score, 2),
            "negative_penalty": round(data.evidence.negative_penalty, 2),
            "rapid_cooling_score": round(data.evidence.rapid_cooling_faster_than_expected, 2),
            "humidity_alignment_score": round(data.evidence.humidity_matches_outdoor, 2),
            "local_divergence_score": round(data.evidence.local_divergence_from_ref_room, 2),
            "hvac_state": data.features.hvac_state,
            "baseline_learning_status": data.baseline_trust.status,
            "baseline_learning_reason": data.baseline_trust.reason,
            "baseline_trust_factor": round(data.baseline_trust.trust_factor, 2),
            "baseline_confidence_band": data.baseline_trust.confidence_band,
        }
