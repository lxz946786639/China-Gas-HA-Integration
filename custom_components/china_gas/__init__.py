"""China Gas integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ChinaGasAccountConfig, ChinaGasApiClient, ChinaGasData, calculate_bill_statistics
from .const import (
    ATTR_FORCE,
    DATA_COORDINATORS,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH_ACCOUNT,
)
from .coordinator import ChinaGasDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_REFRESH_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_FORCE, default=False): cv.boolean,
    }
)

async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the China Gas integration."""
    hass.data.setdefault(DOMAIN, {DATA_COORDINATORS: {}})
    _async_register_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up China Gas from a config entry."""
    hass.data.setdefault(DOMAIN, {DATA_COORDINATORS: {}})

    account_data = {**entry.data, **entry.options}
    account = ChinaGasAccountConfig.from_mapping(account_data)
    session = async_get_clientsession(hass)
    api = ChinaGasApiClient(session, account)
    coordinator = ChinaGasDataUpdateCoordinator(
        hass,
        entry,
        api,
        account.update_interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        raise
    except Exception:
        _LOGGER.exception(
            "Initial China Gas refresh failed; loading the entry with empty data"
        )
        coordinator.data = ChinaGasData(
            customer={
                "cust_code": account.cust_code,
                "cust_name": account.cust_name,
                "balance": None,
                "new_balance": None,
                "owe_money": None,
                "qty_balance": None,
                "max_gas": None,
                "award_money": None,
                "agent_money": None,
                "last_record": None,
                "last_record_time": None,
                "customer_status": None,
                "customer_type": None,
                "meter_status": None,
                "company": None,
                "address": None,
                "mobile": None,
                "meter_no": None,
                "meter_model": None,
                "meter_form_name": None,
                "meter_form_code": None,
                "meter_seq": None,
                "meter_type": None,
            },
            bills=[],
            statistics=calculate_bill_statistics([]),
            latest_bill=None,
            last_update=datetime.now().astimezone().isoformat(),
            available=False,
        )

    hass.data[DOMAIN][DATA_COORDINATORS][entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a China Gas config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATORS].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload an entry after options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_ACCOUNT):
        return

    async def async_refresh_account(call: ServiceCall) -> None:
        """Refresh one or all China Gas accounts."""
        coordinators = _coordinators_from_service_call(hass, call)
        force = call.data.get(ATTR_FORCE, False)

        for coordinator in coordinators:
            if force:
                await coordinator.async_refresh()
            else:
                await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_ACCOUNT,
        async_refresh_account,
        schema=SERVICE_REFRESH_SCHEMA,
    )


def _coordinators_from_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> list[ChinaGasDataUpdateCoordinator]:
    """Resolve service target entities to coordinators."""
    coordinators: dict[str, ChinaGasDataUpdateCoordinator] = hass.data[DOMAIN][
        DATA_COORDINATORS
    ]
    entity_ids = call.data.get(ATTR_ENTITY_ID)
    if not entity_ids:
        return list(coordinators.values())

    registry = er.async_get(hass)
    selected: dict[str, ChinaGasDataUpdateCoordinator] = {}
    for entity_id in entity_ids:
        entity_entry = registry.async_get(entity_id)
        if entity_entry is None or entity_entry.platform != DOMAIN:
            continue
        if entity_entry.config_entry_id in coordinators:
            selected[entity_entry.config_entry_id] = coordinators[
                entity_entry.config_entry_id
            ]

    if not selected:
        _LOGGER.debug("No China Gas coordinators matched service target %s", entity_ids)
    return list(selected.values())
