"""Animated scheme: data on the boiler reason, the view and the card (FR-UI-25)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.hydronic_heating.card import (
    CARD_FILE,
    CARD_URL,
    async_register_card,
    async_unregister_card,
)
from custom_components.hydronic_heating.const import DOMAIN
from custom_components.hydronic_heating.sensor import BoilerReasonSensor

from .test_runtime import _settle, _setup


async def test_reason_says_what_happens_now_and_next(hass: HomeAssistant) -> None:
    hass.config.language = "cs"
    await _setup(hass)
    await _settle(hass)
    attrs = hass.states.get("sensor.hh_boiler_reason").attributes
    assert attrs["now"][0] == attrs["detail"]
    assert attrs["now"][1].startswith("Teplo chtějí: Obývák (")
    assert isinstance(attrs["upcoming"], list)
    # Texts of every step stay out of the history.
    assert {"now", "upcoming"} <= BoilerReasonSensor._unrecorded_attributes


async def test_scheme_view_groups_rooms_by_floor(hass: HomeAssistant) -> None:
    floors = fr.async_get(hass)
    areas = ar.async_get(hass)
    upstairs = floors.async_create("2NP", level=1)
    ground = floors.async_create("1NP", level=0)
    areas.async_create("Ložnice", floor_id=upstairs.floor_id)
    living = areas.async_create("Obývací pokoj", floor_id=ground.floor_id)
    await _setup(hass)
    # Obývák by the area of its device, Ložnice by an area of the same name.
    entry = er.async_get(hass).async_get("climate.hh_obyvak")
    dr.async_get(hass).async_update_device(entry.device_id, area_id=living.id)
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    view = dashboard["views"][1]
    assert (view["path"], view["type"]) == ("schema", "sections")
    card = view["sections"][0]["cards"][0]
    assert card["type"] == "custom:hydronic-heating-flow-card"
    assert card["boiler"] == "binary_sensor.hh_boiler_command"
    assert card["reason"] == "sensor.hh_boiler_reason"
    assert "actual" not in card  # no feedback configured
    assert card["shadow"] == "switch.hh_shadow_mode"
    assert "demo" not in card
    assert [(f["name"], [r["name"] for r in f["rooms"]]) for f in card["floors"]] == [
        ("2NP", ["Ložnice"]),
        ("1NP", ["Obývák"]),
    ]
    assert card["floors"][1]["rooms"][0] == {
        "name": "Obývák",
        "climate": "climate.hh_obyvak",
        "demand": "sensor.hh_obyvak_demand",
        "valve": "sensor.hh_obyvak_valve_state",
        "problem": "binary_sensor.hh_obyvak_problem",
    }


async def test_rooms_without_floor_share_one_row(hass: HomeAssistant) -> None:
    await _setup(hass)
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    floors = dashboard["views"][1]["sections"][0]["cards"][0]["floors"]
    assert [(f["name"], len(f["rooms"])) for f in floors] == [("", 2)]


async def test_card_is_served_and_loaded_with_the_version(hass: HomeAssistant) -> None:
    """Without resources in storage the card is added to every page."""
    assert CARD_FILE.is_file()
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    with patch("custom_components.hydronic_heating.card.add_extra_js_url") as add_js:
        await async_register_card(hass)
    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert (paths[0].url_path, paths[0].path, paths[0].cache_headers) == (
        CARD_URL,
        str(CARD_FILE),
        True,
    )
    url = add_js.call_args.args[1]
    assert url.startswith(f"{CARD_URL}?v=")


async def _lovelace(hass: HomeAssistant):
    """Lovelace with its resources in storage, and the version of the integration."""
    assert await async_setup_component(hass, "lovelace", {})
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    version = (await async_get_integration(hass, DOMAIN)).version
    return hass.data[LOVELACE_DATA].resources, f"{CARD_URL}?v={version}"


def _cards(resources) -> list[dict]:
    return [r for r in resources.async_items() if r["url"].startswith(CARD_URL)]


async def test_card_is_a_lovelace_resource(hass: HomeAssistant) -> None:
    """A resource loads before the dashboard renders, an extra module may come late."""
    resources, url = await _lovelace(hass)
    with patch("custom_components.hydronic_heating.card.add_extra_js_url") as add_js:
        await async_register_card(hass)
        await async_register_card(hass)
    add_js.assert_not_called()
    assert [(r["type"], r["url"]) for r in _cards(resources)] == [("module", url)]


async def test_resource_follows_the_version_and_goes_with_the_integration(
    hass: HomeAssistant,
) -> None:
    resources, url = await _lovelace(hass)
    other = await resources.async_create_item({"res_type": "module", "url": "/local/x.js"})
    await resources.async_create_item({"res_type": "js", "url": f"{CARD_URL}?v=0.18.0"})
    await resources.async_create_item({"res_type": "module", "url": f"{CARD_URL}?v=0.19.0"})
    await async_register_card(hass)
    assert [(r["type"], r["url"]) for r in _cards(resources)] == [("module", url)]

    await async_unregister_card(hass)
    assert _cards(resources) == []
    assert [r["id"] for r in resources.async_items()] == [other["id"]]


async def test_removing_the_integration_removes_the_resource(hass: HomeAssistant) -> None:
    resources, url = await _lovelace(hass)
    entry = await _setup(hass)
    assert [r["url"] for r in _cards(resources)] == [url]
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert _cards(resources) == []


async def test_stored_resources_are_loaded_and_tidied(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Resources saved before the start: the old one is updated in place."""
    hass_storage["lovelace_resources"] = {
        "version": 1,
        "key": "lovelace_resources",
        "data": {
            "items": [
                {"id": "other", "type": "module", "url": "/local/x.js"},
                {"id": "old", "type": "js", "url": f"{CARD_URL}?v=0.18.0"},
                {"id": "copy", "type": "module", "url": CARD_URL},
            ]
        },
    }
    resources, url = await _lovelace(hass)
    await async_register_card(hass)
    items = {r["id"]: (r["type"], r["url"]) for r in resources.async_items()}
    assert items == {"other": ("module", "/local/x.js"), "old": ("module", url)}
    await async_register_card(hass)
    assert {r["id"] for r in resources.async_items()} == {"other", "old"}


async def test_valve_state_tells_the_card_about_flow_and_travel(hass: HomeAssistant) -> None:
    await _setup(hass)
    await _settle(hass)
    attrs = hass.states.get("sensor.hh_obyvak_valve_state").attributes
    assert {"last_flow", "moving_since", "moving_until"} <= set(attrs)
    assert hass.states.get("sensor.hh_obyvak_demand").attributes["call_threshold"] == 50
