"""Data coordinator for the oilprice integration."""

from __future__ import annotations

from datetime import timedelta
import inspect
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    OilPriceApiError,
    OilPriceCannotConnectError,
    OilPriceInvalidRegionError,
    async_fetch_oilprice,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# The coordinator only accepts a config entry since Home Assistant 2024.11.
# On older versions the entry is picked up from the current setup context.
_SUPPORTS_CONFIG_ENTRY = (
    "config_entry" in inspect.signature(DataUpdateCoordinator.__init__).parameters
)


class OilPriceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage periodic oilprice updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        region: str,
        update_interval_hours: int,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize coordinator."""
        kwargs: dict[str, Any] = {
            "name": f"{DOMAIN}_{region}",
            "update_interval": timedelta(hours=max(1, int(update_interval_hours))),
        }
        if _SUPPORTS_CONFIG_ENTRY:
            kwargs["config_entry"] = config_entry

        super().__init__(hass, _LOGGER, **kwargs)
        self._region = region

    @property
    def region(self) -> str:
        """Return configured region."""
        return self._region

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest oilprice data."""
        try:
            return await async_fetch_oilprice(self.hass, self._region)
        except OilPriceCannotConnectError as err:
            raise UpdateFailed("Unable to connect to oilprice service") from err
        except OilPriceInvalidRegionError as err:
            raise UpdateFailed("Region is invalid or unsupported") from err
        except OilPriceApiError as err:
            raise UpdateFailed(str(err)) from err
