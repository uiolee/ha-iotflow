"""Config flow preview for the IoTfLoW integration."""

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .api import api_url
from .const import CONF_CARD, CONF_ENDPOINT, DOMAIN


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/start_preview",
        probatio.Required("flow_id"): str,
        probatio.Required("flow_type"): probatio.Any("config_flow", "options_flow"),
        probatio.Required("user_input"): dict,
    }
)
@callback
def ws_start_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the request URL assembled from the current form input."""
    if msg["flow_type"] == "config_flow":
        base_url = msg["user_input"].get(CONF_URL)
        card = msg["user_input"].get(CONF_CARD)
        endpoint = msg["user_input"].get(CONF_ENDPOINT)
    else:
        flow = hass.config_entries.options.async_get(msg["flow_id"])
        entry = hass.config_entries.async_get_entry(flow["handler"])
        if entry is None:
            raise HomeAssistantError("Config entry not found")
        base_url = entry.data[CONF_URL]
        card = entry.data[CONF_CARD]
        endpoint = entry.data.get(CONF_ENDPOINT)

    connection.send_result(msg["id"])
    connection.send_event(
        msg["id"],
        {
            "domain": "sensor",
            "state": api_url(base_url, endpoint, card),
            "attributes": {"friendly_name": "Request URL"},
        },
    )
    connection.subscriptions[msg["id"]] = lambda: None


def async_register_preview(hass: HomeAssistant) -> None:
    """Register the preview websocket command."""
    websocket_api.async_register_command(hass, ws_start_preview)
