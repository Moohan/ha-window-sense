/**
 * Complete, standard-compliant Home Assistant custom component codebase
 * Ready to drop into custom_components/inferred_window/
 */

export interface HaFile {
  filename: string;
  path: string;
  description: string;
  code: string;
}

export const HA_COMPONENT_FILES: HaFile[] = [
  {
    filename: 'manifest.json',
    path: 'custom_components/inferred_window/manifest.json',
    description: 'Home Assistant Integration Manifest',
    code: `{
  "domain": "inferred_window",
  "name": "Inferred Window-Open Detection",
  "codeowners": ["@community"],
  "config_flow": true,
  "documentation": "https://github.com/custom-components/inferred_window",
  "integration_type": "helper",
  "iot_class": "calculated",
  "issue_tracker": "https://github.com/custom-components/inferred_window/issues",
  "version": "1.0.0"
}`,
  },
  {
    filename: 'const.py',
    path: 'custom_components/inferred_window/const.py',
    description: 'Constants & Default Configuration Values',
    code: `"""Constants for Inferred Window Detection."""

DOMAIN = "inferred_window"

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

DEFAULT_OPEN_THRESHOLD = 0.80
DEFAULT_CLOSE_THRESHOLD = 0.25
DEFAULT_OPEN_PERSISTENCE = 3
DEFAULT_CLOSE_PERSISTENCE = 10
`,
  },
  {
    filename: 'algorithm.py',
    path: 'custom_components/inferred_window/algorithm.py',
    description: 'Hybrid Inference Engine (Physics, Baseline, Change-point, Evidence)',
    code: `"""Local Statistical & Thermodynamic Inference Engine for Inferred Window Detection."""
import math
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

def calc_absolute_humidity(temp_c: float, rh_percent: float) -> float:
    """Calculates absolute humidity in g/m3 using Magnus-Tetens formula."""
    if temp_c is None or rh_percent is None:
        return 0.0
    sat_vp = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    act_vp = (max(0.0, min(100.0, rh_percent)) / 100.0) * sat_vp
    temp_k = temp_c + 273.15
    return (216.7 * act_vp) / temp_k

def calc_dew_point(temp_c: float, rh_percent: float) -> float:
    """Calculates dew point in °C."""
    if temp_c is None or rh_percent is None or rh_percent <= 0:
        return -50.0
    sat_vp = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    act_vp = (rh_percent / 100.0) * sat_vp
    ln_vp = math.log(act_vp / 6.112)
    return (243.5 * ln_vp) / (17.67 - ln_vp)

@dataclass
class Reading:
    timestamp: float
    indoor_temp: float
    outdoor_temp: float
    indoor_humidity: Optional[float] = None
    outdoor_humidity: Optional[float] = None
    reference_temp: Optional[float] = None
    hvac_state: Optional[str] = "idle"

class WindowInferenceEngine:
    def __init__(self, open_thresh=0.80, close_thresh=0.25, open_persist_m=3, close_persist_m=10):
        self.open_thresh = open_thresh
        self.close_thresh = close_thresh
        self.open_persist_sec = open_persist_m * 60
        self.close_persist_sec = close_persist_m * 60

        self.history: List[Reading] = []
        self.learned_baseline: Optional[float] = None
        self.learned_conductance = 0.08
        self.is_open = False
        self.last_state_change = time.time()
        self.high_conf_start: Optional[float] = None
        self.low_conf_start: Optional[float] = None

        # Change-point detector
        self.cusum = 0.0
        self.cusum_min = 0.0
        self.change_point_active = False

    def update(self, reading: Reading) -> Dict[str, Any]:
        self.history.append(reading)
        if len(self.history) > 120:
            self.history.pop(0)

        # 1. Feature extraction
        past_5m = self._find_past(5 * 60, reading.timestamp)
        dt_hr = max(0.016, (reading.timestamp - past_5m.timestamp) / 3600.0)
        temp_rate = (reading.indoor_temp - past_5m.indoor_temp) / dt_hr
        temp_diff = reading.indoor_temp - reading.outdoor_temp

        if self.learned_baseline is None:
            self.learned_baseline = reading.indoor_temp

        # Building thermal residual
        expected_rate = self.learned_conductance * (reading.outdoor_temp - reading.indoor_temp)
        if reading.hvac_state == "heating":
            expected_rate += 2.0
        thermal_residual = temp_rate - expected_rate

        # 2. Change point
        delta = -thermal_residual
        self.cusum = max(0.0, self.cusum + delta - 0.15)
        self.cusum_min = min(self.cusum_min, self.cusum)
        self.change_point_active = (self.cusum - self.cusum_min) > 1.5

        # 3. Evidence scoring
        pos_scores = []
        neg_scores = []
        reasons = []

        # Rapid cooling towards outdoor air
        if temp_diff > 1.5 and temp_rate < -0.8:
            score = min(1.0, abs(temp_rate) / 3.0)
            pos_scores.append(score * 0.4)
            reasons.append(f"Rapid cooling ({abs(temp_rate):.1f}°C/h) towards outdoor air")

        # Thermal gradient
        if abs(temp_diff) > 2.0:
            pos_scores.append(min(1.0, (abs(temp_diff) - 1.5) / 6.0) * 0.3)

        # Humidity match
        if reading.indoor_humidity and reading.outdoor_humidity:
            in_ah = calc_absolute_humidity(reading.indoor_temp, reading.indoor_humidity)
            out_ah = calc_absolute_humidity(reading.outdoor_temp, reading.outdoor_humidity)
            past_ah = calc_absolute_humidity(past_5m.indoor_temp, past_5m.indoor_humidity)
            delta_ah = in_ah - past_ah
            if (out_ah - in_ah) < -0.5 and delta_ah < -0.1:
                pos_scores.append(min(1.0, abs(delta_ah) / 0.8) * 0.3)
                reasons.append("Absolute humidity dropped, matching dry outdoor air")

        # Change-point bonus
        if self.change_point_active:
            pos_scores.append(0.2)
            reasons.append("Thermal inflection point detected")

        # Negative evidence: reference room also dropping
        if reading.reference_temp is not None and past_5m.reference_temp is not None:
            ref_rate = (reading.reference_temp - past_5m.reference_temp) / dt_hr
            if abs(temp_rate - ref_rate) < 0.2 and abs(temp_rate) > 0.5:
                neg_scores.append(0.6)
                reasons.append("Reference room exhibits same cooling rate; house-wide drop")

        raw_pos = sum(pos_scores)
        max_neg = max(neg_scores) if neg_scores else 0.0
        confidence = max(0.0, min(1.0, raw_pos - max_neg))

        # 4. Hysteresis
        now = reading.timestamp
        if not self.is_open:
            if confidence >= self.open_thresh:
                if self.high_conf_start is None:
                    self.high_conf_start = now
                elif now - self.high_conf_start >= self.open_persist_sec:
                    self.is_open = True
                    self.last_state_change = now
            else:
                self.high_conf_start = None
        else:
            if confidence <= self.close_thresh:
                if self.low_conf_start is None:
                    self.low_conf_start = now
                elif now - self.low_conf_start >= self.close_persist_sec:
                    self.is_open = False
                    self.last_state_change = now
            else:
                self.low_conf_start = None

        # 5. Baseline update (freeze if open or confidence high)
        if confidence < 0.35 and not self.is_open:
            self.learned_baseline = 0.96 * self.learned_baseline + 0.04 * reading.indoor_temp

        primary_reason = (
            f"Rapid cooling relative to baseline (residual {thermal_residual:+.2f}°C, rate {temp_rate:+.1f}°C/h); Δ{temp_diff:.1f}°C to outdoor air."
            if confidence >= self.open_thresh else "Room behavior aligns with closed thermal baseline."
        )

        return {
            "is_open": self.is_open,
            "confidence": round(confidence * 100),
            "thermal_residual": round(thermal_residual, 2),
            "temperature_rate": round(temp_rate, 2),
            "temperature_diff": round(temp_diff, 2),
            "reason": primary_reason,
            "readiness": "Ready" if len(self.history) >= 20 else "Learning",
        }

    def _find_past(self, seconds_ago: float, now: float) -> Reading:
        target = now - seconds_ago
        closest = self.history[0]
        min_d = abs(closest.timestamp - target)
        for r in self.history:
            d = abs(r.timestamp - target)
            if d < min_d:
                min_d = d
                closest = r
        return closest
`,
  },
  {
    filename: 'coordinator.py',
    path: 'custom_components/inferred_window/coordinator.py',
    description: 'DataUpdateCoordinator listening to Home Assistant states',
    code: `"""DataUpdateCoordinator for Inferred Window Detection."""
import logging
import time
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change_event
from .const import *
from .algorithm import WindowInferenceEngine, Reading

_LOGGER = logging.getLogger(__name__)

class InferredWindowCoordinator(DataUpdateCoordinator):
    """Coordinator that collects sensor state events and runs inference."""

    def __init__(self, hass: HomeAssistant, entry):
        super().__init__(hass, _LOGGER, name=f"Inferred Window {entry.title}")
        self.entry = entry
        self.engine = WindowInferenceEngine(
            open_thresh=entry.options.get(CONF_OPEN_THRESHOLD, DEFAULT_OPEN_THRESHOLD),
            close_thresh=entry.options.get(CONF_CLOSE_THRESHOLD, DEFAULT_CLOSE_THRESHOLD),
            open_persist_m=entry.options.get(CONF_OPEN_PERSISTENCE, DEFAULT_OPEN_PERSISTENCE),
            close_persist_m=entry.options.get(CONF_CLOSE_PERSISTENCE, DEFAULT_CLOSE_PERSISTENCE),
        )
        self.data = {
            "is_open": False,
            "confidence": 0,
            "thermal_residual": 0.0,
            "temperature_rate": 0.0,
            "temperature_diff": 0.0,
            "reason": "Initializing baseline model...",
            "readiness": "Learning",
        }

    async def async_setup(self):
        """Subscribe to entity state changes."""
        tracked_entities = [
            self.entry.data[CONF_INDOOR_TEMP],
            self.entry.data[CONF_OUTDOOR_TEMP],
        ]
        for opt_key in [CONF_INDOOR_HUMIDITY, CONF_OUTDOOR_HUMIDITY, CONF_REFERENCE_TEMP, CONF_HVAC]:
            if opt_key in self.entry.data and self.entry.data[opt_key]:
                tracked_entities.append(self.entry.data[opt_key])

        self.async_on_remove(
            async_track_state_change_event(self.hass, tracked_entities, self._handle_sensor_update)
        )
        await self._async_evaluate()

    def _handle_sensor_update(self, event):
        """Called whenever one of the room sensors updates."""
        self.hass.async_create_task(self._async_evaluate())

    async def _async_evaluate(self):
        def get_float(entity_id):
            if not entity_id:
                return None
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    return float(state.state)
                except ValueError:
                    return None
            return None

        in_temp = get_float(self.entry.data.get(CONF_INDOOR_TEMP))
        out_temp = get_float(self.entry.data.get(CONF_OUTDOOR_TEMP))

        if in_temp is None or out_temp is None:
            return

        in_hum = get_float(self.entry.data.get(CONF_INDOOR_HUMIDITY))
        out_hum = get_float(self.entry.data.get(CONF_OUTDOOR_HUMIDITY))
        ref_temp = get_float(self.entry.data.get(CONF_REFERENCE_TEMP))

        hvac_state = "idle"
        hvac_id = self.entry.data.get(CONF_HVAC)
        if hvac_id:
            st = self.hass.states.get(hvac_id)
            if st and st.state:
                hvac_state = st.state

        reading = Reading(
            timestamp=time.time(),
            indoor_temp=in_temp,
            outdoor_temp=out_temp,
            indoor_humidity=in_hum,
            outdoor_humidity=out_hum,
            reference_temp=ref_temp,
            hvac_state=hvac_state,
        )

        result = self.engine.update(reading)
        self.async_set_updated_data(result)
`,
  },
  {
    filename: 'binary_sensor.py',
    path: 'custom_components/inferred_window/binary_sensor.py',
    description: 'Window Binary Sensor Entity (device_class: window)',
    code: `"""Binary Sensor platform for Inferred Window Detection."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([InferredWindowBinarySensor(coordinator, entry)])

class InferredWindowBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Exposes window open/closed status with diagnostic attributes."""
    _attr_device_class = BinarySensorDeviceClass.WINDOW
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.entry = entry
        self._attr_name = f"{entry.title} Window"
        self._attr_unique_id = f"{entry.entry_id}_window"

    @property
    def is_on(self) -> bool:
        """Return true if the window is inferred to be open."""
        return bool(self.coordinator.data.get("is_open", False))

    @property
    def extra_state_attributes(self):
        """Rich diagnostic attributes for user trust and automations."""
        data = self.coordinator.data
        return {
            "confidence": data.get("confidence", 0),
            "thermal_anomaly": data.get("thermal_residual", 0.0),
            "temperature_rate": data.get("temperature_rate", 0.0),
            "temperature_difference": data.get("temperature_diff", 0.0),
            "readiness": data.get("readiness", "Learning"),
            "reason": data.get("reason", ""),
            "detection_method": "hybrid_statistical_baseline",
        }
`,
  },
  {
    filename: 'sensor.py',
    path: 'custom_components/inferred_window/sensor.py',
    description: 'Confidence Sensor Entity (0-100%)',
    code: `"""Sensor platform for Inferred Window Detection confidence score."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([InferredWindowConfidenceSensor(coordinator, entry)])

class InferredWindowConfidenceSensor(CoordinatorEntity, SensorEntity):
    """Exposes the continuous confidence score 0-100%."""
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Window Confidence"
        self._attr_unique_id = f"{entry.entry_id}_confidence"

    @property
    def native_value(self):
        return self.coordinator.data.get("confidence", 0)
`,
  },
  {
    filename: 'config_flow.py',
    path: 'custom_components/inferred_window/config_flow.py',
    description: 'Home Assistant UI Config Flow with Entity Selectors',
    code: `"""Config flow for Inferred Window Detection."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import *

class InferredWindowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            title = user_input.get("name", "Bedroom")
            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema({
            vol.Required("name", default="Bedroom"): str,
            vol.Required(CONF_INDOOR_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"], device_class="temperature")
            ),
            vol.Required(CONF_OUTDOOR_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"], device_class="temperature")
            ),
            vol.Optional(CONF_INDOOR_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"], device_class="humidity")
            ),
            vol.Optional(CONF_OUTDOOR_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"], device_class="humidity")
            ),
            vol.Optional(CONF_REFERENCE_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"], device_class="temperature")
            ),
            vol.Optional(CONF_HVAC): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["climate"])
            ),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
`,
  },
  {
    filename: '__init__.py',
    path: 'custom_components/inferred_window/__init__.py',
    description: 'Component Setup and Platform Forwarding',
    code: `"""Inferred Window Detection integration."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
from .coordinator import InferredWindowCoordinator

PLATFORMS = ["binary_sensor", "sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    coordinator = InferredWindowCoordinator(hass, entry)
    await coordinator.async_setup()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
`,
  },
];
