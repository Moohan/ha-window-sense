"""Evidence fusion and explainability for Window Sense."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List
from .features import ExtractedFeatures


@dataclass
class EvidenceScore:
    """Breakdown of positive and negative evidence signals."""
    rapid_cooling_faster_than_expected: float = 0.0
    thermal_residual_departure: float = 0.0
    humidity_matches_outdoor: float = 0.0
    thermal_gradient_sustained: float = 0.0
    local_divergence_from_ref_room: float = 0.0
    change_point_triggered: float = 0.0
    sustained_open_anomaly: float = 0.0
    heating_turned_off_recently: float = 0.0
    outdoor_cannot_explain_cooling: float = 0.0
    multi_room_global_drop: float = 0.0
    internal_moisture_source: float = 0.0
    anomaly_too_brief: float = 0.0
    raw_score: float = 0.0
    negative_penalty: float = 0.0
    final_confidence: float = 0.0
    primary_reason: str = ""


class EvidenceScorer:
    """Weights and fuses physical signals, suppresses false positives, and generates reasoning."""

    @staticmethod
    def evaluate(
        features: ExtractedFeatures,
        change_point_active: bool,
        min_gradient: float = 2.0,
        is_currently_open: bool = False,
    ) -> EvidenceScore:
        ev = EvidenceScore()

        abs_temp_diff = abs(features.temp_diff)
        is_cooling = features.temp_rate < -0.3
        is_heating_from_outside = features.temp_rate > 0.3 and features.temp_diff < -2.0

        is_recovering_towards_baseline = (
            (features.thermal_residual < -0.2 and features.temp_rate > 0.1)
            or (features.thermal_residual > 0.2 and features.temp_rate < -0.1)
        )

        # --- Positive Evidence ---

        # 1. Rapid Thermal Drift Rate (towards outdoor air)
        if features.temp_diff > 1.0 and features.temp_rate < -0.3 and features.thermal_residual < 0.1:
            cooling_speed = abs(features.temp_rate)
            if cooling_speed > 2.5:
                ev.rapid_cooling_faster_than_expected = 1.0
            elif cooling_speed > 1.2:
                ev.rapid_cooling_faster_than_expected = 0.85
            elif cooling_speed > 0.6:
                ev.rapid_cooling_faster_than_expected = 0.60
            else:
                ev.rapid_cooling_faster_than_expected = 0.30
        elif features.temp_diff < -1.0 and features.temp_rate > 0.3 and features.thermal_residual > -0.1:
            heating_speed = features.temp_rate
            if heating_speed > 2.5:
                ev.rapid_cooling_faster_than_expected = 1.0
            elif heating_speed > 1.2:
                ev.rapid_cooling_faster_than_expected = 0.85
            elif heating_speed > 0.6:
                ev.rapid_cooling_faster_than_expected = 0.60
            else:
                ev.rapid_cooling_faster_than_expected = 0.30

        # 2. Thermal Residual Departure from learned baseline
        abs_residual = abs(features.thermal_residual)
        if not is_recovering_towards_baseline and abs_residual > 0.4:
            if abs(features.temp_rate) >= 0.3 or change_point_active or is_currently_open:
                ev.thermal_residual_departure = min(1.0, (abs_residual - 0.2) / 1.5)

        # 3. Sustained Thermal Gradient to outside air
        if abs_temp_diff >= min_gradient:
            ev.thermal_gradient_sustained = min(1.0, (abs_temp_diff - 1.0) / 6.0)
        else:
            ev.thermal_gradient_sustained = max(0.1, abs_temp_diff / min_gradient)

        # 4. Change Point Triggered
        if change_point_active:
            ev.change_point_triggered = 1.0

        # 5. Sustained open anomaly (when window is open, large residual confirms continued open state)
        if is_currently_open and not is_recovering_towards_baseline and abs_residual > 1.5 and abs_temp_diff > 2.0:
            ev.sustained_open_anomaly = min(1.0, abs_residual / 3.0)

        # 6. Psychrometric Outdoor Humidity Coupling
        if features.indoor_abs_humidity is not None and features.outdoor_abs_humidity is not None:
            if abs(features.temp_rate) >= 0.3 or change_point_active or is_currently_open:
                ah_diff = features.indoor_abs_humidity - features.outdoor_abs_humidity
                if abs(ah_diff) < 1.2:
                    ev.humidity_matches_outdoor = 0.9
                elif features.humidity_delta_5m < -0.3 and features.indoor_abs_humidity > features.outdoor_abs_humidity:
                    ev.humidity_matches_outdoor = 0.8
                elif features.humidity_delta_5m > 0.3 and features.indoor_abs_humidity < features.outdoor_abs_humidity:
                    ev.humidity_matches_outdoor = 0.8

        # 7. Local Divergence from Reference Room
        if features.has_ref_sensor:
            if features.ref_room_diff_rate > 0.8:
                ev.local_divergence_from_ref_room = 1.0
            elif features.ref_room_diff_rate > 0.4:
                ev.local_divergence_from_ref_room = 0.65

        # --- Negative Evidence (False Positive Suppression) ---

        if is_cooling and features.outdoor_rate > 1.0 and features.temp_diff < 0.5:
            ev.outdoor_cannot_explain_cooling = 0.8

        if features.humidity_delta_5m > 1.5 and features.temp_rate > -0.2:
            ev.internal_moisture_source = 0.95

        if (
            features.hvac_state == "idle"
            and -1.2 < features.temp_rate < -0.2
            and features.temp_accel > 0.0
            and not features.has_ref_sensor
        ):
            ev.heating_turned_off_recently = 0.45

        # --- Dynamic Available Channel Weighting ---
        pos_score = 0.0
        total_weight = 0.0

        # Rate evidence
        effective_rate_score = max(ev.rapid_cooling_faster_than_expected, ev.sustained_open_anomaly * 0.90)
        pos_score += effective_rate_score * 0.30
        total_weight += 0.30

        # Residual evidence
        pos_score += ev.thermal_residual_departure * 0.35
        total_weight += 0.35

        # Change-point evidence
        effective_cp = max(ev.change_point_triggered, ev.sustained_open_anomaly * 0.80)
        pos_score += effective_cp * 0.15
        total_weight += 0.15

        # Humidity evidence (only if channel present)
        if features.indoor_abs_humidity is not None and features.outdoor_abs_humidity is not None:
            pos_score += ev.humidity_matches_outdoor * 0.15
            total_weight += 0.15

        # Reference sensor evidence (only if channel present)
        if features.has_ref_sensor:
            pos_score += ev.local_divergence_from_ref_room * 0.10
            total_weight += 0.10

        raw_pos = pos_score / max(0.1, total_weight)

        gradient_multiplier = (
            0.35 if ev.thermal_gradient_sustained < 0.2
            else min(1.0, ev.thermal_gradient_sustained + 0.3)
        )
        gated_pos = raw_pos * gradient_multiplier

        neg_penalty = max(
            ev.heating_turned_off_recently * 0.7,
            ev.outdoor_cannot_explain_cooling * 1.0,
            ev.multi_room_global_drop * 0.8,
            ev.internal_moisture_source * 0.95,
        )

        final_conf = max(0.0, min(1.0, gated_pos - neg_penalty))

        ev.raw_score = round(raw_pos, 3)
        ev.negative_penalty = round(neg_penalty, 3)
        ev.final_confidence = round(final_conf, 3)

        if final_conf >= 0.80 or (is_currently_open and final_conf >= 0.60):
            ev.primary_reason = (
                f"Rapid thermal departure ({features.temp_rate:.1f}°C/h, residual "
                f"{features.thermal_residual:+.1f}°C) driven by Δ{abs_temp_diff:.1f}°C outdoor gradient."
            )
            if ev.humidity_matches_outdoor > 0.5:
                ev.primary_reason += " Absolute humidity confirms outdoor air exchange."
        elif neg_penalty > 0.4:
            if ev.internal_moisture_source > 0.5:
                ev.primary_reason = "Humidity spike without cooling indicates internal moisture source (e.g. shower)."
            elif ev.heating_turned_off_recently > 0.4:
                ev.primary_reason = "Cooling deceleration matches normal radiator thermal decay."
            else:
                ev.primary_reason = "Environmental telemetry contradicts open window dynamics."
        else:
            ev.primary_reason = f"Thermal equilibrium aligned with baseline (residual {features.thermal_residual:+.2f}°C)."

        return ev
