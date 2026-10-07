"""Entities and the show_message service against a mocked screen."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.pixelwall.const import DOMAIN

from .conftest import HOST, STATE


async def setup(hass: HomeAssistant, aioclient_mock, entry) -> None:
    for path in ("brightness", "power", "next", "previous", "auto", "show", "notify"):
        aioclient_mock.post(f"http://{HOST}/api/{path}", json=STATE)
    aioclient_mock.get(f"http://{HOST}/api/state", json=STATE)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def calls(aioclient_mock, path: str) -> list:
    return [c for c in aioclient_mock.mock_calls if c[1].path == f"/api/{path}"]


async def test_entities(hass: HomeAssistant, aioclient_mock, entry) -> None:
    await setup(hass, aioclient_mock, entry)
    assert entry.state is ConfigEntryState.LOADED

    light = hass.states.get("light.woonkamer")
    assert light.state == "on"
    assert light.attributes["brightness"] == 153
    app = hass.states.get("select.woonkamer_app")
    assert app.state == "Weer"
    assert app.attributes["options"] == ["Vluchten", "Weer", "Klok"]
    assert hass.states.get("binary_sensor.woonkamer_connected_to_pixelwall_nl").state == "on"

    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    assert (device.name, device.sw_version) == ("Woonkamer", "0.9.0")


async def test_commands(hass: HomeAssistant, aioclient_mock, entry) -> None:
    await setup(hass, aioclient_mock, entry)

    await hass.services.async_call("light", "turn_on", {"entity_id": "light.woonkamer", "brightness": 51}, blocking=True)
    assert calls(aioclient_mock, "brightness")[-1][1].query["value"] == "20"
    await hass.services.async_call("light", "turn_off", {"entity_id": "light.woonkamer"}, blocking=True)
    assert calls(aioclient_mock, "power")[-1][1].query["state"] == "off"
    await hass.services.async_call("button", "press", {"entity_id": "button.woonkamer_next_app"}, blocking=True)
    assert len(calls(aioclient_mock, "next")) == 1
    await hass.services.async_call("select", "select_option", {"entity_id": "select.woonkamer_app", "option": "Vluchten"}, blocking=True)
    assert calls(aioclient_mock, "show")[-1][2] == {"app": "flights"}


async def test_messages(hass: HomeAssistant, aioclient_mock, entry) -> None:
    await setup(hass, aioclient_mock, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]

    await hass.services.async_call(
        DOMAIN,
        "show_message",
        {"device_id": device.id, "message": "Er staat iemand voor de deur", "title": "Deurbel", "icon": "bell", "color": [255, 200, 0], "duration": 20},
        blocking=True,
    )
    assert calls(aioclient_mock, "notify")[-1][2] == {
        "message": "Er staat iemand voor de deur",
        "title": "Deurbel",
        "icon": "bell",
        "color": "#ffc800",
        "duration": 20,
    }

    await hass.services.async_call("notify", "send_message", {"entity_id": "notify.woonkamer_message", "message": "Wasmachine klaar", "title": "Was"}, blocking=True)
    assert calls(aioclient_mock, "notify")[-1][2] == {"message": "Wasmachine klaar", "title": "Was"}


async def test_regenerated_key_starts_reauth(hass: HomeAssistant, aioclient_mock, entry) -> None:
    aioclient_mock.get(f"http://{HOST}/api/state", status=401, json={"error": "invalid key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(flow["context"]["source"] == "reauth" for flow in hass.config_entries.flow.async_progress())
