"""Diagnostics support for the IoTfLoW integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_CARD
from .coordinator import IoTfLoWConfigEntry

# The flow query service returns personal data of the SIM card.
TO_REDACT = {CONF_CARD, "meCardNum", "iccId", "upCardNum"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IoTfLoWConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": coordinator.last_update_success_time,
            "last_error": coordinator.last_error,
            "data": async_redact_data(coordinator.data, TO_REDACT),
        },
    }
