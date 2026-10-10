"""Config flow: by address, via zeroconf, and a new key after it was regenerated."""
from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import replace
from ipaddress import ip_address

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

from custom_components.pixelwall.const import CONF_KEY, DOMAIN

from .conftest import HOST, INFO, KEY, STATE


async def test_user_flow(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"http://{HOST}/api/info", json=INFO)
    aioclient_mock.get(f"http://{HOST}/api/state", json=STATE)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: f"http://{HOST}/", CONF_KEY: f" {KEY} "})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Woonkamer"
    assert result["data"] == {CONF_HOST: HOST, CONF_KEY: KEY}
    assert result["result"].unique_id == "G4HVH8"
    assert aioclient_mock.mock_calls[-1][3] == {"X-Pixelwall-Key": KEY}


async def test_user_flow_wrong_key_and_unreachable(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"http://{HOST}/api/info", json=INFO)
    aioclient_mock.get(f"http://{HOST}/api/state", status=401, json={"error": "invalid key"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_KEY: "nope"})
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get("http://192.0.2.99/api/info", exc=TimeoutError())
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.0.2.99", CONF_KEY: KEY})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_refuses_odd_addresses(hass: HomeAssistant, aioclient_mock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    for host in ("https://192.0.2.10", "192.0.2.10/api?x=1", "user@evil.example"):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: host, CONF_KEY: KEY})
        assert result["errors"] == {CONF_HOST: "invalid_host"}
    assert aioclient_mock.call_count == 0, "nothing is sent to an address that isn't one"

    aioclient_mock.get(f"http://{HOST}/api/info", json={"name": "No id"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_KEY: KEY})
    assert result["errors"] == {"base": "cannot_connect"}


DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(HOST),
    ip_addresses=[ip_address(HOST)],
    hostname="pixelwall-g4hvh8.local.",
    name="pixelwall-g4hvh8._pixelwall._tcp.local.",
    port=80,
    type="_pixelwall._tcp.local.",
    properties={"id": "G4HVH8", "model": "hd-wf2", "fw": "0.9.0"},
)
MOVED = replace(DISCOVERY, ip_address=ip_address("192.0.2.11"), ip_addresses=[ip_address("192.0.2.11")])


def proving(key: str, screen_id: str = "G4HVH8"):
    """/api/info of firmware 0.13.5+: proof = HMAC-SHA256(key, "pixelwall-proof:" + nonce)."""
    async def answer(method, url, data):
        nonce = url.query["nonce"]
        assert len(nonce) == 32 and all(c in "0123456789abcdef" for c in nonce)
        proof = hmac.new(key.encode(), f"pixelwall-proof:{nonce}".encode(), hashlib.sha256).hexdigest()
        return AiohttpClientMockResponse(method, url, json={**INFO, "id": screen_id, "proof": proof})
    return answer


async def test_zeroconf_flow(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"http://{HOST}/api/info", json=INFO)
    aioclient_mock.get(f"http://{HOST}/api/state", json=STATE)
    discovery = DISCOVERY

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_KEY: KEY})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Woonkamer"

    # found again on the same address: nothing to ask
    aioclient_mock.clear_requests()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery)
    assert result["reason"] == "already_configured"
    assert aioclient_mock.call_count == 0


async def test_zeroconf_follows_a_new_address_that_proves_the_key(hass: HomeAssistant, aioclient_mock, entry) -> None:
    entry.add_to_hass(hass)
    aioclient_mock.get("http://192.0.2.11/api/info", side_effect=proving(KEY))

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=MOVED)
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.11"
    assert [c[3] for c in aioclient_mock.mock_calls] == [{}], "the key itself never goes to the new address"
    await hass.async_block_till_done()   # let the reload it triggers finish before teardown


@pytest.mark.parametrize("answer", [
    {"json": INFO},                                                         # firmware before 0.13.5: no proof
    {"side_effect": proving("pwk_someoneelse")},                            # proof with another key
    {"side_effect": proving(KEY, screen_id="OTHER1")},                      # a proof for another screen
    {"json": {**INFO, "proof": "nope"}},
    {"json": {**INFO, "proof": "ü" * 64}},
    {"exc": TimeoutError()},
])
async def test_zeroconf_keeps_the_address_without_proof(hass: HomeAssistant, aioclient_mock, entry, caplog, answer) -> None:
    entry.add_to_hass(hass)
    aioclient_mock.get("http://192.0.2.11/api/info", **answer)
    caplog.set_level(logging.DEBUG)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=MOVED)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST
    assert all(c[3] == {} for c in aioclient_mock.mock_calls)
    assert "keeping its address" in caplog.text
    assert KEY not in caplog.text


async def test_reauth_with_new_key(hass: HomeAssistant, aioclient_mock, entry) -> None:
    entry.add_to_hass(hass)
    aioclient_mock.get(f"http://{HOST}/api/state", json=STATE)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_KEY: " pwk_new\n"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_KEY] == "pwk_new"
    assert aioclient_mock.mock_calls[0][3] == {"X-Pixelwall-Key": "pwk_new"}, "tested the key as it is stored"
    await hass.async_block_till_done()   # let the reload it triggers finish before teardown
