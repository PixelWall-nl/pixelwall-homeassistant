"""Client for the Pixelwall screen's local API (firmware 0.9+)."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json as jsonlib
import re
from ipaddress import IPv6Address, ip_address
from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=8)
# The screen answers with a few hundred bytes; anything this big is not the screen.
MAX_RESPONSE = 64 * 1024

# What the entities read from /api/state (and command answers) and /api/info, with its type.
# A field of the wrong type is dropped, as if the firmware didn't report it; other fields pass.
STATE_FIELDS: dict[str, type] = {
    "id": str, "name": str, "model": str, "firmware": str, "latest": str, "power": str, "scene": str,
    "app": str, "ip": str, "proof": str, "brightness": int, "rssi": int, "update_percent": int,
    "updating": bool, "online": bool, "linked": bool,
}
APP_FIELDS: dict[str, type] = {"key": str, "name": str, "enabled": bool}

PROOF_PREFIX = "pixelwall-proof:"

HOSTNAME = re.compile(r"^(?=.{1,253}$)[a-z0-9_]([a-z0-9_-]{0,62})(\.[a-z0-9_]([a-z0-9_-]{0,62}))*\.?$", re.IGNORECASE)


class PixelwallError(Exception):
    """The screen could not be reached or answered with an error."""


class PixelwallAuthError(PixelwallError):
    """The key was rejected (regenerated in the dashboard?)."""


def normalize_host(text: str) -> str | None:
    """What someone typed as the screen's address → host[:port], or None if it is anything else.

    "http://pixelwall-g4hvh8.local/" → "pixelwall-g4hvh8.local"; IPv6 gets brackets ("[fd00::1]:80").
    Paths, queries, user info and other schemes (https://) are refused.
    """
    host = text.strip()
    if host[:7].lower() == "http://":
        host = host[7:]
    host = host.rstrip("/")
    if not host or any(c in host for c in "/?#@\\ "):
        return None
    if bracketed := re.fullmatch(r"\[([0-9a-fA-F:.]+)\](?::(\d{1,5}))?", host):
        address, port = bracketed.groups()
    elif host.count(":") > 1:
        address, port = host, None   # bare IPv6, no room for a port
    else:
        address, colon, port = host.partition(":")
        port = port if colon else None
        if not HOSTNAME.fullmatch(address):
            return None
    if port is not None and not (port.isdigit() and 0 < int(port) < 65536):
        return None
    if bracketed or host.count(":") > 1:
        try:
            if not isinstance(ip := ip_address(address), IPv6Address):
                return None
        except ValueError:
            return None
        address = f"[{ip.compressed}]"
    return f"{address}:{int(port)}" if port is not None else address


def base_url(host: str) -> str:
    """http://host[:port]; a bare IPv6 address (as zeroconf reports it) gets its brackets."""
    if host.count(":") > 1 and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}"


class PixelwallClient:
    """Talks to http://<host>/api/… with the screen's key."""

    def __init__(self, session: aiohttp.ClientSession, host: str, key: str | None = None) -> None:
        self._session = session
        self.host = host
        self._key = key
        self._url = base_url(host)

    async def info(self, nonce: str | None = None) -> dict[str, Any]:
        """Identity of the screen; never sends the key.

        With a nonce, firmware 0.13.5+ adds "proof" (see valid_proof): the screen shows it holds
        the key without us handing it to a host we don't trust yet.
        """
        info = await self._request("GET", "/api/info", auth=False, params={"nonce": nonce} if nonce else None)
        if not info.get("id"):
            raise PixelwallError(f"{self.host}: no screen id in /api/info")
        return info

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

    async def update(self) -> dict[str, Any]:
        """Look for a firmware update now and install it (firmware 0.13.2+)."""
        return await self._request("POST", "/api/update")

    async def page(self, page: dict[str, Any]) -> dict[str, Any]:
        """A page design {page, title, layout, items}, or {page, delete: true} (firmware 0.13.2+)."""
        return await self._request("POST", "/api/page", json=page)

    async def values(self, page: str, values: dict[str, str]) -> dict[str, Any]:
        """New texts for a page's items; the screen shows them at once (firmware 0.13.2+)."""
        return await self._request("POST", "/api/values", json={"page": page, "values": values})

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
            async with self._session.request(method, f"{self._url}{path}", params=params, json=json,
                                             headers=headers, timeout=TIMEOUT) as resp:
                if resp.status == 401:
                    raise PixelwallAuthError("invalid key")
                length = resp.headers.get("Content-Length", "")
                if length.isdigit() and int(length) > MAX_RESPONSE:
                    raise PixelwallError(f"{self.host}: answer too large")
                body = await resp.content.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise PixelwallError(f"{self.host}: answer too large")
                data = jsonlib.loads(body) if body.strip() else {}
                if resp.status >= 400:
                    error = data.get("error") if isinstance(data, dict) else None
                    raise PixelwallError(error[:100] if isinstance(error, str) else f"HTTP {resp.status}")
                return clean(data)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise PixelwallError(f"{self.host}: {err}") from err


def valid_proof(key: str, nonce: str, proof: Any) -> bool:
    """Whether proof is HMAC-SHA256(key, "pixelwall-proof:" + nonce) in lowercase hex."""
    if not isinstance(proof, str):
        return False
    expected = hmac.new(key.encode(), f"{PROOF_PREFIX}{nonce}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), proof.encode())


def clean(data: Any) -> dict[str, Any]:
    """The answer with malformed fields dropped, so a confused screen can't trip up an entity."""
    if not isinstance(data, dict):
        return {}
    out = {k: v for k, v in data.items() if k not in STATE_FIELDS and k != "apps"}
    for field, kind in STATE_FIELDS.items():
        # bool is an int to Python; a brightness of true is still wrong.
        if isinstance(data.get(field), kind) and (kind is bool or not isinstance(data[field], bool)):
            out[field] = data[field]
    if "apps" in data:
        apps = data["apps"] if isinstance(data["apps"], list) else []
        out["apps"] = [
            {k: app[k] for k, kind in APP_FIELDS.items() if isinstance(app.get(k), kind)}
            for app in apps
            if isinstance(app, dict) and isinstance(app.get("key"), str) and app["key"]
        ]
    return out
