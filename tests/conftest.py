"""Fixtures: a screen at 192.0.2.10 with key pwk_test."""
from __future__ import annotations

import pytest
from homeassistant.const import CONF_HOST
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pixelwall.const import CONF_KEY, DOMAIN

HOST = "192.0.2.10"
KEY = "pwk_testtesttesttesttesttesttest"
INFO = {"id": "G4HVH8", "model": "hd-wf2", "firmware": "0.9.0", "name": "Woonkamer", "linked": True}
STATE = {
    "id": "G4HVH8",
    "name": "Woonkamer",
    "firmware": "0.9.0",
    "brightness": 60,
    "power": "on",
    "scene": "weather-1",
    "app": "weather",
    "apps": [{"key": "flights", "name": "Vluchten"}, {"key": "weather", "name": "Weer"}, {"key": "clock", "name": "Klok"}],
    "ip": HOST,
    "rssi": -58,
    "online": True,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, unique_id="G4HVH8", title="Woonkamer", data={CONF_HOST: HOST, CONF_KEY: KEY})
