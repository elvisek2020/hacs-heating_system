"""Animated scheme: data on the boiler reason, the view and the card (FR-UI-25)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)

from custom_components.hydronic_heating.card import CARD_FILE, CARD_URL, async_register_card
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
    assert [(f["name"], [r["name"] for r in f["rooms"]]) for f in card["floors"]] == [
        ("2NP", ["Ložnice"]),
        ("1NP", ["Obývák"]),
    ]
    assert card["floors"][1]["rooms"][0] == {
        "name": "Obývák",
        "climate": "climate.hh_obyvak",
        "demand": "sensor.hh_obyvak_demand",
        "valve": "sensor.hh_obyvak_valve_state",
    }


async def test_rooms_without_floor_share_one_row(hass: HomeAssistant) -> None:
    await _setup(hass)
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    floors = dashboard["views"][1]["sections"][0]["cards"][0]["floors"]
    assert [(f["name"], len(f["rooms"])) for f in floors] == [("", 2)]


async def test_card_is_served_and_loaded_with_the_version(hass: HomeAssistant) -> None:
    assert CARD_FILE.is_file()
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    with patch("custom_components.hydronic_heating.card.add_extra_js_url") as add_js:
        await async_register_card(hass)
    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert (paths[0].url_path, paths[0].path) == (CARD_URL, str(CARD_FILE))
    url = add_js.call_args.args[1]
    assert url.startswith(f"{CARD_URL}?v=")
