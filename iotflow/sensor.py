"""Support for IoTfLoW sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from yarl import URL

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_URL, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import device_configuration_url, endpoint_path, normalize_endpoint
from .const import (
    CONF_CARD,
    CONF_ENDPOINT,
    DEFAULT_ENDPOINT,
    DOMAIN,
    FLOW_EXPIRY,
    FLOW_REMAINING,
    FLOW_TOTAL,
    FLOW_USED,
    SERVICE_TIME_ZONE,
)
from .coordinator import IoTfLoWConfigEntry, IoTfLoWDataUpdateCoordinator


def _parse_expiry(value: Any) -> datetime | None:
    """Parse the expiry timestamp returned by the service."""
    if not isinstance(value, str):
        return None
    try:
        parsed = dt_util.parse_datetime(value)
    except ValueError:  # Well formatted, but not a valid datetime
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SERVICE_TIME_ZONE)
    return dt_util.as_local(parsed)


def _base_url_host(base_url: str) -> str:
    """Return the host of the configured API base URL."""
    try:
        return URL(base_url).host or base_url
    except ValueError:  # The user supplied an unparsable base URL
        return base_url


@dataclass(frozen=True, kw_only=True)
class IoTfLoWSensorEntityDescription(SensorEntityDescription):
    """Describes an IoTfLoW sensor entity."""

    value_fn: Callable[[IoTfLoWDataUpdateCoordinator], StateType | datetime]


SENSORS: tuple[IoTfLoWSensorEntityDescription, ...] = (
    IoTfLoWSensorEntityDescription(
        key="total_flow",
        translation_key="total_flow",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.data.get(FLOW_TOTAL),
    ),
    IoTfLoWSensorEntityDescription(
        key="used_flow",
        translation_key="used_flow",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda coordinator: coordinator.data.get(FLOW_USED),
    ),
    IoTfLoWSensorEntityDescription(
        key="remaining_flow",
        translation_key="remaining_flow",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.data.get(FLOW_REMAINING),
    ),
    IoTfLoWSensorEntityDescription(
        key="expiry_time",
        translation_key="expiry_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda coordinator: _parse_expiry(coordinator.data.get(FLOW_EXPIRY)),
    ),
    IoTfLoWSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.last_update_success_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IoTfLoWConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IoTfLoW sensors based on a config entry."""
    coordinator = entry.runtime_data
    card = entry.data[CONF_CARD]
    endpoint = normalize_endpoint(entry.data.get(CONF_ENDPOINT, DEFAULT_ENDPOINT))
    manufacturer = _base_url_host(entry.data[CONF_URL])
    configuration_url = device_configuration_url(entry.data[CONF_URL], endpoint, card)

    async_add_entities(
        IoTfLoWSensor(
            coordinator, description, manufacturer, card, endpoint, configuration_url
        )
        for description in SENSORS
    )


class IoTfLoWSensor(CoordinatorEntity[IoTfLoWDataUpdateCoordinator], SensorEntity):
    """Representation of an IoTfLoW sensor."""

    _attr_has_entity_name = True
    entity_description: IoTfLoWSensorEntityDescription

    def __init__(
        self,
        coordinator: IoTfLoWDataUpdateCoordinator,
        description: IoTfLoWSensorEntityDescription,
        manufacturer: str,
        card: str,
        endpoint: str,
        configuration_url: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=manufacturer,
            model=endpoint_path(endpoint),
            serial_number=card,
            name=f"{card}",
        )
        if configuration_url is not None:
            device_info["configuration_url"] = configuration_url

    @property
    @override
    def available(self) -> bool:
        """Keep the last known values while a refresh is failing."""
        return self.coordinator.data is not None

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator)
