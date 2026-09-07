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
        WindowSenseBaselineLearningSensor(coordinator, entry),
    ])


class WindowSenseBaselineLearningSensor(CoordinatorEntity[WindowSenseCoordinator], SensorEntity):
    """Sensor tracking whether baseline learning is currently active, slowed, or frozen."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator: WindowSenseCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Baseline Learning Status"
        self._attr_unique_id = f"{entry.entry_id}_baseline_learning_status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Window Sense",
        }

    @property
    def native_value(self) -> Optional[str]:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.baseline_trust.status

    @property
    def icon(self) -> str:
        status = self.native_value
        if status == "active":
            return "mdi:check-decagram-outline"
        elif status == "slowed":
            return "mdi:speedometer-slow"
        return "mdi:snowflake-alert"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self.coordinator.data
        if not data or not hasattr(data, "baseline_trust"):
            return {}
        trust = data.baseline_trust
        return {
            "is_trusted": trust.is_trusted,
            "learning_allowed": trust.learning_allowed,
            "trust_factor": round(trust.trust_factor, 2),
            "effective_learning_rate": round(trust.effective_learning_rate, 5),
            "confidence_band": trust.confidence_band,
            "reason": trust.reason,
            "freeze_reasons": trust.freeze_reasons,
            "expected_room_baseline_c": round(self.coordinator.engine.baseline_model.expected_temp, 2),
            "learned_conductance": round(self.coordinator.engine.baseline_model.learned_conductance, 4),
            "in_recovery_quarantine": self.coordinator.engine.baseline_model.in_recovery_quarantine,
        }


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
