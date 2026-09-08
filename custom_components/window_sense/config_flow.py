"""Config flow for WindowSense integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    CONF_INDOOR_HUMIDITY,
    CONF_OUTDOOR_HUMIDITY,
    CONF_REFERENCE_TEMP,
    CONF_HVAC,
    CONF_OPEN_THRESHOLD,
    CONF_CLOSE_THRESHOLD,
    CONF_OPEN_PERSISTENCE,
    CONF_CLOSE_PERSISTENCE,
    CONF_BASELINE_LEARNING_RATE,
    CONF_CHANGE_POINT_SENSITIVITY,
    DEFAULT_OPEN_THRESHOLD,
    DEFAULT_CLOSE_THRESHOLD,
    DEFAULT_OPEN_PERSISTENCE,
    DEFAULT_CLOSE_PERSISTENCE,
    DEFAULT_BASELINE_LEARNING_RATE,
    DEFAULT_CHANGE_POINT_SENSITIVITY,
)

_LOGGER = logging.getLogger(__name__)


class WindowSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles UI configuration for WindowSense."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: Select room sensors."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            title = user_input.get(CONF_INDOOR_TEMP, "").split(".")[-1].replace("_temperature", "").title()
            title = f"{title} Window Sense"
            return self.async_create_entry(title=title, data=user_input)

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

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return WindowSenseOptionsFlowHandler(config_entry)


class WindowSenseOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options and parameter tuning flow for an existing WindowSense entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        data = self.config_entry.data

        schema = vol.Schema({
            vol.Optional(
                CONF_OPEN_THRESHOLD,
                default=opts.get(CONF_OPEN_THRESHOLD, data.get(CONF_OPEN_THRESHOLD, DEFAULT_OPEN_THRESHOLD)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.50, max=0.95, step=0.05, mode="slider")
            ),
            vol.Optional(
                CONF_OPEN_PERSISTENCE,
                default=opts.get(CONF_OPEN_PERSISTENCE, data.get(CONF_OPEN_PERSISTENCE, DEFAULT_OPEN_PERSISTENCE)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, step=1, mode="slider")
            ),
            vol.Optional(
                CONF_CLOSE_THRESHOLD,
                default=opts.get(CONF_CLOSE_THRESHOLD, data.get(CONF_CLOSE_THRESHOLD, DEFAULT_CLOSE_THRESHOLD)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.10, max=0.45, step=0.05, mode="slider")
            ),
            vol.Optional(
                CONF_CLOSE_PERSISTENCE,
                default=opts.get(CONF_CLOSE_PERSISTENCE, data.get(CONF_CLOSE_PERSISTENCE, DEFAULT_CLOSE_PERSISTENCE)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=3, max=20, step=1, mode="slider")
            ),
            vol.Optional(
                CONF_BASELINE_LEARNING_RATE,
                default=opts.get(CONF_BASELINE_LEARNING_RATE, data.get(CONF_BASELINE_LEARNING_RATE, DEFAULT_BASELINE_LEARNING_RATE)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.01, max=0.15, step=0.01, mode="slider")
            ),
            vol.Optional(
                CONF_CHANGE_POINT_SENSITIVITY,
                default=opts.get(CONF_CHANGE_POINT_SENSITIVITY, data.get(CONF_CHANGE_POINT_SENSITIVITY, DEFAULT_CHANGE_POINT_SENSITIVITY)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.6, max=2.0, step=0.1, mode="slider")
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
