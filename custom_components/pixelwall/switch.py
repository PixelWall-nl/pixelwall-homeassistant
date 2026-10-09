"""One switch per app: in the screen's rotation or not (hide the radio app while the radio is off)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PixelwallConfigEntry, PixelwallCoordinator
from .entity import PixelwallEntity


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    added: set[str] = set()

    @callback
    def add_new_apps() -> None:
        # Firmware before 0.13.0-beta.7 doesn't report "enabled": no switches then.
        new = [a for a in (coordinator.data or {}).get("apps", []) if "enabled" in a and a.get("key") and a["key"] not in added]
        added.update(a["key"] for a in new)
        async_add_entities([PixelwallAppSwitch(coordinator, a["key"], a.get("name") or a["key"]) for a in new])

    add_new_apps()
    entry.async_on_unload(coordinator.async_add_listener(add_new_apps))


class PixelwallAppSwitch(PixelwallEntity, SwitchEntity):
    def __init__(self, coordinator: PixelwallCoordinator, app: str, name: str) -> None:
        super().__init__(coordinator, f"rotation_{app}")
        self._app = app
        self._attr_translation_key = "rotation"
        self._attr_translation_placeholders = {"app": name}

    def _entry(self) -> dict | None:
        return next((a for a in (self.coordinator.data or {}).get("apps", []) if a.get("key") == self._app), None)

    @property
    def available(self) -> bool:
        return super().available and self._entry() is not None   # uninstalled since

    @property
    def is_on(self) -> bool | None:
        app = self._entry()
        return bool(app["enabled"]) if app and "enabled" in app else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.run(self.coordinator.client.enable(self._app, True))

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.run(self.coordinator.client.enable(self._app, False))
