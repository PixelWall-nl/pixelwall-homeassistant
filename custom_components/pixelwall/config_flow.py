"""Config flow: found via zeroconf (_pixelwall._tcp) or by address; the key comes from pixelwall.nl."""
from __future__ import annotations

import logging
import secrets
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import PixelwallAuthError, PixelwallClient, PixelwallError, normalize_host, valid_proof
from .const import CONF_KEY, DASHBOARD_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

KEY_SCHEMA = vol.Schema({vol.Required(CONF_KEY): str})


class PixelwallConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._info: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = normalize_host(user_input[CONF_HOST])
            if self._host is None:
                errors[CONF_HOST] = "invalid_host"
            else:
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
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str, vol.Required(CONF_KEY): str}),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        screen_id = discovery_info.properties.get("id")
        if not screen_id:
            return self.async_abort(reason="not_pixelwall")
        self._host = discovery_info.host
        await self.async_set_unique_id(screen_id)
        # Anything on the network can announce a (public) screen id: the entry only follows a new
        # address that proves it holds the key, otherwise the key would go to whoever announced it.
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, screen_id)
        if entry is not None and entry.data.get(CONF_HOST) != self._host and await self._holds_key(entry.data[CONF_KEY]):
            self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        self._abort_if_unique_id_configured()
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
            key = user_input[CONF_KEY].strip()
            try:
                await self._client(key).state()
            except PixelwallAuthError:
                errors["base"] = "invalid_auth"
            except PixelwallError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_KEY: key})
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

    async def _holds_key(self, key: str) -> bool:
        """Whether the screen at the newly found address knows the key, asked without sending it (firmware 0.13.5+)."""
        nonce = secrets.token_hex(16)
        try:
            info = await self._client().info(nonce)
        except PixelwallError as err:
            _LOGGER.debug("Pixelwall %s announced at %s, but no answer there (%s); keeping its address", self.unique_id, self._host, err)
            return False
        if "proof" not in info:
            _LOGGER.debug("Pixelwall %s announced at %s without proof of its key (firmware before 0.13.5?); keeping its address", self.unique_id, self._host)
            return False
        if info.get("id") == self.unique_id and valid_proof(key, nonce, info["proof"]):
            return True
        _LOGGER.warning("Pixelwall %s announced at %s, but that host does not hold its key; keeping its address", self.unique_id, self._host)
        return False

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
