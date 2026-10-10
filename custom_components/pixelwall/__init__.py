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
    ATTR_ITEMS,
    ATTR_LAYOUT,
    ATTR_MESSAGE,
    ATTR_PAGE,
    ATTR_TITLE,
    ATTR_VALUES,
    CONF_KEY,
    DOMAIN,
    SERVICE_DELETE_PAGE,
    SERVICE_SET_PAGE,
    SERVICE_SET_VALUES,
    SERVICE_SHOW_MESSAGE,
)
from .coordinator import PixelwallConfigEntry, PixelwallCoordinator
from .pages import LAYOUTS, MAX_ITEMS

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.LIGHT, Platform.NOTIFY, Platform.SELECT, Platform.SENSOR, Platform.SWITCH, Platform.UPDATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

COLOR = vol.Any(
    vol.All(cv.string, vol.Match(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$")),
    vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)), lambda rgb: "#{:02x}{:02x}{:02x}".format(*rgb)),
)
DEVICES = vol.All(cv.ensure_list, [cv.string])
ICON = vol.All(cv.string, vol.Length(max=32))
PAGE = vol.All(cv.string, vol.Length(min=1, max=32))
ITEM_KEY = vol.All(cv.string, vol.Length(min=1, max=32))
# A gauge's ends: a number, not nan or inf (those don't survive the trip as JSON).
BOUND = vol.All(vol.Coerce(float), vol.Range(min=-1e9, max=1e9))
# set_values: a page has at most six items; this leaves room for old keys without letting a template flood the screen.
MAX_VALUES = 32
TEXT = vol.All(cv.string, vol.Length(max=255))

SHOW_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): DEVICES,
        vol.Required(ATTR_MESSAGE): vol.All(cv.string, vol.Length(min=1, max=200)),
        vol.Optional(ATTR_TITLE): vol.All(cv.string, vol.Length(max=60)),
        vol.Optional(ATTR_ICON): ICON,
        vol.Optional(ATTR_COLOR): COLOR,
        vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=3, max=600)),
    }
)

ITEM_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional("key"): ITEM_KEY,
            vol.Optional("label"): vol.All(cv.string, vol.Length(max=24)),
            vol.Optional("entity"): cv.entity_id,
            vol.Optional("value"): vol.Any(TEXT, vol.Coerce(float)),
            vol.Optional("unit"): vol.All(cv.string, vol.Length(max=8)),
            vol.Optional(ATTR_ICON): ICON,
            vol.Optional(ATTR_COLOR): COLOR,
            vol.Optional("min"): BOUND,
            vol.Optional("max"): BOUND,
        }
    ),
    cv.has_at_least_one_key("entity", "value"),
)

SET_PAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): DEVICES,
        vol.Required(ATTR_PAGE): PAGE,
        vol.Optional(ATTR_LAYOUT, default="grid"): vol.In(LAYOUTS),
        vol.Optional(ATTR_TITLE): vol.All(cv.string, vol.Length(max=40)),
        vol.Required(ATTR_ITEMS): vol.All(cv.ensure_list, vol.Length(min=1, max=MAX_ITEMS), [ITEM_SCHEMA]),
    }
)

DELETE_PAGE_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): DEVICES, vol.Required(ATTR_PAGE): PAGE})

SET_VALUES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): DEVICES,
        vol.Required(ATTR_PAGE): PAGE,
        vol.Required(ATTR_VALUES): vol.All(
            {ITEM_KEY: TEXT},
            vol.Length(max=MAX_VALUES),
        ),
    }
)


def _coordinators(hass: HomeAssistant, call: ServiceCall) -> list[PixelwallCoordinator]:
    """The screens a service call names (device_id)."""
    registry = dr.async_get(hass)
    found = []
    for device_id in call.data[ATTR_DEVICE_ID]:
        device = registry.async_get(device_id)
        entry = next(
            (e for e in hass.config_entries.async_loaded_entries(DOMAIN) if device is not None and e.entry_id in device.config_entries),
            None,
        )
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_device")
        found.append(entry.runtime_data)
    return found


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def show_message(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.run(
                coordinator.client.notify(
                    call.data[ATTR_MESSAGE],
                    title=call.data.get(ATTR_TITLE),
                    icon=call.data.get(ATTR_ICON),
                    color=call.data.get(ATTR_COLOR),
                    duration=call.data.get(ATTR_DURATION),
                )
            )

    async def set_page(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.run(coordinator.pages.set_page(call.data[ATTR_PAGE], call.data[ATTR_LAYOUT], call.data.get(ATTR_TITLE), call.data[ATTR_ITEMS]))

    async def delete_page(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.run(coordinator.pages.delete_page(call.data[ATTR_PAGE]))

    async def set_values(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass, call):
            await coordinator.run(coordinator.pages.set_values(call.data[ATTR_PAGE], call.data[ATTR_VALUES]))

    hass.services.async_register(DOMAIN, SERVICE_SHOW_MESSAGE, show_message, schema=SHOW_MESSAGE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_PAGE, set_page, schema=SET_PAGE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_PAGE, delete_page, schema=DELETE_PAGE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_VALUES, set_values, schema=SET_VALUES_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PixelwallConfigEntry) -> bool:
    client = PixelwallClient(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_KEY])
    coordinator = PixelwallCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.pages.async_load()
    entry.async_on_unload(coordinator.pages.async_unload)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PixelwallConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
