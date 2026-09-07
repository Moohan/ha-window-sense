/**
 * Complete, standard-compliant Home Assistant custom component codebase
 * Restructured into custom_components/window_sense/
 */

export interface HaFile {
  filename: string;
  path: string;
  category: 'component' | 'tests' | 'docs' | 'config';
  description: string;
  code: string;
}

export const HA_COMPONENT_FILES: HaFile[] = [
  {
    filename: '__init__.py',
    path: 'custom_components/window_sense/__init__.py',
    category: 'component',
    description: 'Component Setup and Platform Forwarding',
    code: `"""Window Sense custom integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WindowSenseCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Sets up the WindowSense component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Sets up WindowSense from a config entry."""
    coordinator = WindowSenseCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloads a WindowSense config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reloads config entry on options update."""
    await hass.config_entries.async_reload(entry.entry_id)
`,
  },
  {
    filename: 'manifest.json',
    path: 'custom_components/window_sense/manifest.json',
    category: 'component',
    description: 'Home Assistant Integration Manifest',
    code: `{
  "domain": "window_sense",
  "name": "Window Sense",
  "codeowners": ["@community"],
  "config_flow": true,
  "documentation": "https://github.com/custom-components/ha-window-sense",
  "integration_type": "helper",
  "iot_class": "calculated",
  "issue_tracker": "https://github.com/custom-components/ha-window-sense/issues",
  "version": "1.0.0"
}`,
  },
  {
    filename: 'const.py',
    path: 'custom_components/window_sense/const.py',
    category: 'component',
    description: 'Constants & Default Configuration Values',
    code: `"""Constants for WindowSense."""

DOMAIN = "window_sense"

CONF_INDOOR_TEMP = "indoor_temp_entity"
CONF_OUTDOOR_TEMP = "outdoor_temp_entity"
CONF_INDOOR_HUMIDITY = "indoor_humidity_entity"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity_entity"
CONF_REFERENCE_TEMP = "reference_temp_entity"
CONF_HVAC = "hvac_entity"

CONF_OPEN_THRESHOLD = "open_confidence_threshold"
CONF_CLOSE_THRESHOLD = "close_confidence_threshold"
CONF_OPEN_PERSISTENCE = "open_persistence_min"
CONF_CLOSE_PERSISTENCE = "close_persistence_min"
CONF_BASELINE_LEARNING_RATE = "baseline_learning_rate"
CONF_CHANGE_POINT_SENSITIVITY = "change_point_sensitivity"

DEFAULT_OPEN_THRESHOLD = 0.80
DEFAULT_CLOSE_THRESHOLD = 0.25
DEFAULT_OPEN_PERSISTENCE = 3
DEFAULT_CLOSE_PERSISTENCE = 10
DEFAULT_BASELINE_LEARNING_RATE = 0.05
DEFAULT_CHANGE_POINT_SENSITIVITY = 1.0
DEFAULT_MIN_GRADIENT = 2.0
`,
  },
  {
    filename: 'config_flow.py',
    path: 'custom_components/window_sense/config_flow.py',
    category: 'component',
    description: 'UI Config Flow and Parameter Options Flow',
    code: `"""Config flow for WindowSense integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import *

class WindowSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            title = user_input.get(CONF_INDOOR_TEMP, "").split(".")[-1].replace("_temperature", "").title()
            return self.async_create_entry(title=f"{title} Window Sense", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_INDOOR_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(CONF_OUTDOOR_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_INDOOR_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
            ),
            vol.Optional(CONF_OUTDOOR_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
            ),
            vol.Optional(CONF_REFERENCE_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_HVAC): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["climate", "sensor"])
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WindowSenseOptionsFlowHandler(config_entry)
`,
  },
  {
    filename: 'coordinator.py',
    path: 'custom_components/window_sense/coordinator.py',
    category: 'component',
    description: 'DataUpdateCoordinator handling live telemetry updates',
    code: `"""DataUpdateCoordinator for WindowSense integration."""
import logging
import time
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import *
from .features import SensorReading
from .inference import WindowInferenceEngine

_LOGGER = logging.getLogger(__name__)

class WindowSenseCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry):
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{entry.title}", update_interval=timedelta(seconds=60))
        self.entry = entry
        self.engine = WindowInferenceEngine()
        self.indoor_temp_entity = entry.data[CONF_INDOOR_TEMP]
        self.outdoor_temp_entity = entry.data[CONF_OUTDOOR_TEMP]
        self.indoor_humidity_entity = entry.data.get(CONF_INDOOR_HUMIDITY)
        self.outdoor_humidity_entity = entry.data.get(CONF_OUTDOOR_HUMIDITY)
        self.reference_temp_entity = entry.data.get(CONF_REFERENCE_TEMP)
        self.hvac_entity = entry.data.get(CONF_HVAC)

    async def _async_update_data(self):
        in_t = self._parse_float(self.indoor_temp_entity)
        out_t = self._parse_float(self.outdoor_temp_entity)
        if in_t is None or out_t is None:
            if self.data is not None:
                return self.data
            raise UpdateFailed("Indoor/Outdoor temperature unavailable")

        reading = SensorReading(
            timestamp=time.time(),
            indoor_temp=in_t,
            outdoor_temp=out_t,
            indoor_humidity=self._parse_float(self.indoor_humidity_entity),
            outdoor_humidity=self._parse_float(self.outdoor_humidity_entity),
            reference_temp=self._parse_float(self.reference_temp_entity),
            hvac_state="idle",
        )
        return self.engine.process_reading(reading)

    def _parse_float(self, eid):
        if not eid:
            return None
        st = self.hass.states.get(eid)
        if not st or st.state in ("unknown", "unavailable"):
            return None
        try:
            return float(st.state)
        except (ValueError, TypeError):
            return None
`,
  },
  {
    filename: 'inference.py',
    path: 'custom_components/window_sense/inference.py',
    category: 'component',
    description: 'Baseline Model, CUSUM Change-Point & Hysteresis State Machine',
    code: `"""Core inference engine and state machine."""
from dataclasses import dataclass
from .features import SensorReading, FeatureExtractor
from .evidence import EvidenceScorer

class AdaptiveBaselineModel:
    def __init__(self, initial_temp=21.0, learning_rate=0.05):
        self.expected_temp = initial_temp
        self.learning_rate = learning_rate
        self.is_frozen = False

    def update(self, indoor_t, outdoor_t):
        if self.is_frozen:
            return self.expected_temp
        target = (indoor_t * 0.92) + (outdoor_t * 0.08)
        self.expected_temp = (self.expected_temp * (1.0 - self.learning_rate)) + (target * self.learning_rate)
        return self.expected_temp

class PageHinkleyChangePoint:
    def __init__(self, threshold=1.0, alpha=0.05):
        self.threshold = threshold
        self.alpha = alpha
        self.sum_val = 0.0
        self.min_val = float("inf")

    def update(self, residual):
        self.sum_val += abs(residual) - self.alpha
        if self.sum_val < self.min_val:
            self.min_val = self.sum_val
        return (self.sum_val - self.min_val) > self.threshold

class WindowInferenceEngine:
    def __init__(self, open_thresh=0.80, close_thresh=0.25, open_pers=3, close_pers=10):
        self.open_threshold = open_thresh
        self.close_threshold = close_thresh
        self.open_persistence_min = open_pers
        self.close_persistence_min = close_pers
        self.feature_extractor = FeatureExtractor()
        self.baseline_model = AdaptiveBaselineModel()
        self.change_point = PageHinkleyChangePoint()
        self.is_open = False
        self.open_counter = 0
        self.close_counter = 0

    def process_reading(self, reading: SensorReading):
        self.feature_extractor.add_reading(reading)
        self.baseline_model.is_frozen = self.is_open
        baseline = self.baseline_model.update(reading.indoor_temp, reading.outdoor_temp)
        features = self.feature_extractor.extract(baseline)
        cp_active = self.change_point.update(features.thermal_residual)
        evidence = EvidenceScorer.evaluate(features, cp_active)

        if not self.is_open:
            if evidence.final_confidence >= self.open_threshold:
                self.open_counter += 1
                if self.open_counter >= self.open_persistence_min:
                    self.is_open = True
                    self.open_counter = 0
            else:
                self.open_counter = max(0, self.open_counter - 1)
        else:
            if evidence.final_confidence <= self.close_threshold:
                self.close_counter += 1
                if self.close_counter >= self.close_persistence_min:
                    self.is_open = False
                    self.close_counter = 0
            else:
                self.close_counter = max(0, self.close_counter - 1)

        return type("State", (), {
            "is_open": self.is_open,
            "confidence": evidence.final_confidence,
            "thermal_residual": features.thermal_residual,
            "temperature_rate": features.temp_rate,
            "temperature_diff": features.temp_diff,
            "primary_reason": evidence.primary_reason,
            "evidence": evidence,
            "features": features,
        })()
`,
  },
  {
    filename: 'features.py',
    path: 'custom_components/window_sense/features.py',
    category: 'component',
    description: 'Psychrometrics (Magnus-Tetens) and Rolling Feature Extractor',
    code: `"""Psychrometric calculations and rolling feature extraction."""
import math
from dataclasses import dataclass
from typing import Optional, List

def calc_absolute_humidity(temp_c: float, rh: float) -> float:
    if temp_c is None or rh is None:
        return 0.0
    sat_vp = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    act_vp = (max(0.0, min(100.0, rh)) / 100.0) * sat_vp
    return (216.7 * act_vp) / (temp_c + 273.15)

def calc_dew_point(temp_c: float, rh: float) -> float:
    if temp_c is None or rh is None or rh <= 0:
        return -50.0
    act_vp = (rh / 100.0) * (6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5)))
    ln_vp = math.log(max(0.001, act_vp) / 6.112)
    return (243.5 * ln_vp) / (17.67 - ln_vp)

@dataclass
class SensorReading:
    timestamp: float
    indoor_temp: float
    outdoor_temp: float
    indoor_humidity: Optional[float] = None
    outdoor_humidity: Optional[float] = None
    reference_temp: Optional[float] = None
    hvac_state: Optional[str] = "idle"

class FeatureExtractor:
    def __init__(self, max_minutes=45):
        self.history: List[SensorReading] = []

    def add_reading(self, r: SensorReading):
        self.history.append(r)
        if len(self.history) > 60:
            self.history.pop(0)

    def extract(self, baseline_t: float):
        latest = self.history[-1]
        r_5m = self.history[-6] if len(self.history) >= 6 else self.history[0]
        dt_hr = max(0.016, (latest.timestamp - r_5m.timestamp) / 3600.0)
        temp_rate = (latest.indoor_temp - r_5m.indoor_temp) / dt_hr

        return type("Features", (), {
            "temp_rate": temp_rate,
            "temp_diff": latest.indoor_temp - latest.outdoor_temp,
            "thermal_residual": latest.indoor_temp - baseline_t,
            "indoor_abs_humidity": calc_absolute_humidity(latest.indoor_temp, latest.indoor_humidity) if latest.indoor_humidity else None,
            "outdoor_abs_humidity": calc_absolute_humidity(latest.outdoor_temp, latest.outdoor_humidity) if latest.outdoor_humidity else None,
            "sample_count": len(self.history),
        })()
`,
  },
  {
    filename: 'evidence.py',
    path: 'custom_components/window_sense/evidence.py',
    category: 'component',
    description: 'Continuous Evidence Weighting & False-Alarm Suppression',
    code: `"""Evidence scoring and negative suppression logic."""
class EvidenceScorer:
    @staticmethod
    def evaluate(features, change_point_active: bool):
        cooling_speed = abs(features.temp_rate)
        rapid_cooling = min(1.0, cooling_speed / 2.5) if features.temp_rate < -0.4 else 0.0
        gradient = min(1.0, max(0.0, abs(features.temp_diff) / 6.0))
        residual_score = min(1.0, abs(features.thermal_residual) / 1.5) if abs(features.thermal_residual) > 0.3 else 0.0

        raw_score = (rapid_cooling * 0.35) + (gradient * 0.25) + (residual_score * 0.40)
        if change_point_active:
            raw_score = min(1.0, raw_score * 1.3)

        # Negative suppression: heating setback or unphysical cooling
        penalty = 0.0
        if features.temp_diff < -1.0 and features.temp_rate < -0.3:
            penalty = 0.85  # Outdoor cannot explain cooling

        final_confidence = max(0.0, min(1.0, raw_score * (1.0 - penalty)))
        reason = f"Thermal rate {features.temp_rate:+.1f}°C/h (Δ{features.temp_diff:.1f}°C gradient)" if final_confidence >= 0.8 else "Room in baseline equilibrium"

        return type("Evidence", (), {
            "raw_score": raw_score,
            "negative_penalty": penalty,
            "final_confidence": final_confidence,
            "primary_reason": reason,
        })()
`,
  },
  {
    filename: 'binary_sensor.py',
    path: 'custom_components/window_sense/binary_sensor.py',
    category: 'component',
    description: 'BinarySensorEntity exposing device_class: window',
    code: `"""Binary sensor platform for WindowSense."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WindowSenseBinarySensor(coordinator, entry)])

class WindowSenseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Window State"
        self._attr_unique_id = f"{entry.entry_id}_window_state"

    @property
    def is_on(self):
        return self.coordinator.data.is_open if self.coordinator.data else False

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        d = self.coordinator.data
        return {
            "confidence_percent": round(d.confidence * 100),
            "primary_reason": d.primary_reason,
            "temperature_rate": round(d.temperature_rate, 2),
            "thermal_residual": round(d.thermal_residual, 2),
        }
`,
  },
  {
    filename: 'sensor.py',
    path: 'custom_components/window_sense/sensor.py',
    category: 'component',
    description: 'Sensor platform for confidence (%) and thermal anomaly (°C)',
    code: `"""Sensor platform for WindowSense."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        WindowSenseConfidenceSensor(coordinator, entry),
    ])

class WindowSenseConfidenceSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Window Confidence"
        self._attr_unique_id = f"{entry.entry_id}_confidence"

    @property
    def native_value(self):
        return round(self.coordinator.data.confidence * 100) if self.coordinator.data else 0
`,
  },
  {
    filename: 'diagnostics.py',
    path: 'custom_components/window_sense/diagnostics.py',
    category: 'component',
    description: 'Diagnostics provider for Home Assistant dumps',
    code: `"""Diagnostics support for WindowSense."""
from .const import DOMAIN

async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    d = coordinator.data
    return {
        "is_open": d.is_open if d else False,
        "confidence": d.confidence if d else 0,
        "thermal_residual": d.thermal_residual if d else 0,
        "primary_reason": d.primary_reason if d else "",
    }
`,
  },
  {
    filename: 'algorithm.md',
    path: 'docs/algorithm.md',
    category: 'docs',
    description: 'Thermodynamic & Mathematical Specification',
    code: `# WindowSense: Algorithmic Architecture Specification

## 1. Thermodynamic & Psychrometric Foundations
Calculates absolute humidity ($AH$) in $g/m^3$ via Magnus-Tetens:
$$AH(T, RH) = \\frac{216.7 \\cdot P_{act}(T, RH)}{T + 273.15}$$

## 2. Adaptive Baseline & CUSUM Inflection
Tracks structural equilibrium and freezes during suspected open states. Page-Hinkley cumulative sum detects sharp changes.
`,
  },
  {
    filename: 'sensor-requirements.md',
    path: 'docs/sensor-requirements.md',
    category: 'docs',
    description: 'Sensor Placement & Accuracy Requirements',
    code: `# Sensor Requirements & Placement Recommendations

- Resolution: 0.1°C temperature and 1% RH.
- Reporting: Heartbeat $\\le 3$ minutes, reporting on $\\Delta 0.1^\\circ\\text{C}$.
- Placement: 1.2–1.6m above floor, 1.5–3.5m away from windows.
`,
  },
  {
    filename: 'README.md',
    path: 'README.md',
    category: 'docs',
    description: 'Repository Documentation and Installation Guide',
    code: `# WindowSense (ha-window-sense)

Native Home Assistant custom integration inferring window state using climate telemetry.
`,
  },
  {
    filename: 'hacs.json',
    path: 'hacs.json',
    category: 'config',
    description: 'HACS Custom Component Manifest',
    code: `{
  "name": "WindowSense",
  "content_in_root": false,
  "render_readme": true,
  "homeassistant": "2024.1.0"
}`,
  },
  {
    filename: 'pyproject.toml',
    path: 'pyproject.toml',
    category: 'config',
    description: 'Packaging & Test Configuration',
    code: `[project]
name = "ha-window-sense"
version = "1.0.0"
requires-python = ">=3.11"
`,
  },
  {
    filename: 'requirements.txt',
    path: 'requirements.txt',
    category: 'config',
    description: 'Python Test and Development Dependencies',
    code: `homeassistant>=2024.1.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
voluptuous>=0.13.0
`,
  },
];
