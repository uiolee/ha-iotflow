"""DataUpdateCoordinator for the IoTfLoW integration."""

from datetime import timedelta
from typing import Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    IoTfLoWApi,
    IoTfLoWApiError,
    IoTfLoWError,
    IoTfLoWInvalidCardError,
)
from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ISSUE_API_ERROR,
    LOGGER,
)

type IoTfLoWConfigEntry = ConfigEntry[IoTfLoWDataUpdateCoordinator]


class IoTfLoWDataUpdateCoordinator(TimestampDataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching flow data for a single card."""

    config_entry: IoTfLoWConfigEntry
    last_error: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: IoTfLoWConfigEntry,
        api: IoTfLoWApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=config_entry.options.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                )
            ),
        )
        self.api = api

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest flow data from the service."""
        try:
            data = await self.api.async_get_flow_data()
        except IoTfLoWInvalidCardError as err:
            # Only the user can provide a card number the service accepts.
            self._async_report_error(None)
            raise ConfigEntryAuthFailed(str(err)) from err
        except IoTfLoWApiError as err:
            self._async_report_error(err.message)
            raise UpdateFailed(str(err)) from err
        except IoTfLoWError as err:
            raise UpdateFailed(str(err)) from err

        self._async_report_error(None)
        return data

    @callback
    def _async_report_error(self, error: str | None) -> None:
        """Report a failing flow query to the user, or clear the report."""
        self.last_error = error
        issue_id = f"{ISSUE_API_ERROR}_{self.config_entry.entry_id}"
        if error is None:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_API_ERROR,
            translation_placeholders={"card": self.api.card, "error": error},
        )
