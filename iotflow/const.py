"""Constants for the IoTfLoW integration."""

import logging
from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "iotflow"
LOGGER = logging.getLogger(__package__)

# The service reports its timestamps in China Standard Time.
SERVICE_TIME_ZONE: Final = ZoneInfo("Asia/Shanghai")

ISSUE_API_ERROR: Final = "api_error"

CONF_CARD: Final = "card"
CONF_ENDPOINT: Final = "endpoint"
CONF_RETRIES: Final = "retries"
CONF_RETRY_INTERVAL: Final = "retry_interval"
CONF_UPDATE_INTERVAL: Final = "update_interval"

SECTION_ADVANCED: Final = "advanced"

ENDPOINT_CARD_FLOW: Final = "getCardFlow"
ENDPOINT_PHONE_SIM_CARD: Final = "phoneSimCard"
ENDPOINTS: Final = (ENDPOINT_CARD_FLOW, ENDPOINT_PHONE_SIM_CARD)

# Fields of the flow query response the sensors read.
FLOW_TOTAL: Final = "sumFlow"
FLOW_USED: Final = "consumeFlow"
FLOW_REMAINING: Final = "surplusFlow"
FLOW_EXPIRY: Final = "maxEndTime"
FLOW_KEYS: Final = (FLOW_TOTAL, FLOW_USED, FLOW_REMAINING)

DEFAULT_BASE_URL: Final = "https://sdx.babm.cn"
DEFAULT_ENDPOINT: Final = ENDPOINT_CARD_FLOW
DEFAULT_RETRIES: Final = 5
DEFAULT_RETRY_INTERVAL: Final = 15
DEFAULT_TIMEOUT: Final = 10
DEFAULT_UPDATE_INTERVAL: Final = 30
