"""A notify entity: notify.send_message shows the text on the screen."""
from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PixelwallConfigEntry
from .entity import PixelwallEntity


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([PixelwallNotify(entry.runtime_data, "message")])


class PixelwallNotify(PixelwallEntity, NotifyEntity):
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await self.coordinator.run(self.coordinator.client.notify(message, title=title))
