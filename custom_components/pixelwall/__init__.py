"""Pixelwall: control a Pixelwall LED screen on your network and send it messages."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import PixelwallClient
from .const import (
    ATTR_COLOR,
    ATTR_DEVICE_ID,
    ATTR_DURATION,
    ATTR_ICON,
    ATTR_MESSAGE,
    ATTR_TITLE,
    CONF_KEY,
    DOMAIN,
    SERVICE_SHOW_MESSAGE,
)
from .coordinator import PixelwallConfigEntry, PixelwallCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.LIGHT, Platform.NOTIFY, Platform.SELECT, Platform.SENSOR, Platform.SWITCH, Platform.UPDATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SHOW_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_MESSAGE): vol.All(cv.string, vol.Length(min=1, max=200)),
        vol.Optional(ATTR_TITLE): vol.All(cv.string, vol.Length(max=60)),
        vol.Optional(ATTR_ICON): cv.string,
        vol.Optional(ATTR_COLOR): vol.Any(
            vol.All(cv.string, vol.Match(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$")),
            vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)), lambda rgb: "#{:02x}{:02x}{:02x}".format(*rgb)),
        ),
        vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=3, max=600)),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def show_message(call: ServiceCall) -> None:
        registry = dr.async_get(hass)
        for device_id in call.data[ATTR_DEVICE_ID]:
            device = registry.async_get(device_id)
            entry = next(
                (
                    e
                    for e in hass.config_entries.async_loaded_entries(DOMAIN)
                    if device is not None and e.entry_id in device.config_entries
                ),
                None,
            )
            if entry is None or entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_device")
            coordinator: PixelwallCoordinator = entry.runtime_data
            await coordinator.run(
                coordinator.client.notify(
                    call.data[ATTR_MESSAGE],
                    title=call.data.get(ATTR_TITLE),
                    icon=call.data.get(ATTR_ICON),
                    color=call.data.get(ATTR_COLOR),
                    duration=call.data.get(ATTR_DURATION),
                )
            )

    hass.services.async_register(DOMAIN, SERVICE_SHOW_MESSAGE, show_message, schema=SHOW_MESSAGE_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry) -> bool:
    client = PixelwallClient(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_KEY])
    coordinator = PixelwallCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PixelwallConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
