"""Pages on the screen that Home Assistant fills (pixelwall.set_page).

A page is a layout (value, grid, list, gauge, chart) with up to six items. An item shows an
entity's state or a fixed value. The page design goes to the screen once (POST /api/page, the
server draws it); after that every state change of a tracked entity goes straight to the screen
as a value (POST /api/values), which fills it in itself: instant, and without pixelwall.nl.
Pages are kept per screen in .storage, so tracking resumes after a restart.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .api import PixelwallClient, PixelwallError

_LOGGER = logging.getLogger(__name__)

LAYOUTS = ["grid", "value", "list", "gauge", "chart"]
MAX_ITEMS = 6
# Values of one page are sent at most this often (a power sensor may update every second).
SEND_DELAY = 1.0


def slug(text: str, length: int) -> str:
    """Same rule as the server: lowercase, anything else than a-z 0-9 _ becomes _."""
    return re.sub(r"[^a-z0-9_]+", "_", str(text).strip().lower())[:length]


def item_key(item: dict[str, Any], index: int) -> str:
    return slug(item.get("key") or item.get("entity", "").split(".")[-1] or f"i{index}", 16) or f"i{index}"


class PageManager:
    """The pages of one screen and the entities they follow."""

    def __init__(self, hass: HomeAssistant, entry_id: str, client: PixelwallClient) -> None:
        self.hass = hass
        self.client = client
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"pixelwall.pages.{entry_id}")
        self.pages: dict[str, dict[str, Any]] = {}
        self._unsub = None
        self._pending: dict[str, asyncio.TimerHandle] = {}

    async def async_load(self) -> None:
        self.pages = (await self._store.async_load() or {}).get("pages", {})
        self._track()
        for page in list(self.pages):   # the screen may have missed changes while we were down
            await self._send_values(page)

    @callback
    def async_unload(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        for handle in self._pending.values():
            handle.cancel()
        self._pending.clear()

    async def set_page(self, page: str, layout: str, title: str | None, items: list[dict[str, Any]]) -> None:
        name = slug(page, 32)
        items = [{**item, "key": item_key(item, i)} for i, item in enumerate(items[:MAX_ITEMS])]
        await self.client.page({
            "page": name,
            "title": title or "",
            "layout": layout,
            "items": [self._payload(item) for item in items],
        })
        self.pages[name] = {"layout": layout, "title": title, "items": items}
        await self._save()

    async def delete_page(self, page: str) -> None:
        name = slug(page, 32)
        await self.client.page({"page": name, "delete": True})
        self.pages.pop(name, None)
        await self._save()

    async def set_values(self, page: str, values: dict[str, Any]) -> None:
        """Fixed values from an automation: {key: text}."""
        await self.client.values(slug(page, 32), {slug(k, 16): str(v)[:20] for k, v in values.items()})

    # ---------- internals ----------

    def _payload(self, item: dict[str, Any]) -> dict[str, Any]:
        out = {"key": item["key"], "text": self._text(item)}
        for field in ("label", "icon", "color", "min", "max"):
            if item.get(field) not in (None, ""):
                out[field] = item[field]
        return out

    def _text(self, item: dict[str, Any]) -> str:
        """What the screen shows for an item: the entity's state (or the fixed value) with its unit."""
        unit = item.get("unit")
        if item.get("entity"):
            state = self.hass.states.get(item["entity"])
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return "-"
            value = state.state
            if unit is None:
                unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        else:
            value = item.get("value", "")
        text = self._number(value)
        if unit:
            text += unit if str(unit).startswith(("°", "%")) else f" {unit}"
        return text[:20]

    def _number(self, value: Any) -> str:
        """21.4372 → "21,4" (Dutch) / "21.4"; whole numbers and words stay as they are."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        text = str(round(number)) if number.is_integer() or abs(number) >= 100 else f"{number:.1f}"
        return text.replace(".", ",") if self.hass.config.language.startswith("nl") else text

    @callback
    def _track(self) -> None:
        if self._unsub:
            self._unsub()
        entities = {item["entity"] for page in self.pages.values() for item in page["items"] if item.get("entity")}
        self._unsub = async_track_state_change_event(self.hass, list(entities), self._changed) if entities else None

    @callback
    def _changed(self, event: Event[EventStateChangedData]) -> None:
        entity = event.data["entity_id"]
        for name, page in self.pages.items():
            if any(item.get("entity") == entity for item in page["items"]) and name not in self._pending:
                self._pending[name] = self.hass.loop.call_later(
                    SEND_DELAY, lambda name=name: self.hass.async_create_task(self._send_values(name))
                )

    async def _send_values(self, name: str) -> None:
        self._pending.pop(name, None)
        page = self.pages.get(name)
        if not page:
            return
        try:
            await self.client.values(name, {item["key"]: self._text(item) for item in page["items"]})
        except PixelwallError as err:
            _LOGGER.debug("Pixelwall page %s: %s", name, err)

    async def _save(self) -> None:
        await self._store.async_save({"pages": self.pages})
        self._track()
