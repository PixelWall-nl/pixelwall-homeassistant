"""Diagnostics: whether the screen is connected to pixelwall.nl (scenes come from there)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PixelwallConfigEntry
from .entity import PixelwallEntity


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([PixelwallCloud(entry.runtime_data, "cloud")])


class PixelwallCloud(PixelwallEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("online"))
