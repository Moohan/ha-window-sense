"""Psychrometric calculations and rolling feature extraction for Window Sense."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


def calc_saturation_vapor_pressure(temp_c: float) -> float:
    """Calculates saturation vapor pressure in hPa using Magnus-Tetens formula.
    
    Valid over liquid water between -45°C and +60°C.
    """
    if temp_c is None:
        return 0.0
    return 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))


def calc_actual_vapor_pressure(temp_c: float, rh_percent: float) -> float:
    """Calculates actual vapor pressure in hPa from temperature and relative humidity."""
    if temp_c is None or rh_percent is None:
        return 0.0
    clamped_rh = max(0.0, min(100.0, rh_percent))
    return (clamped_rh / 100.0) * calc_saturation_vapor_pressure(temp_c)


def calc_absolute_humidity(temp_c: float, rh_percent: float) -> float:
    """Calculates absolute humidity in g/m3.
    
    Formula: AH = (216.7 * P_actual_hPa) / (T_Celsius + 273.15)
    Unlike relative humidity, absolute humidity represents the actual mass of water
    vapor per unit volume of air, invariant to temperature changes alone.
    """
    if temp_c is None or rh_percent is None:
        return 0.0
    act_vp = calc_actual_vapor_pressure(temp_c, rh_percent)
    temp_k = temp_c + 273.15
    return (216.7 * act_vp) / temp_k


def calc_dew_point(temp_c: float, rh_percent: float) -> float:
    """Calculates dew point temperature in °C."""
    if temp_c is None or rh_percent is None or rh_percent <= 0:
        return -50.0
    act_vp = calc_actual_vapor_pressure(temp_c, rh_percent)
    if act_vp <= 0.0:
        return -50.0
    ln_vp = math.log(act_vp / 6.112)
    return (243.5 * ln_vp) / (17.67 - ln_vp)


@dataclass
class SensorReading:
    """Represents a single point in time sensor reading."""
    timestamp: float  # seconds since epoch
    indoor_temp: float
    outdoor_temp: float
    indoor_humidity: Optional[float] = None
    outdoor_humidity: Optional[float] = None
    reference_temp: Optional[float] = None
    hvac_state: Optional[str] = "idle"


@dataclass
class ExtractedFeatures:
    """Extracted temporal and thermodynamic features from sensor history."""
    delta_1m: float = 0.0
    delta_5m: float = 0.0
    delta_10m: float = 0.0
    delta_20m: float = 0.0
    temp_rate: float = 0.0          # °C / hour
    temp_accel: float = 0.0         # °C / hour^2
    temp_diff: float = 0.0          # Indoor - Outdoor
    outdoor_rate: float = 0.0       # Outdoor °C / hour
    thermal_residual: float = 0.0   # Difference from learned baseline
    indoor_abs_humidity: Optional[float] = None
    outdoor_abs_humidity: Optional[float] = None
    humidity_delta_5m: float = 0.0
    dew_point: Optional[float] = None
    ref_room_diff_rate: float = 0.0
    has_ref_sensor: bool = False
    hvac_state: str = "idle"
    sample_count: int = 0


class FeatureExtractor:
    """Maintains a rolling window buffer of sensor readings and extracts features."""

    def __init__(self, max_history_minutes: int = 45):
        self.max_history_seconds = max_history_minutes * 60
        self.history: List[SensorReading] = []

    def add_reading(self, reading: SensorReading) -> None:
        """Appends a new reading and evicts readings older than max_history."""
        self.history.append(reading)
        cutoff = reading.timestamp - self.max_history_seconds
        self.history = [r for r in self.history if r.timestamp >= cutoff]

    def _get_past_reading(self, target_seconds_ago: float) -> Optional[SensorReading]:
        """Finds the reading closest to target_seconds_ago."""
        if not self.history:
            return None
        latest = self.history[-1]
        target_time = latest.timestamp - target_seconds_ago

        closest = None
        min_diff = float("inf")
        for r in self.history:
            diff = abs(r.timestamp - target_time)
            if diff < min_diff:
                min_diff = diff
                closest = r

        # Allow max tolerance of 3 minutes
        if min_diff <= 180:
            return closest
        return None

    def extract(self, baseline_expected_temp: float) -> ExtractedFeatures:
        """Extracts features relative to current state and baseline model."""
        if not self.history:
            return ExtractedFeatures()

        latest = self.history[-1]
        features = ExtractedFeatures()
        features.sample_count = len(self.history)
        features.temp_diff = latest.indoor_temp - latest.outdoor_temp
        features.thermal_residual = latest.indoor_temp - baseline_expected_temp
        features.hvac_state = latest.hvac_state or "idle"

        # Psychrometrics
        if latest.indoor_humidity is not None:
            features.indoor_abs_humidity = calc_absolute_humidity(
                latest.indoor_temp, latest.indoor_humidity
            )
            features.dew_point = calc_dew_point(latest.indoor_temp, latest.indoor_humidity)

        if latest.outdoor_humidity is not None:
            features.outdoor_abs_humidity = calc_absolute_humidity(
                latest.outdoor_temp, latest.outdoor_humidity
            )

        # Rolling deltas (1m, 5m, 10m, 20m)
        r_1m = self._get_past_reading(60)
        r_5m = self._get_past_reading(300)
        r_10m = self._get_past_reading(600)
        r_20m = self._get_past_reading(1200)

        if r_1m:
            features.delta_1m = latest.indoor_temp - r_1m.indoor_temp
        if r_5m:
            features.delta_5m = latest.indoor_temp - r_5m.indoor_temp
            if features.indoor_abs_humidity is not None and r_5m.indoor_humidity is not None:
                past_ah = calc_absolute_humidity(r_5m.indoor_temp, r_5m.indoor_humidity)
                features.humidity_delta_5m = features.indoor_abs_humidity - past_ah
        if r_10m:
            features.delta_10m = latest.indoor_temp - r_10m.indoor_temp
        if r_20m:
            features.delta_20m = latest.indoor_temp - r_20m.indoor_temp

        # Temperature rate dT/dt in °C / hour (using 5-minute interval or latest span)
        if r_5m and (latest.timestamp - r_5m.timestamp) > 30:
            dt_hours = (latest.timestamp - r_5m.timestamp) / 3600.0
            features.temp_rate = (latest.indoor_temp - r_5m.indoor_temp) / dt_hours
            features.outdoor_rate = (latest.outdoor_temp - r_5m.outdoor_temp) / dt_hours

            # Temperature acceleration (d2T/dt2) comparing first 5m derivative with 5-10m derivative
            if r_10m and (r_5m.timestamp - r_10m.timestamp) > 30:
                past_dt_hours = (r_5m.timestamp - r_10m.timestamp) / 3600.0
                past_rate = (r_5m.indoor_temp - r_10m.indoor_temp) / past_dt_hours
                features.temp_accel = (features.temp_rate - past_rate) / dt_hours

        # Reference room rate divergence
        if (
            latest.reference_temp is not None
            and r_5m
            and r_5m.reference_temp is not None
            and (latest.timestamp - r_5m.timestamp) > 30
        ):
            features.has_ref_sensor = True
            dt_hours = (latest.timestamp - r_5m.timestamp) / 3600.0
            ref_rate = (latest.reference_temp - r_5m.reference_temp) / dt_hours
            features.ref_room_diff_rate = abs(features.temp_rate - ref_rate)

        return features
