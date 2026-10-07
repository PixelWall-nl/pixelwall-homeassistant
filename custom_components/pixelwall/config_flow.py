"""Config flow: found via zeroconf (_pixelwall._tcp) or by address; the key comes from pixelwall.nl."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import PixelwallAuthError, PixelwallClient, PixelwallError
from .const import CONF_KEY, DASHBOARD_URL, DOMAIN

KEY_SCHEMA = vol.Schema({vol.Required(CONF_KEY): str})


class PixelwallConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._info: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip().removeprefix("http://").rstrip("/")
            try:
                self._info = await self._client().info()
            except PixelwallError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(self._info["id"])
                self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
                return await self._finish(user_input[CONF_KEY], errors, "user")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=self._host or ""): str, vol.Required(CONF_KEY): str}),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        screen_id = discovery_info.properties.get("id")
        if not screen_id:
            return self.async_abort(reason="not_pixelwall")
        self._host = discovery_info.host
        await self.async_set_unique_id(screen_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        try:
            self._info = await self._client().info()
        except PixelwallError:
            return self.async_abort(reason="cannot_connect")
        self.context["title_placeholders"] = {"name": self._title()}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return await self._finish(user_input[CONF_KEY], errors, "zeroconf_confirm")
        return self._key_form("zeroconf_confirm", errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await self._client(user_input[CONF_KEY]).state()
            except PixelwallAuthError:
                errors["base"] = "invalid_auth"
            except PixelwallError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_KEY: user_input[CONF_KEY].strip()})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=KEY_SCHEMA,
            errors=errors,
            description_placeholders={"name": entry.title, "url": DASHBOARD_URL.format(id=entry.unique_id)},
        )

    async def _finish(self, key: str, errors: dict[str, str], step: str) -> ConfigFlowResult:
        key = key.strip()
        try:
            state = await self._client(key).state()
        except PixelwallAuthError:
            errors["base"] = "invalid_auth"
        except PixelwallError:
            errors["base"] = "cannot_connect"
        else:
            self._info["name"] = state.get("name") or self._info.get("name")
            return self.async_create_entry(title=self._title(), data={CONF_HOST: self._host, CONF_KEY: key})
        if step == "user":
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_HOST, default=self._host or ""): str, vol.Required(CONF_KEY): str}),
                errors=errors,
            )
        return self._key_form(step, errors)

    def _key_form(self, step: str, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id=step,
            data_schema=KEY_SCHEMA,
            errors=errors,
            description_placeholders={"name": self._title(), "url": DASHBOARD_URL.format(id=self.unique_id)},
        )

    def _title(self) -> str:
        return self._info.get("name") or f"Pixelwall {self._info.get('id', '')}".strip()

    def _client(self, key: str | None = None) -> PixelwallClient:
        return PixelwallClient(async_get_clientsession(self.hass), self._host or "", key)
