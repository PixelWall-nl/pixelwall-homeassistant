"""Which app is on screen; choosing one shows it now (for its duration)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PixelwallConfigEntry
from .entity import PixelwallEntity


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([PixelwallAppSelect(entry.runtime_data, "app")])


class PixelwallAppSelect(PixelwallEntity, SelectEntity):
    def _apps(self) -> list[dict[str, str]]:
        return [a for a in (self.coordinator.data or {}).get("apps", []) if a.get("key") and a.get("name")]

    @property
    def options(self) -> list[str]:
        return [a["name"] for a in self._apps()]

    @property
    def current_option(self) -> str | None:
        current = (self.coordinator.data or {}).get("app")
        return next((a["name"] for a in self._apps() if a["key"] == current), None)

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {"app_key": (self.coordinator.data or {}).get("app") or None}

    async def async_select_option(self, option: str) -> None:
        key = next(a["key"] for a in self._apps() if a["name"] == option)
        await self.coordinator.run(self.coordinator.client.show(key))
