"""Config flow: by address, via zeroconf, and a new key after it was regenerated."""
from __future__ import annotations

from dataclasses import replace
from ipaddress import ip_address

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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


async def test_zeroconf_flow(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"http://{HOST}/api/info", json=INFO)
    aioclient_mock.get(f"http://{HOST}/api/state", json=STATE)
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(HOST),
        ip_addresses=[ip_address(HOST)],
        hostname="pixelwall-g4hvh8.local.",
        name="pixelwall-g4hvh8._pixelwall._tcp.local.",
        port=80,
        type="_pixelwall._tcp.local.",
        properties={"id": "G4HVH8", "model": "hd-wf2", "fw": "0.9.0"},
    )

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_KEY: KEY})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Woonkamer"

    # found again on a new address: the entry follows, no second flow
    aioclient_mock.clear_requests()
    moved = replace(discovery, ip_address=ip_address("192.0.2.11"), ip_addresses=[ip_address("192.0.2.11")])
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=moved)
    assert result["type"] is FlowResultType.ABORT
    assert hass.config_entries.async_entries(DOMAIN)[0].data[CONF_HOST] == "192.0.2.11"


async def test_reauth_with_new_key(hass: HomeAssistant, aioclient_mock, entry) -> None:
    entry.add_to_hass(hass)
    aioclient_mock.get(f"http://{HOST}/api/state", json=STATE)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_KEY: "pwk_new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_KEY] == "pwk_new"
    await hass.async_block_till_done()   # let the reload it triggers finish before teardown
