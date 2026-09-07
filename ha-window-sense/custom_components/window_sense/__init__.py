"""Window Sense custom integration."""
import logging

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant
    from .coordinator import WindowSenseCoordinator

    PLATFORMS: list[Platform] = [
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ]
except ImportError:
    # Allows standalone running of testbed and unit tests without full HA core installed
    ConfigEntry = object  # type: ignore
    HomeAssistant = object  # type: ignore
    PLATFORMS = []  # type: ignore
    WindowSenseCoordinator = None  # type: ignore

from .const import DOMAIN


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
