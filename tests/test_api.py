"""The client against a screen that answers too much or the wrong thing."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.pixelwall.api import MAX_RESPONSE, PixelwallClient, PixelwallError

from .conftest import HOST, KEY, STATE
from .test_init import setup


def client(hass: HomeAssistant, host: str = HOST) -> PixelwallClient:
    return PixelwallClient(async_get_clientsession(hass), host, KEY)


async def test_too_large_answers_are_refused(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"http://{HOST}/api/state", text="{}", headers={"Content-Length": str(MAX_RESPONSE + 1)})
    with pytest.raises(PixelwallError, match="too large"):
        await client(hass).state()

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"http://{HOST}/api/state", text='{"name": "' + "x" * MAX_RESPONSE + '"}')
    with pytest.raises(PixelwallError, match="too large"):
        await client(hass).state()


async def test_malformed_fields_are_dropped(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"http://{HOST}/api/state", json={
        "name": ["Woonkamer"], "brightness": "60", "rssi": True, "update_percent": 42, "updating": "yes", "power": "on",
        "apps": [{"key": "weather", "name": "Weer", "enabled": "no"}, {"name": "no key"}, {"key": 5}, "clock", {"key": "radio", "name": 7}],
    })
    assert await client(hass).state() == {
        "update_percent": 42, "power": "on",
        "apps": [{"key": "weather", "name": "Weer"}, {"key": "radio"}],
    }

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"http://{HOST}/api/state", json={"apps": {"key": "weather"}})
    assert await client(hass).state() == {"apps": []}

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"http://{HOST}/api/state", json=["not", "an", "object"])
    assert await client(hass).state() == {}


async def test_info_needs_an_id(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"http://{HOST}/api/info", json={"id": 12, "name": "Woonkamer"})
    with pytest.raises(PixelwallError, match="no screen id"):
        await client(hass).info()


async def test_entities_survive_a_malformed_state(hass: HomeAssistant, aioclient_mock, entry) -> None:
    await setup(hass, aioclient_mock, entry)
    coordinator = entry.runtime_data

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"http://{HOST}/api/state", json={
        **STATE, "brightness": "max", "updating": True, "update_percent": "half",
        "apps": [{"key": "weather", "name": {"nl": "Weer"}, "enabled": True}, {"name": "Klok"}, None],
    })
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert hass.states.get("light.woonkamer").attributes["brightness"] is None
    assert hass.states.get("select.woonkamer_app").attributes["options"] == []
    assert hass.states.get("switch.woonkamer_weer_in_rotation").state == "on"
    assert hass.states.get("update.woonkamer_firmware").attributes["update_percentage"] is None
