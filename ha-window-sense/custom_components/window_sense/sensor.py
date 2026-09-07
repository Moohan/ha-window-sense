"""Sensor platform for WindowSense."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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
    """Sets up WindowSense sensor entities."""
    coordinator: WindowSenseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        WindowSenseConfidenceSensor(coordinator, entry),
        WindowSenseThermalResidualSensor(coordinator, entry),
        WindowSenseRateSensor(coordinator, entry),
    ])


class WindowSenseConfidenceSensor(CoordinatorEntity[WindowSenseCoordinator], SensorEntity):
    """Sensor tracking inference confidence (0 to 100%)."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:shield-check-outline"

    def __init__(self, coordinator: WindowSenseCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Window Confidence"
        self._attr_unique_id = f"{entry.entry_id}_window_confidence"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Window Sense",
        }

    @property
    def native_value(self) -> Optional[int]:
        if self.coordinator.data is None:
            return None
        return int(round(self.coordinator.data.confidence * 100))


class WindowSenseThermalResidualSensor(CoordinatorEntity[WindowSenseCoordinator], SensorEntity):
    """Sensor tracking thermal residual deviation from expected room equilibrium."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    def __init__(self, coordinator: WindowSenseCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Thermal Anomaly Residual"
        self._attr_unique_id = f"{entry.entry_id}_thermal_residual"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Window Sense",
        }

    @property
    def native_value(self) -> Optional[float]:
        if self.coordinator.data is None:
            return None
        return round(self.coordinator.data.thermal_residual, 2)


class WindowSenseRateSensor(CoordinatorEntity[WindowSenseCoordinator], SensorEntity):
    """Sensor tracking rate of temperature change (°C/h)."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C/h"
    _attr_icon = "mdi:thermometer-chevron-down"

    def __init__(self, coordinator: WindowSenseCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Temperature Drift Rate"
        self._attr_unique_id = f"{entry.entry_id}_temp_drift_rate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Window Sense",
        }

    @property
    def native_value(self) -> Optional[float]:
        if self.coordinator.data is None:
            return None
        return round(self.coordinator.data.temperature_rate, 2)
