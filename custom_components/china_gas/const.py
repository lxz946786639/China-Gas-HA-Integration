"""Constants for the China Gas integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "china_gas"
NAME = "China Gas"
MANUFACTURER = "China Gas"

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_ACCESS_FROM = "access_from"
CONF_ACCESS_TOKEN = "access_token"
CONF_ADVANCED_OPTIONS = "advanced_options"
CONF_BILL_MONTHS = "bill_months"
CONF_CUST_CODE = "cust_code"
CONF_CUST_NAME = "cust_name"
CONF_REFERER = "referer"
CONF_SECRET_KEY = "secret_key"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_UPDATE_INTERVAL_MINUTES = "update_interval_minutes"
CONF_USER_AGENT = "user_agent"
CONF_USER_ID = "user_id"
CONF_X_MAS_APP_INFO = "x_mas_app_info"

DEFAULT_ACCESS_FROM = "yphpaymp"
DEFAULT_BILL_MONTHS = 12
DEFAULT_REFERER = "https://servicewechat.com/wx2082cbdc25b3b8e6/103/page-frame.html"
DEFAULT_SECRET_KEY = "yph1234567890"
DEFAULT_UPDATE_INTERVAL = 21600
DEFAULT_UPDATE_INTERVAL_MINUTES = DEFAULT_UPDATE_INTERVAL // 60
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 "
    "MicroMessenger MiniProgramEnv"
)
DEFAULT_X_MAS_APP_INFO = ""

MAX_BILL_MONTHS = 12
MIN_BILL_MONTHS = 2
MIN_UPDATE_INTERVAL = 300
MIN_UPDATE_INTERVAL_MINUTES = MIN_UPDATE_INTERVAL // 60

SERVICE_REFRESH_ACCOUNT = "refresh_account"
ATTR_FORCE = "force"

DATA_COORDINATORS = "coordinators"
