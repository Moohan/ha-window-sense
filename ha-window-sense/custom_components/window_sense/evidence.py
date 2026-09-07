"""Evidence fusion and explainability for WindowSense."""
from dataclasses import dataclass
from typing import Dict, Any, List
from .features import ExtractedFeatures


@dataclass
class EvidenceScore:
    """Breakdown of positive and negative evidence signals."""
    rapid_cooling_faster_than_expected: float = 0.0
    humidity_matches_outdoor: float = 0.0
    thermal_gradient_sustained: float = 0.0
    local_divergence_from_ref_room: float = 0.0
    change_point_triggered: float = 0.0
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
    ) -> EvidenceScore:
        ev = EvidenceScore()

        abs_temp_diff = abs(features.temp_diff)
        is_cooling = features.temp_rate < -0.3
        is_heating_from_outside = features.temp_rate > 0.3 and features.temp_diff < -2.0

        # --- Positive Evidence ---

        # 1. Rapid Thermal Drift Rate (towards outdoor air)
        # In cold weather (outdoor < indoor), window open causes cooling (temp_rate < 0)
        # In hot weather (outdoor > indoor), window open causes heating (temp_rate > 0)
        if features.temp_diff > 1.0 and features.temp_rate < -0.3 and features.thermal_residual < 0.1:
            cooling_speed = abs(features.temp_rate)
            if cooling_speed > 2.5:
                ev.rapid_cooling_faster_than_expected = 1.0
            elif cooling_speed > 1.2:
                ev.rapid_cooling_faster_than_expected = 0.75
            elif cooling_speed > 0.6:
                ev.rapid_cooling_faster_than_expected = 0.45
        elif features.temp_diff < -1.0 and features.temp_rate > 0.3 and features.thermal_residual > -0.1:
            heating_speed = features.temp_rate
            if heating_speed > 2.5:
                ev.rapid_cooling_faster_than_expected = 1.0
            elif heating_speed > 1.2:
                ev.rapid_cooling_faster_than_expected = 0.75
            elif heating_speed > 0.6:
                ev.rapid_cooling_faster_than_expected = 0.45
        else:
            ev.rapid_cooling_faster_than_expected = 0.0

        # 2. Sustained Thermal Gradient driving force
        if abs_temp_diff >= min_gradient:
            ev.thermal_gradient_sustained = min(1.0, abs_temp_diff / 8.0)
        else:
            ev.thermal_gradient_sustained = 0.1

        # 3. Moisture Infiltration towards outdoor absolute humidity (weight ~ 15%)
        if (
            features.indoor_abs_humidity is not None
            and features.outdoor_abs_humidity is not None
        ):
            indoor_ah = features.indoor_abs_humidity
            outdoor_ah = features.outdoor_abs_humidity
            ah_diff = abs(indoor_ah - outdoor_ah)

            # If outdoor is drier and indoor is drying towards outdoor
            if outdoor_ah < indoor_ah and features.humidity_delta_5m < -0.2 and ah_diff < 4.0:
                ev.humidity_matches_outdoor = min(1.0, abs(features.humidity_delta_5m) / 1.0)
            elif outdoor_ah > indoor_ah and features.humidity_delta_5m > 0.2:
                ev.humidity_matches_outdoor = min(1.0, features.humidity_delta_5m / 1.0)
            elif ah_diff < 1.0:
                ev.humidity_matches_outdoor = 0.3

        # 4. Local Divergence from Reference Room (weight ~ 10%)
        if features.ref_room_diff_rate > 0.8:
            ev.local_divergence_from_ref_room = min(1.0, features.ref_room_diff_rate / 2.5)

        # 5. Change-Point CUSUM Inflection (weight ~ 15%)
        if change_point_active:
            ev.change_point_triggered = 0.9

        # Thermal residual factor (weight ~ 35%)
        # Residual must pull temperature toward outdoor temperature
        res_factor = 0.0
        if features.temp_diff > 1.0 and features.thermal_residual < -0.3:
            res_factor = min(1.0, abs(features.thermal_residual) / 1.6)
        elif features.temp_diff < -1.0 and features.thermal_residual > 0.3:
            res_factor = min(1.0, features.thermal_residual / 1.6)

        # Calculate Raw Positive Score
        ev.raw_score = (
            ev.rapid_cooling_faster_than_expected * 0.25
            + res_factor * 0.35
            + ev.thermal_gradient_sustained * 0.15
            + ev.humidity_matches_outdoor * 0.15
            + ev.local_divergence_from_ref_room * 0.10
        )

        if change_point_active and ev.raw_score > 0.25:
            ev.raw_score = min(1.0, ev.raw_score * 1.3)

        # --- Negative Evidence / False Positive Suppression ---

        # Negative 1: Heating cycled off recently (thermostat setback)
        if features.hvac_state == "off_recent" or (
            features.hvac_state == "idle" and -1.0 < features.temp_rate < -0.1
        ):
            # If cooling is mild and no humidity shift, likely heating setback
            if ev.rapid_cooling_faster_than_expected < 0.6 and ev.humidity_matches_outdoor < 0.2:
                ev.heating_turned_off_recently = 0.70

        # Negative 2: Outdoor cannot physically explain cooling
        # (e.g. outdoor is 26°C, indoor is 21°C and dropping - must be AC or internal sensor fault)
        if features.temp_diff < -1.0 and features.temp_rate < -0.3:
            ev.outdoor_cannot_explain_cooling = 0.85

        # Negative 3: Global house-wide drop (reference room cooling at exact same rate)
        # ONLY evaluated if a reference room sensor is actually configured
        if features.has_ref_sensor and features.ref_room_diff_rate < 0.25 and abs(features.temp_rate) > 0.8:
            ev.multi_room_global_drop = 0.60

        # Negative 4: Internal moisture source (e.g. shower steam or cooking)
        # Humidity spiked upwards drastically while room temperature did NOT drop
        if features.humidity_delta_5m > 0.6 and features.temp_rate >= -0.2:
            ev.internal_moisture_source = 0.85
        elif features.thermal_residual > 0.4 and features.humidity_delta_5m > 0.3:
            # Room is warmer than baseline with humidity spike
            ev.internal_moisture_source = 0.80

        # Negative 5: Transient spike / insufficient history
        if features.sample_count < 3:
            ev.anomaly_too_brief = 0.75

        # Aggregate penalty
        ev.negative_penalty = max(
            ev.heating_turned_off_recently,
            ev.outdoor_cannot_explain_cooling,
            ev.multi_room_global_drop,
            ev.internal_moisture_source,
            ev.anomaly_too_brief,
        )

        ev.final_confidence = max(0.0, min(1.0, ev.raw_score * (1.0 - ev.negative_penalty)))

        # Primary Explanation Generation
        ev.primary_reason = EvidenceScorer._generate_reason(ev, features)
        return ev

    @staticmethod
    def _generate_reason(ev: EvidenceScore, features: ExtractedFeatures) -> str:
        if ev.final_confidence >= 0.80:
            if ev.humidity_matches_outdoor > 0.4:
                return (
                    f"Strong outdoor ventilation: rapid thermal drift ({features.temp_rate:.1f}°C/h) "
                    f"and absolute humidity shift towards ambient."
                )
            return (
                f"Sustained thermal anomaly: temperature diverging at {features.temp_rate:.1f}°C/h "
                f"under Δ{features.temp_diff:.1f}°C gradient."
            )
        elif ev.final_confidence >= 0.50:
            return (
                f"Moderate cooling detected ({features.temp_rate:.1f}°C/h); "
                f"monitoring persistence window for confirmation."
            )
        elif ev.negative_penalty >= 0.5:
            if ev.internal_moisture_source > 0.5:
                return "Internal moisture spike (shower/cooking) detected; window open ruled out."
            if ev.outdoor_cannot_explain_cooling > 0.5:
                return "Outdoor temperature cannot explain temperature change (likely A/C or sensor drift)."
            if ev.heating_turned_off_recently > 0.5:
                return "Cooling rate matches normal structural thermal inertia following HVAC cycle-off."
            if ev.multi_room_global_drop > 0.5:
                return "Global multi-room thermostat setback detected; local window open rejected."
            return "Suppressed by negative evidence filter."
        else:
            return "Room in normal thermal equilibrium with expected building envelope drift."
