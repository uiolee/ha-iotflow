"""Config flow for the IoTfLoW integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_TIMEOUT, CONF_URL, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    IoTfLoWApi,
    IoTfLoWApiError,
    IoTfLoWError,
    IoTfLoWInvalidCardError,
    api_for_entry,
    endpoint_path,
    normalize_base_url,
    normalize_card,
    normalize_endpoint,
)
from .const import (
    CONF_CARD,
    CONF_ENDPOINT,
    CONF_RETRIES,
    CONF_RETRY_INTERVAL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_ENDPOINT,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENDPOINTS,
    SECTION_ADVANCED,
)
from .preview import async_register_preview

ENDPOINT_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=endpoint, label=endpoint_path(endpoint))
            for endpoint in ENDPOINTS
        ],
        mode=selector.SelectSelectorMode.LIST,
    )
)

TIMEOUT_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=5,
        max=60,
        step=1,
        unit_of_measurement=UnitOfTime.SECONDS,
        mode=selector.NumberSelectorMode.BOX,
    )
)

RETRIES_SELECTOR = probatio.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=15, mode=selector.NumberSelectorMode.BOX
        )
    ),
    probatio.Coerce(int),
)

RETRY_INTERVAL_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=5,
        max=60,
        step=1,
        unit_of_measurement=UnitOfTime.SECONDS,
        mode=selector.NumberSelectorMode.BOX,
    )
)

UPDATE_INTERVAL_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=5,
        max=1440,
        step=1,
        unit_of_measurement=UnitOfTime.MINUTES,
        mode=selector.NumberSelectorMode.BOX,
    )
)

UPDATE_INTERVAL_FIELD = {
    probatio.Optional(
        CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
    ): UPDATE_INTERVAL_SELECTOR,
}

ADVANCED_FIELDS = {
    probatio.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): TIMEOUT_SELECTOR,
    probatio.Optional(CONF_RETRIES, default=DEFAULT_RETRIES): RETRIES_SELECTOR,
    probatio.Optional(
        CONF_RETRY_INTERVAL, default=DEFAULT_RETRY_INTERVAL
    ): RETRY_INTERVAL_SELECTOR,
}

USER_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_URL, default=DEFAULT_BASE_URL): str,
        probatio.Required(CONF_CARD): str,
        probatio.Required(CONF_ENDPOINT, default=DEFAULT_ENDPOINT): ENDPOINT_SELECTOR,
        **UPDATE_INTERVAL_FIELD,
        probatio.Optional(SECTION_ADVANCED): section(
            probatio.Schema(ADVANCED_FIELDS), SectionConfig(collapsed=True)
        ),
    }
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        **UPDATE_INTERVAL_FIELD,
        probatio.Optional(SECTION_ADVANCED): section(
            probatio.Schema(ADVANCED_FIELDS), SectionConfig(collapsed=True)
        ),
    }
)

REAUTH_SCHEMA = probatio.Schema({probatio.Required(CONF_CARD): str})


def _settings(user_input: dict[str, Any]) -> dict[str, Any]:
    """Extract the settings from an user input."""
    advanced: dict[str, Any] = user_input.get(SECTION_ADVANCED) or {}
    return {
        CONF_TIMEOUT: advanced.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        CONF_RETRIES: advanced.get(CONF_RETRIES, DEFAULT_RETRIES),
        CONF_RETRY_INTERVAL: advanced.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL),
        CONF_UPDATE_INTERVAL: user_input.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        ),
    }


async def _async_validate(api: IoTfLoWApi) -> tuple[dict[str, str], dict[str, str]]:
    """Query the service and return the errors of a failing query, if any."""
    errors: dict[str, str] = {}
    description_placeholders: dict[str, str] = {}
    try:
        await api.async_get_flow_data()
    except IoTfLoWInvalidCardError:
        errors["base"] = "invalid_card"
    except IoTfLoWApiError as err:
        errors["base"] = "api_error"
        description_placeholders["error"] = err.message
    except IoTfLoWError as err:
        errors["base"] = "cannot_connect"
        description_placeholders["error"] = str(err)
    return errors, description_placeholders


class IoTfLoWConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IoTfLoW."""

    VERSION = 2

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> IoTfLoWOptionsFlow:
        """Return the options flow."""
        return IoTfLoWOptionsFlow()

    @staticmethod
    @override
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up the preview of the assembled request URL."""
        async_register_preview(hass)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        card = normalize_card((user_input or {}).get(CONF_CARD))
        base_url = normalize_base_url((user_input or {}).get(CONF_URL))
        endpoint = normalize_endpoint((user_input or {}).get(CONF_ENDPOINT))
        if user_input is not None:
            self._async_abort_entries_match({CONF_CARD: card, CONF_ENDPOINT: endpoint})

            options = _settings(user_input)
            api = IoTfLoWApi(
                session=async_get_clientsession(self.hass),
                base_url=base_url,
                card=card,
                endpoint=endpoint,
                timeout=options[CONF_TIMEOUT],
                retries=options[CONF_RETRIES],
                retry_interval=options[CONF_RETRY_INTERVAL],
            )
            errors, description_placeholders = await _async_validate(api)
            if not errors:
                return self.async_create_entry(
                    title=f"{card}",
                    data={
                        CONF_URL: base_url,
                        CONF_CARD: card,
                        CONF_ENDPOINT: endpoint,
                    },
                    options=options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
            preview=DOMAIN,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a card number that the service stopped accepting."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a new card number for an already configured entry."""
        entry = self._get_reauth_entry()
        endpoint = normalize_endpoint(entry.data.get(CONF_ENDPOINT))
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        card = normalize_card((user_input or entry.data).get(CONF_CARD))
        if user_input is not None:
            self._async_abort_entries_match({CONF_CARD: card, CONF_ENDPOINT: endpoint})

            errors, description_placeholders = await _async_validate(
                api_for_entry(self.hass, entry, card=card)
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_CARD: card}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, {CONF_CARD: card}
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )


class IoTfLoWOptionsFlow(OptionsFlowWithReload):
    """Handle the request settings of an IoTfLoW config entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the request settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=_settings(user_input))

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    CONF_UPDATE_INTERVAL: options.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                    SECTION_ADVANCED: options,
                },
            ),
        )
