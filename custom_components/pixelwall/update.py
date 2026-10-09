"""Firmware: which version runs, which one pixelwall.nl offers, and "install now"."""
from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PixelwallConfigEntry
from .entity import PixelwallEntity


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    # Firmware before 0.13.2 doesn't report "latest": no update entity then.
    if "latest" in (entry.runtime_data.data or {}):
        async_add_entities([PixelwallUpdate(entry.runtime_data, "firmware")])


class PixelwallUpdate(PixelwallEntity, UpdateEntity):
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    # The screen also installs updates by itself (within minutes of a release).
    _attr_auto_update = True

    @property
    def installed_version(self) -> str | None:
        return (self.coordinator.data or {}).get("firmware")

    @property
    def latest_version(self) -> str | None:
        data = self.coordinator.data or {}
        return data.get("latest") or data.get("firmware")

    @property
    def in_progress(self) -> bool:
        return bool((self.coordinator.data or {}).get("updating"))

    @property
    def update_percentage(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("update_percent") if data.get("updating") else None

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        await self.coordinator.run(self.coordinator.client.update())
