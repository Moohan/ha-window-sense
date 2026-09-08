"""Diagnostics support for WindowSense."""
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WindowSenseCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Returns diagnostics for a config entry."""
    coordinator: WindowSenseCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    diagnostics: Dict[str, Any] = {
        "entry_data": dict(entry.data),
        "entry_options": dict(entry.options),
        "engine_settings": {
            "open_threshold": coordinator.engine.open_threshold,
            "close_threshold": coordinator.engine.close_threshold,
            "open_persistence_min": coordinator.engine.open_persistence_min,
            "close_persistence_min": coordinator.engine.close_persistence_min,
            "baseline_expected": round(coordinator.engine.baseline_model.expected_temp, 2),
            "baseline_frozen": coordinator.engine.baseline_model.is_frozen,
            "learned_conductance": round(coordinator.engine.baseline_model.learned_conductance, 4),
            "in_recovery_quarantine": coordinator.engine.baseline_model.in_recovery_quarantine,
        },
    }

    if data:
        diagnostics["current_state"] = {
            "is_open": data.is_open,
            "confidence": data.confidence,
            "detection_quality": data.detection_quality,
            "baseline_learning": {
                "status": data.baseline_trust.status,
                "confidence_band": data.baseline_trust.confidence_band,
                "trust_factor": round(data.baseline_trust.trust_factor, 2),
                "effective_learning_rate": round(data.baseline_trust.effective_learning_rate, 5),
                "is_trusted": data.baseline_trust.is_trusted,
                "learning_allowed": data.baseline_trust.learning_allowed,
                "reason": data.baseline_trust.reason,
                "freeze_reasons": data.baseline_trust.freeze_reasons,
            },
            "thermal_residual": data.thermal_residual,
            "temperature_rate": data.temperature_rate,
            "temperature_diff": data.temperature_diff,
            "open_persistence_counter": data.open_persistence_counter,
            "close_persistence_counter": data.close_persistence_counter,
            "primary_reason": data.primary_reason,
            "evidence": {
                "raw_score": data.evidence.raw_score,
                "negative_penalty": data.evidence.negative_penalty,
                "rapid_cooling": data.evidence.rapid_cooling_faster_than_expected,
                "humidity_match": data.evidence.humidity_matches_outdoor,
                "gradient_sustained": data.evidence.thermal_gradient_sustained,
                "ref_divergence": data.evidence.local_divergence_from_ref_room,
                "change_point": data.evidence.change_point_triggered,
                "heating_off_recent": data.evidence.heating_turned_off_recently,
                "outdoor_unphysical": data.evidence.outdoor_cannot_explain_cooling,
                "global_drop": data.evidence.multi_room_global_drop,
                "internal_moisture": data.evidence.internal_moisture_source,
            },
            "features": {
                "delta_1m": data.features.delta_1m,
                "delta_5m": data.features.delta_5m,
                "delta_10m": data.features.delta_10m,
                "delta_20m": data.features.delta_20m,
                "temp_accel": data.features.temp_accel,
                "indoor_abs_humidity": data.features.indoor_abs_humidity,
                "dew_point": data.features.dew_point,
                "sample_count": data.features.sample_count,
            },
        }

    return diagnostics
