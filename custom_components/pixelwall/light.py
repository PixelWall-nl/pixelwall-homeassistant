"""The panel as a dimmable light: on/off and brightness (overrides the schedule until it changes)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PixelwallConfigEntry
from .entity import PixelwallEntity


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([PixelwallLight(entry.runtime_data, "display")])


class PixelwallLight(PixelwallEntity, LightEntity):
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_name = None   # the device itself

    @property
    def is_on(self) -> bool:
        return (self.coordinator.data or {}).get("power") == "on"

    @property
    def brightness(self) -> int | None:
        percent = (self.coordinator.data or {}).get("brightness")
        return round(percent * 255 / 100) if isinstance(percent, int) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        client = self.coordinator.client
        if ATTR_BRIGHTNESS in kwargs:
            await self.coordinator.run(client.brightness(max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))))
        else:
            await self.coordinator.run(client.power(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.run(self.coordinator.client.power(False))
