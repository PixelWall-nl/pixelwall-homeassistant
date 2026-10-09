"""Client for the Pixelwall screen's local API (firmware 0.9+)."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=8)


class PixelwallError(Exception):
    """The screen could not be reached or answered with an error."""


class PixelwallAuthError(PixelwallError):
    """The key was rejected (regenerated in the dashboard?)."""


class PixelwallClient:
    """Talks to http://<host>/api/… with the screen's key."""

    def __init__(self, session: aiohttp.ClientSession, host: str, key: str | None = None) -> None:
        self._session = session
        self.host = host
        self._key = key

    async def info(self) -> dict[str, Any]:
        """Identity of the screen; needs no key."""
        return await self._request("GET", "/api/info", auth=False)

    async def state(self) -> dict[str, Any]:
        return await self._request("GET", "/api/state")

    async def brightness(self, percent: int) -> dict[str, Any]:
        return await self._request("POST", "/api/brightness", params={"value": max(0, min(100, percent))})

    async def power(self, on: bool) -> dict[str, Any]:
        return await self._request("POST", "/api/power", params={"state": "on" if on else "off"})

    async def command(self, action: str) -> dict[str, Any]:
        """next, previous or auto (back to the brightness schedule)."""
        return await self._request("POST", f"/api/{action}")

    async def show(self, app: str) -> dict[str, Any]:
        return await self._request("POST", "/api/show", json={"app": app})

    async def enable(self, app: str, enabled: bool) -> dict[str, Any]:
        """Takes an app into or out of the rotation (firmware 0.13.0-beta.7+)."""
        return await self._request("POST", "/api/enable", json={"app": app, "enabled": enabled})

    async def notify(self, message: str, title: str | None = None, icon: str | None = None,
                     color: str | None = None, duration: int | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"message": message}
        for field, value in (("title", title), ("icon", icon), ("color", color), ("duration", duration)):
            if value not in (None, ""):
                body[field] = value
        return await self._request("POST", "/api/notify", json=body)

    async def _request(self, method: str, path: str, *, auth: bool = True,
                       params: dict[str, Any] | None = None, json: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"X-Pixelwall-Key": self._key} if auth and self._key else {}
        try:
            async with self._session.request(method, f"http://{self.host}{path}", params=params, json=json,
                                             headers=headers, timeout=TIMEOUT) as resp:
                if resp.status == 401:
                    raise PixelwallAuthError("invalid key")
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise PixelwallError(data.get("error", f"HTTP {resp.status}") if isinstance(data, dict) else f"HTTP {resp.status}")
                return data if isinstance(data, dict) else {}
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise PixelwallError(f"{self.host}: {err}") from err
