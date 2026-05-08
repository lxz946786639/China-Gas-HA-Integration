"""Diagnostics support for China Gas."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_USER_ID,
    CONF_X_MAS_APP_INFO,
    DATA_COORDINATORS,
    DOMAIN,
)

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_USER_ID,
    CONF_X_MAS_APP_INFO,
    "address",
    "mobile",
    "meter_no",
    "meter_seq",
    "referer",
    "secret_key",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(DATA_COORDINATORS, {}).get(
        config_entry.entry_id
    )
    data: dict[str, Any] = {
        "entry": {
            "title": config_entry.title,
            "data": config_entry.data,
            "options": config_entry.options,
        }
    }

    if coordinator is not None and coordinator.data is not None:
        data["last_update_success"] = coordinator.last_update_success
        data["account"] = {
            "customer": coordinator.data.customer,
            "bill_count": len(coordinator.data.bills),
            "statistics": coordinator.data.statistics,
            "last_update": coordinator.data.last_update,
        }

    return async_redact_data(data, TO_REDACT)
