"""The IoTfLoW integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import api_for_entry
from .coordinator import IoTfLoWConfigEntry, IoTfLoWDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IoTfLoWConfigEntry) -> bool:
    """Set up IoTfLoW from a config entry."""
    coordinator = IoTfLoWDataUpdateCoordinator(hass, entry, api_for_entry(hass, entry))

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IoTfLoWConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
