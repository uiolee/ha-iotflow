"""API client for the IoTfLoW integration."""

import asyncio
from typing import Any
from urllib.parse import quote

import aiohttp
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TIMEOUT, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CARD,
    CONF_ENDPOINT,
    CONF_RETRIES,
    CONF_RETRY_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_ENDPOINT,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_TIMEOUT,
    ENDPOINTS,
    FLOW_KEYS,
    LOGGER,
)

SIM_CARD_PATH = "/app/simCard"

# The service reports a permanently unusable card number with the same status
# code as a temporarily unavailable backend, so the message tells them apart.
INVALID_CARD_MARKERS = ("不存在", "码号信息错误")


def successful_data(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the data of a successful response, if it holds the sensor values."""
    if payload.get("status") is not True or payload.get("code") != 0:
        return None
    data = payload.get("data")
    if not isinstance(data, dict) or not all(
        isinstance(data.get(key), int | float) for key in FLOW_KEYS
    ):
        return None
    return data


def error_message(payload: dict[str, Any]) -> str:
    """Return a description of an unsuccessful response."""
    if payload.get("status") is True and payload.get("code") == 0:
        return "The response does not contain any flow data"
    return str(payload.get("msg") or "Unknown error")


def normalize_base_url(value: str | None) -> str:
    """Return the API base URL without a trailing slash."""
    return str(value or "").strip().rstrip("/") or DEFAULT_BASE_URL


def normalize_card(value: str | None) -> str:
    """Return the SIM card number."""
    return str(value or "").strip()


def normalize_endpoint(value: str | None) -> str:
    """Return a supported API endpoint."""
    endpoint = str(value or "").strip()
    return endpoint if endpoint in ENDPOINTS else DEFAULT_ENDPOINT


def endpoint_path(endpoint: str | None) -> str:
    """Return the path of an API endpoint."""
    return f"{SIM_CARD_PATH}/{normalize_endpoint(endpoint)}"


def api_url(base_url: str | None, endpoint: str | None, card: str | None) -> str:
    """Return the URL of a flow query request."""
    url = f"{normalize_base_url(base_url)}{endpoint_path(endpoint)}"
    card = normalize_card(card)
    if not card:
        return url
    try:
        return str(URL(url).with_query(card=card))
    except ValueError:  # The user supplied an unparsable base URL
        return f"{url}?card={quote(card, safe='')}"


def device_configuration_url(
    base_url: str | None, endpoint: str | None, card: str | None
) -> str | None:
    """Return the request URL of the service when a browser can open it."""
    try:
        url = URL(api_url(base_url, endpoint, card))
    except ValueError:  # The user supplied an unparsable base URL
        return None
    return str(url) if url.scheme in {"http", "https"} and url.host else None


class IoTfLoWError(HomeAssistantError):
    """Base class for IoTfLoW errors."""


class IoTfLoWConnectionError(IoTfLoWError):
    """Raised when the service cannot be reached."""


class IoTfLoWApiError(IoTfLoWError):
    """Raised when the service returns an unsuccessful response."""

    def __init__(self, code: int | None, message: str) -> None:
        """Initialize the error."""
        super().__init__(f"API error {code}: {message}")
        self.code = code
        self.message = message


class IoTfLoWInvalidCardError(IoTfLoWApiError):
    """Raised when the card number is not known to the service."""


class IoTfLoWApi:
    """Client for the SIM card flow query service."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        card: str,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        retry_interval: float = DEFAULT_RETRY_INTERVAL,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = normalize_base_url(base_url)
        self._card = normalize_card(card)
        self._endpoint = normalize_endpoint(endpoint)
        self._timeout = timeout
        self._retries = max(retries, 1)
        self._retry_interval = retry_interval

    @property
    def card(self) -> str:
        """Return the queried SIM card number."""
        return self._card

    @property
    def request_url(self) -> str:
        """Return the URL used to query the flow data."""
        return api_url(self._base_url, self._endpoint, self._card)

    async def async_get_flow_data(self) -> dict[str, Any]:
        """Return the flow data for the configured card."""
        for attempt in range(1, self._retries + 1):
            last_attempt = attempt == self._retries
            try:
                payload = await self._async_request()
            except IoTfLoWConnectionError:
                if last_attempt:
                    raise
                reason = "the service could not be reached"
            else:
                data = successful_data(payload)
                if data is not None:
                    return data

                code = payload.get("code")
                message = error_message(payload)
                LOGGER.debug(
                    "Service responded with code=%s message=%s payload=%s",
                    code,
                    message,
                    payload,
                )

                # A rejected card number will not become valid on a retry.
                if any(marker in message for marker in INVALID_CARD_MARKERS):
                    raise IoTfLoWInvalidCardError(code, message)

                if last_attempt:
                    raise IoTfLoWApiError(code, message)

                reason = f"the service responded with code={code} message={message}"

            LOGGER.debug(
                "Attempt %s/%s failed because %s, retrying in %s seconds",
                attempt,
                self._retries,
                reason,
                self._retry_interval,
            )
            await asyncio.sleep(self._retry_interval)

        raise IoTfLoWApiError(None, "The service is temporarily unavailable")

    async def _async_request(self) -> dict[str, Any]:
        """Perform a single request against the service."""
        try:
            async with self._session.get(
                self.request_url,
                headers={"Referer": f"{self._base_url}/wap/index.html"},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except TimeoutError as err:
            raise IoTfLoWConnectionError(
                "Timeout while communicating with the service"
            ) from err
        except aiohttp.ClientError as err:
            raise IoTfLoWConnectionError(
                f"Error communicating with the service: {err}"
            ) from err
        except ValueError as err:
            raise IoTfLoWConnectionError(
                "Received an invalid response from the service"
            ) from err

        if not isinstance(payload, dict):
            raise IoTfLoWConnectionError(
                "Received an unexpected response from the service"
            )

        return payload


def api_for_entry(
    hass: HomeAssistant, entry: ConfigEntry, card: str | None = None
) -> IoTfLoWApi:
    """Return an API client configured by a config entry."""
    options = entry.options
    return IoTfLoWApi(
        session=async_get_clientsession(hass),
        base_url=entry.data.get(CONF_URL, DEFAULT_BASE_URL),
        card=normalize_card(card if card is not None else entry.data.get(CONF_CARD)),
        endpoint=entry.data.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
        timeout=options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        retries=options.get(CONF_RETRIES, DEFAULT_RETRIES),
        retry_interval=options.get(CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL),
    )
