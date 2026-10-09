"""Polls the screen's state."""
from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PixelwallAuthError, PixelwallClient, PixelwallError
from .const import DOMAIN, SCAN_INTERVAL
from .pages import PageManager

_LOGGER = logging.getLogger(__name__)

type PixelwallConfigEntry = ConfigEntry[PixelwallCoordinator]


class PixelwallCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """State of one screen: brightness, current app, the apps it can show, …"""

    config_entry: PixelwallConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PixelwallConfigEntry, client: PixelwallClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client
        self.pages = PageManager(hass, entry.entry_id, client)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.state()
        except PixelwallAuthError as err:
            raise ConfigEntryAuthFailed("De koppelsleutel klopt niet meer") from err
        except PixelwallError as err:
            raise UpdateFailed(str(err)) from err

    async def run(self, call: Awaitable[dict[str, Any]]) -> None:
        """Run a command; commands answer with the new state, so entities update at once."""
        try:
            state = await call
        except PixelwallAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("De koppelsleutel van de Pixelwall klopt niet meer") from err
        except PixelwallError as err:
            raise HomeAssistantError(f"Pixelwall: {err}") from err
        if state:
            self.async_set_updated_data({**(self.data or {}), **state})
        else:
            await self.async_request_refresh()
