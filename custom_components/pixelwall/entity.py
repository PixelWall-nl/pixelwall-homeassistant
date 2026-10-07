"""Base entity: one device per screen."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DASHBOARD_URL, DOMAIN, MANUFACTURER
from .coordinator import PixelwallCoordinator


class PixelwallEntity(CoordinatorEntity[PixelwallCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PixelwallCoordinator, key: str) -> None:
        super().__init__(coordinator)
        screen_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{screen_id}_{key}"
        self._attr_translation_key = key
        data = coordinator.data or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, screen_id)},
            name=data.get("name") or f"Pixelwall {screen_id}",
            manufacturer=MANUFACTURER,
            model="HD-WF2 128×64",
            serial_number=screen_id,
            sw_version=data.get("firmware"),
            configuration_url=DASHBOARD_URL.format(id=screen_id),
        )
