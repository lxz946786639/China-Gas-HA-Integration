"""Config flow for China Gas."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

try:
    from homeassistant.data_entry_flow import section
except ImportError:  # pragma: no cover - compatibility with older HA versions
    section = None

from .api import (
    ChinaGasAccountConfig,
    ChinaGasAccountError,
    ChinaGasApiClient,
    ChinaGasAuthError,
    ChinaGasError,
)
from .const import (
    CONF_ACCESS_FROM,
    CONF_ACCESS_TOKEN,
    CONF_ADVANCED_OPTIONS,
    CONF_BILL_MONTHS,
    CONF_CUST_CODE,
    CONF_CUST_NAME,
    CONF_REFERER,
    CONF_SECRET_KEY,
    CONF_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL_MINUTES,
    CONF_USER_AGENT,
    CONF_USER_ID,
    CONF_X_MAS_APP_INFO,
    DEFAULT_ACCESS_FROM,
    DEFAULT_BILL_MONTHS,
    DEFAULT_REFERER,
    DEFAULT_SECRET_KEY,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DEFAULT_USER_AGENT,
    DEFAULT_X_MAS_APP_INFO,
    DOMAIN,
    MAX_BILL_MONTHS,
    MIN_BILL_MONTHS,
    MIN_UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

CONF_NAME = "name"
NON_EMPTY_STRING = vol.All(str, vol.Length(min=1))


class CannotConnect(Exception):
    """Error to indicate connection failure."""


class InvalidAuth(Exception):
    """Error to indicate invalid auth."""


class AccountNotFound(Exception):
    """Error to indicate invalid account information."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate user input and return the entry title."""
    account = ChinaGasAccountConfig.from_mapping(data)
    api = ChinaGasApiClient(async_get_clientsession(hass), account)

    try:
        try:
            await api.async_track_event()
        except ChinaGasError as err:
            _LOGGER.warning("China Gas initialization request failed: %s", err)

        try:
            await api.async_check_token()
        except ChinaGasAuthError:
            raise
        except ChinaGasError as err:
            _LOGGER.warning("China Gas token check failed; continuing: %s", err)

        await api.async_get_customer_info()
    except ChinaGasAuthError as err:
        raise InvalidAuth from err
    except ChinaGasAccountError as err:
        raise AccountNotFound from err
    except ChinaGasError as err:
        raise CannotConnect from err

    return account.name


def account_defaults(defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return account form defaults."""
    defaults = defaults or {}
    return {
        CONF_NAME: defaults.get(CONF_NAME, ""),
        CONF_CUST_CODE: defaults.get(CONF_CUST_CODE, ""),
        CONF_CUST_NAME: defaults.get(CONF_CUST_NAME, ""),
        CONF_USER_ID: defaults.get(CONF_USER_ID, ""),
        CONF_ACCESS_TOKEN: defaults.get(CONF_ACCESS_TOKEN, ""),
        CONF_SECRET_KEY: defaults.get(CONF_SECRET_KEY, DEFAULT_SECRET_KEY),
        CONF_X_MAS_APP_INFO: defaults.get(CONF_X_MAS_APP_INFO, DEFAULT_X_MAS_APP_INFO),
        CONF_REFERER: defaults.get(CONF_REFERER, DEFAULT_REFERER),
        CONF_ACCESS_FROM: defaults.get(CONF_ACCESS_FROM, DEFAULT_ACCESS_FROM),
        CONF_USER_AGENT: defaults.get(CONF_USER_AGENT, DEFAULT_USER_AGENT),
        CONF_BILL_MONTHS: defaults.get(CONF_BILL_MONTHS, DEFAULT_BILL_MONTHS),
    }


def normalize_account_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize first-step account form data."""
    data = dict(user_input)
    advanced = data.pop(CONF_ADVANCED_OPTIONS, None)
    if isinstance(advanced, dict):
        data.update(advanced)

    for key, value in list(data.items()):
        if isinstance(value, str):
            data[key] = value.strip()

    defaults = account_defaults(data)
    data = {**defaults, **data}

    cust_code = str(data[CONF_CUST_CODE]).strip()
    cust_name = str(data[CONF_CUST_NAME]).strip()
    data[CONF_NAME] = data.get(CONF_NAME) or f"{cust_code}-{cust_name}"
    data[CONF_BILL_MONTHS] = int(data.get(CONF_BILL_MONTHS, DEFAULT_BILL_MONTHS))
    data[CONF_UPDATE_INTERVAL] = int(
        data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )
    return data


def add_refresh_to_data(data: dict[str, Any], user_input: dict[str, Any]) -> dict[str, Any]:
    """Add second-step refresh interval to config entry data."""
    merged = dict(data)
    minutes = int(user_input[CONF_UPDATE_INTERVAL_MINUTES])
    merged[CONF_UPDATE_INTERVAL] = minutes * 60
    return merged


def update_interval_minutes(defaults: dict[str, Any] | None = None) -> int:
    """Return refresh interval minutes for form defaults."""
    defaults = defaults or {}
    if CONF_UPDATE_INTERVAL_MINUTES in defaults:
        return int(defaults[CONF_UPDATE_INTERVAL_MINUTES])
    seconds = int(defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
    return max(MIN_UPDATE_INTERVAL_MINUTES, seconds // 60)


def account_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return first-step account schema."""
    defaults = account_defaults(defaults)
    advanced_schema = vol.Schema(
        {
            vol.Optional(CONF_NAME, default=defaults[CONF_NAME]): str,
            vol.Optional(CONF_REFERER, default=defaults[CONF_REFERER]): str,
            vol.Optional(
                CONF_ACCESS_FROM,
                default=defaults[CONF_ACCESS_FROM],
            ): str,
            vol.Optional(CONF_USER_AGENT, default=defaults[CONF_USER_AGENT]): str,
            vol.Required(
                CONF_BILL_MONTHS,
                default=defaults[CONF_BILL_MONTHS],
            ): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_BILL_MONTHS, max=MAX_BILL_MONTHS)
            ),
        }
    )

    schema: dict[Any, Any] = {
        vol.Required(CONF_CUST_CODE, default=defaults[CONF_CUST_CODE]): NON_EMPTY_STRING,
        vol.Required(CONF_CUST_NAME, default=defaults[CONF_CUST_NAME]): NON_EMPTY_STRING,
        vol.Required(CONF_USER_ID, default=defaults[CONF_USER_ID]): NON_EMPTY_STRING,
        vol.Required(
            CONF_ACCESS_TOKEN, default=defaults[CONF_ACCESS_TOKEN]
        ): NON_EMPTY_STRING,
        vol.Required(CONF_SECRET_KEY, default=defaults[CONF_SECRET_KEY]): NON_EMPTY_STRING,
        vol.Required(
            CONF_X_MAS_APP_INFO,
            default=defaults[CONF_X_MAS_APP_INFO],
        ): NON_EMPTY_STRING,
    }

    if section is not None:
        schema[vol.Optional(CONF_ADVANCED_OPTIONS)] = section(
            advanced_schema,
            {"collapsed": True},
        )
    else:
        schema.update(advanced_schema.schema)

    return vol.Schema(schema)


def refresh_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return second-step refresh interval schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_UPDATE_INTERVAL_MINUTES,
                default=update_interval_minutes(defaults),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES)),
        }
    )


class ChinaGasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for China Gas."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._account_data: dict[str, Any] = {}
        self._title: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the account information step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                data = normalize_account_input(user_input)
            except Exception:
                _LOGGER.exception("Invalid China Gas config form input")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{data[CONF_USER_ID]}_{data[CONF_CUST_CODE]}"
                )
                self._abort_if_unique_id_configured()

            if not errors:
                try:
                    self._title = await validate_input(self.hass, data)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except AccountNotFound:
                    errors["base"] = "account_not_found"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected exception while validating China Gas config"
                    )
                    errors["base"] = "cannot_connect"
                else:
                    self._account_data = data
                    return await self.async_step_refresh()

        return self.async_show_form(
            step_id="user",
            data_schema=account_schema(user_input),
            errors=errors,
        )

    async def async_step_refresh(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the refresh interval step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                data = add_refresh_to_data(self._account_data, user_input)
            except Exception:
                _LOGGER.exception("Invalid China Gas refresh form input")
                errors["base"] = "cannot_connect"
            else:
                title = self._title or data[CONF_NAME]
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="refresh",
            data_schema=refresh_schema(self._account_data),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return ChinaGasOptionsFlow(config_entry)


class ChinaGasOptionsFlow(config_entries.OptionsFlow):
    """Handle China Gas options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._account_data: dict[str, Any] = {}
        self._title: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage account options."""
        errors: dict[str, str] = {}
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            try:
                merged = normalize_account_input({**current, **user_input})
            except Exception:
                _LOGGER.exception("Invalid China Gas options form input")
                errors["base"] = "cannot_connect"
            else:
                try:
                    title = await validate_input(self.hass, merged)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except AccountNotFound:
                    errors["base"] = "account_not_found"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected exception while validating China Gas options"
                    )
                    errors["base"] = "cannot_connect"
                else:
                    self._account_data = merged
                    self._title = title
                    return await self.async_step_refresh()

        return self.async_show_form(
            step_id="init",
            data_schema=account_schema(current),
            errors=errors,
        )

    async def async_step_refresh(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage refresh interval options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                merged = add_refresh_to_data(self._account_data, user_input)
            except Exception:
                _LOGGER.exception("Invalid China Gas options refresh form input")
                errors["base"] = "cannot_connect"
            else:
                if self._title is not None:
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        title=self._title,
                    )
                return self.async_create_entry(title="", data=merged)

        return self.async_show_form(
            step_id="refresh",
            data_schema=refresh_schema(self._account_data),
            errors=errors,
        )
