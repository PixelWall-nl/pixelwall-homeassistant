"""Pages: the design goes to the screen once, entity changes follow as values."""
from __future__ import annotations

from datetime import timedelta

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.pixelwall.const import DOMAIN

from .conftest import HOST
from .test_init import calls, setup


async def test_set_page_follows_entities(hass: HomeAssistant, aioclient_mock, entry) -> None:
    hass.config.language = "nl"
    hass.states.async_set("sensor.binnen", "21.43", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.zon", "2140", {"unit_of_measurement": "W"})
    await setup(hass, aioclient_mock, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]

    await hass.services.async_call(DOMAIN, "set_page", {
        "device_id": device.id, "page": "Thuis", "title": "Thuis", "items": [
            {"entity": "sensor.binnen", "label": "Binnen", "icon": "thermometer"},
            {"entity": "sensor.zon", "label": "Zon", "color": [255, 204, 51]},
            {"key": "Afval", "value": "morgen", "label": "GFT"},
        ],
    }, blocking=True)
    assert calls(aioclient_mock, "page")[-1][2] == {
        "page": "thuis", "title": "Thuis", "layout": "grid", "items": [
            {"key": "binnen", "text": "21,4°C", "label": "Binnen", "icon": "thermometer"},
            {"key": "zon", "text": "2140 W", "label": "Zon", "color": "#ffcc33"},
            {"key": "afval", "text": "morgen", "label": "GFT"},
        ],
    }

    hass.states.async_set("sensor.binnen", "21.9", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.zon", "2200", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert calls(aioclient_mock, "values") == [], "waits a moment to bundle changes"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert [c[2] for c in calls(aioclient_mock, "values")] == [
        {"page": "thuis", "values": {"binnen": "21,9°C", "zon": "2200 W", "afval": "morgen"}},
    ]

    hass.states.async_set("sensor.binnen", "unavailable")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    assert calls(aioclient_mock, "values")[-1][2]["values"]["binnen"] == "-"

    await hass.services.async_call(DOMAIN, "set_values", {"device_id": device.id, "page": "thuis", "values": {"afval": "vandaag"}}, blocking=True)
    assert calls(aioclient_mock, "values")[-1][2] == {"page": "thuis", "values": {"afval": "vandaag"}}

    await hass.services.async_call(DOMAIN, "delete_page", {"device_id": device.id, "page": "thuis"}, blocking=True)
    assert calls(aioclient_mock, "page")[-1][2] == {"page": "thuis", "delete": True}
    hass.states.async_set("sensor.zon", "10", {"unit_of_measurement": "W"})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls(aioclient_mock, "values")) == 3, "a deleted page is no longer followed"


async def test_pages_survive_a_restart(hass: HomeAssistant, aioclient_mock, entry, hass_storage) -> None:
    hass_storage[f"pixelwall.pages.{entry.entry_id}"] = {
        "version": 1, "key": f"pixelwall.pages.{entry.entry_id}",
        "data": {"pages": {"co2": {"layout": "value", "title": None, "items": [{"key": "ppm", "entity": "sensor.co2", "label": "CO2"}]}}},
    }
    hass.states.async_set("sensor.co2", "612", {"unit_of_measurement": "ppm"})
    await setup(hass, aioclient_mock, entry)

    assert calls(aioclient_mock, "values")[-1][2] == {"page": "co2", "values": {"ppm": "612 ppm"}}


@pytest.mark.parametrize(("service", "data"), [
    ("set_page", {"page": "x" * 33, "items": [{"value": "1"}]}),
    ("set_page", {"page": "thuis", "items": [{"value": "1", "icon": "i" * 33}]}),
    ("set_page", {"page": "thuis", "items": [{"value": "1", "key": "k" * 33}]}),
    ("set_page", {"page": "thuis", "items": [{"value": "v" * 256}]}),
    ("set_page", {"page": "thuis", "layout": "gauge", "items": [{"value": "1", "min": float("nan")}]}),
    ("set_page", {"page": "thuis", "layout": "gauge", "items": [{"value": "1", "max": "inf"}]}),
    ("delete_page", {"page": "x" * 33}),
    ("delete_page", {"page": ""}),
    ("set_values", {"page": "x" * 33, "values": {"a": "1"}}),
    ("set_values", {"page": "thuis", "values": {"k" * 33: "1"}}),
    ("set_values", {"page": "thuis", "values": {"a": "v" * 256}}),
    ("set_values", {"page": "thuis", "values": {f"k{i}": "1" for i in range(33)}}),
    ("show_message", {"message": "hoi", "icon": "i" * 33}),
])
async def test_service_limits(hass: HomeAssistant, aioclient_mock, entry, service: str, data: dict) -> None:
    await setup(hass, aioclient_mock, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, service, {"device_id": device.id, **data}, blocking=True)
    assert calls(aioclient_mock, "page") == [] and calls(aioclient_mock, "notify") == []


async def test_pages_go_when_the_screen_is_removed(hass: HomeAssistant, aioclient_mock, entry, hass_storage) -> None:
    await setup(hass, aioclient_mock, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    await hass.services.async_call(DOMAIN, "set_page", {"device_id": device.id, "page": "afval", "items": [{"key": "gft", "value": "morgen"}]}, blocking=True)
    assert f"pixelwall.pages.{entry.entry_id}" in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert f"pixelwall.pages.{entry.entry_id}" not in hass_storage
