"""Next / previous app, and back to the brightness schedule."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PixelwallConfigEntry, PixelwallCoordinator
from .entity import PixelwallEntity

BUTTONS = {"next": None, "previous": None, "auto": EntityCategory.CONFIG}


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities(PixelwallButton(entry.runtime_data, action, category) for action, category in BUTTONS.items())


class PixelwallButton(PixelwallEntity, ButtonEntity):
    def __init__(self, coordinator: PixelwallCoordinator, action: str, category: EntityCategory | None) -> None:
        super().__init__(coordinator, action)
        self._action = action
        self._attr_entity_category = category

    async def async_press(self) -> None:
        await self.coordinator.run(self.coordinator.client.command(self._action))
