"""Data update coordinator for China Gas."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ChinaGasApiClient,
    ChinaGasAuthError,
    ChinaGasData,
    ChinaGasError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ChinaGasDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinate updates for one China Gas config entry."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: ChinaGasApiClient,
        update_interval_seconds: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.api = api

    async def _async_update_data(self) -> ChinaGasData:
        """Fetch account data."""
        try:
            return await self.api.async_fetch_all()
        except ChinaGasAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ChinaGasError as err:
            raise UpdateFailed(str(err)) from err
