"""Psychrometric calculations and rolling feature extraction for Window Sense."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


def calc_saturation_vapor_pressure(temp_c: Optional[float]) -> float:
    """Calculates saturation vapor pressure in hPa using Magnus-Tetens formula."""
    if temp_c is None or math.isnan(temp_c) or math.isinf(temp_c):
        return 0.0
    return 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))


def calc_actual_vapor_pressure(temp_c: Optional[float], rh_percent: Optional[float]) -> float:
    """Calculates actual vapor pressure in hPa from temperature and relative humidity."""
    if (
        temp_c is None
        or rh_percent is None
        or math.isnan(temp_c)
        or math.isinf(temp_c)
        or math.isnan(rh_percent)
        or math.isinf(rh_percent)
    ):
        return 0.0
    clamped_rh = max(0.0, min(100.0, rh_percent))
    return (clamped_rh / 100.0) * calc_saturation_vapor_pressure(temp_c)


def calc_absolute_humidity(temp_c: Optional[float], rh_percent: Optional[float]) -> float:
    """Calculates absolute humidity in g/m3."""
    if (
        temp_c is None
        or rh_percent is None
        or math.isnan(temp_c)
        or math.isinf(temp_c)
        or math.isnan(rh_percent)
        or math.isinf(rh_percent)
    ):
        return 0.0
    act_vp = calc_actual_vapor_pressure(temp_c, rh_percent)
    temp_k = temp_c + 273.15
    if temp_k <= 0:
        return 0.0
    return (216.7 * act_vp) / temp_k


def calc_dew_point(temp_c: Optional[float], rh_percent: Optional[float]) -> float:
    """Calculates dew point temperature in °C."""
    if (
        temp_c is None
        or rh_percent is None
        or math.isnan(temp_c)
        or math.isinf(temp_c)
        or math.isnan(rh_percent)
        or math.isinf(rh_percent)
        or rh_percent <= 0
    ):
        return -50.0
    act_vp = calc_actual_vapor_pressure(temp_c, rh_percent)
    if act_vp <= 0.0:
        return -50.0
    ln_vp = math.log(act_vp / 6.112)
    denom = 17.67 - ln_vp
    if abs(denom) < 1e-6:
        return -50.0
    return (243.5 * ln_vp) / denom


@dataclass
class SensorReading:
    """Represents a single point in time sensor reading."""
    timestamp: float
    indoor_temp: Optional[float]
    outdoor_temp: Optional[float]
    indoor_humidity: Optional[float] = None
    outdoor_humidity: Optional[float] = None
    reference_temp: Optional[float] = None
    hvac_state: Optional[str] = "idle"
    indoor_temp_updated_at: Optional[float] = None
    outdoor_temp_updated_at: Optional[float] = None
    indoor_humidity_updated_at: Optional[float] = None
    outdoor_humidity_updated_at: Optional[float] = None


@dataclass
class ExtractedFeatures:
    """Extracted temporal and thermodynamic features from sensor history."""
    delta_1m: float = 0.0
    delta_5m: float = 0.0
    delta_10m: float = 0.0
    delta_20m: float = 0.0
    temp_rate: float = 0.0
    temp_accel: float = 0.0
    temp_diff: float = 0.0
    outdoor_rate: float = 0.0
    thermal_residual: float = 0.0
    indoor_abs_humidity: Optional[float] = None
    outdoor_abs_humidity: Optional[float] = None
    humidity_delta_5m: float = 0.0
    dew_point: Optional[float] = None
    ref_room_diff_rate: float = 0.0
    has_ref_sensor: bool = False
    has_humidity_sensor: bool = False
    hvac_state: str = "idle"
    sample_count: int = 0
    post_outage_suppressed: bool = False
    indoor_stale_sec: float = 0.0
    outdoor_stale_sec: float = 0.0


class FeatureExtractor:
    """Maintains a rolling window buffer of valid sensor readings and extracts features."""

    def __init__(self, max_history_minutes: int = 45, max_gap_seconds: float = 900.0):
        self.max_history_seconds = max_history_minutes * 60
        self.max_gap_seconds = max_gap_seconds
        self.history: List[SensorReading] = []
        self.last_reading_time: Optional[float] = None

    def add_reading(self, reading: SensorReading) -> None:
        if reading.timestamp is None or math.isnan(reading.timestamp) or math.isinf(reading.timestamp):
            return

        self.history.append(reading)
        cutoff = reading.timestamp - self.max_history_seconds
        self.history = [r for r in self.history if r.timestamp >= cutoff]

    def _get_past_reading(self, target_seconds_ago: float) -> Optional[SensorReading]:
        if not self.history:
            return None
        latest = self.history[-1]
        target_time = latest.timestamp - target_seconds_ago

        closest = None
        min_diff = float("inf")
        for r in self.history:
            if r.indoor_temp is None or math.isnan(r.indoor_temp):
                continue
            diff = abs(r.timestamp - target_time)
            if diff < min_diff:
                min_diff = diff
                closest = r

        if min_diff <= 180 and closest is not None:
            time_gap = latest.timestamp - closest.timestamp
            if time_gap <= (target_seconds_ago + 300.0):
                return closest
        return None

    def extract(self, baseline_expected_temp: float) -> ExtractedFeatures:
        if not self.history:
            return ExtractedFeatures()

        latest = self.history[-1]
        features = ExtractedFeatures()

        valid_samples = [
            r for r in self.history
            if r.indoor_temp is not None and not math.isnan(r.indoor_temp) and not math.isinf(r.indoor_temp)
        ]
        features.sample_count = len(valid_samples)

        if latest.indoor_temp is None or math.isnan(latest.indoor_temp) or math.isinf(latest.indoor_temp):
            self.last_reading_time = latest.timestamp
            return features

        if latest.outdoor_temp is not None and not math.isnan(latest.outdoor_temp) and not math.isinf(latest.outdoor_temp):
            features.temp_diff = latest.indoor_temp - latest.outdoor_temp

        features.thermal_residual = latest.indoor_temp - baseline_expected_temp
        features.hvac_state = latest.hvac_state or "idle"

        in_up = latest.indoor_temp_updated_at if latest.indoor_temp_updated_at is not None else latest.timestamp
        out_up = latest.outdoor_temp_updated_at if latest.outdoor_temp_updated_at is not None else latest.timestamp
        features.indoor_stale_sec = max(0.0, latest.timestamp - in_up)
        features.outdoor_stale_sec = max(0.0, latest.timestamp - out_up)

        if self.last_reading_time is not None:
            gap = latest.timestamp - self.last_reading_time
            if gap > self.max_gap_seconds:
                features.post_outage_suppressed = True
        elif len(self.history) >= 2:
            prev = self.history[-2]
            gap = latest.timestamp - prev.timestamp
            if gap > self.max_gap_seconds:
                features.post_outage_suppressed = True

        self.last_reading_time = latest.timestamp

        if latest.indoor_humidity is not None and not math.isnan(latest.indoor_humidity) and not math.isinf(latest.indoor_humidity):
            features.indoor_abs_humidity = calc_absolute_humidity(latest.indoor_temp, latest.indoor_humidity)
            features.dew_point = calc_dew_point(latest.indoor_temp, latest.indoor_humidity)

        if latest.outdoor_humidity is not None and not math.isnan(latest.outdoor_humidity) and not math.isinf(latest.outdoor_humidity):
            if latest.outdoor_temp is not None and not math.isnan(latest.outdoor_temp):
                features.outdoor_abs_humidity = calc_absolute_humidity(latest.outdoor_temp, latest.outdoor_humidity)

        features.has_humidity_sensor = (features.indoor_abs_humidity is not None and features.outdoor_abs_humidity is not None)

        if features.post_outage_suppressed:
            return features

        r_1m = self._get_past_reading(60)
        r_5m = self._get_past_reading(300)
        r_10m = self._get_past_reading(600)
        r_20m = self._get_past_reading(1200)

        if r_1m and r_1m.indoor_temp is not None:
            features.delta_1m = latest.indoor_temp - r_1m.indoor_temp
        if r_5m and r_5m.indoor_temp is not None:
            features.delta_5m = latest.indoor_temp - r_5m.indoor_temp
            if (
                features.indoor_abs_humidity is not None
                and r_5m.indoor_humidity is not None
                and not math.isnan(r_5m.indoor_humidity)
            ):
                past_ah = calc_absolute_humidity(r_5m.indoor_temp, r_5m.indoor_humidity)
                if past_ah is not None:
                    features.humidity_delta_5m = features.indoor_abs_humidity - past_ah

        if r_10m and r_10m.indoor_temp is not None:
            features.delta_10m = latest.indoor_temp - r_10m.indoor_temp
        if r_20m and r_20m.indoor_temp is not None:
            features.delta_20m = latest.indoor_temp - r_20m.indoor_temp

        if r_5m and r_5m.indoor_temp is not None:
            dt_sec = latest.timestamp - r_5m.timestamp
            if dt_sec >= 30:
                dt_hours = dt_sec / 3600.0
                features.temp_rate = (latest.indoor_temp - r_5m.indoor_temp) / dt_hours
                if latest.outdoor_temp is not None and r_5m.outdoor_temp is not None:
                    features.outdoor_rate = (latest.outdoor_temp - r_5m.outdoor_temp) / dt_hours

                if r_10m and r_10m.indoor_temp is not None:
                    past_dt_sec = r_5m.timestamp - r_10m.timestamp
                    if past_dt_sec >= 30:
                        past_dt_hours = past_dt_sec / 3600.0
                        past_rate = (r_5m.indoor_temp - r_10m.indoor_temp) / past_dt_hours
                        features.temp_accel = (features.temp_rate - past_rate) / dt_hours

        if (
            latest.reference_temp is not None
            and not math.isnan(latest.reference_temp)
            and r_5m
            and r_5m.reference_temp is not None
            and not math.isnan(r_5m.reference_temp)
        ):
            dt_sec = latest.timestamp - r_5m.timestamp
            if dt_sec >= 30:
                features.has_ref_sensor = True
                dt_hours = dt_sec / 3600.0
                ref_rate = (latest.reference_temp - r_5m.reference_temp) / dt_hours
                features.ref_room_diff_rate = abs(features.temp_rate - ref_rate)

        return features
