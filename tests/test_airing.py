"""Airing by hand: switches, floors, services and the dashboard (FR-WIN-07)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import area_registry as ar, floor_registry as fr
import pytest
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.hydronic_heating.const import DOMAIN, EVENT_DECISION

from .test_runtime import _settle, _setup


async def _turn(hass: HomeAssistant, entity_id: str, on: bool = True) -> None:
    await hass.services.async_call(
        "switch", "turn_on" if on else "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await _settle(hass)


async def test_room_airing_switch_and_extension(hass: HomeAssistant) -> None:
    await _setup(hass)
    events = async_capture_events(hass, EVENT_DECISION)
    assert hass.states.get("switch.hh_ventilation").state == "off"
    await _turn(hass, "switch.hh_obyvak_ventilation")
    living = hass.states.get("climate.hh_obyvak").attributes
    assert living["window_state"] == "open_manual"
    assert living["target_reason"] == "ventilation"
    assert living["target_detail"].startswith("Airing (by hand) until ")
    switch = hass.states.get("switch.hh_obyvak_ventilation")
    assert switch.state == "on"
    assert switch.attributes["ends"].startswith("until ")
    assert switch.attributes["source"] == "manual"
    # No floors: the room switch airs only its room; the house switch shows any airing.
    assert hass.states.get("switch.hh_loznice_ventilation").state == "off"
    assert hass.states.get("switch.hh_ventilation").state == "on"
    first = switch.attributes["until"]
    await hass.services.async_call(
        DOMAIN, "ventilate", {"entity_id": "switch.hh_obyvak_ventilation"}, blocking=True
    )
    await _settle(hass)
    assert hass.states.get("switch.hh_obyvak_ventilation").attributes["until"] > first
    logged = [e.data for e in events if e.data["kind"] == "ventilation"]
    assert [e["entity_id"] for e in logged] == ["climate.hh_obyvak"] * 2
    assert logged[0]["message"].startswith("[Shadow] Obývák: airing by hand until ")
    assert logged[1]["message"].startswith("[Shadow] Obývák: airing extended until ")
    await _turn(hass, "switch.hh_ventilation", on=False)
    assert hass.states.get("switch.hh_obyvak_ventilation").state == "off"


async def test_house_airing_and_services(hass: HomeAssistant) -> None:
    await _setup(hass)
    await hass.services.async_call(DOMAIN, "ventilate", {"minutes": 5}, blocking=True)
    await _settle(hass)
    assert hass.states.get("switch.hh_obyvak_ventilation").state == "on"
    assert hass.states.get("switch.hh_loznice_ventilation").state == "on"
    await hass.services.async_call(
        DOMAIN, "stop_ventilation", {"entity_id": "climate.hh_loznice"}, blocking=True
    )
    await _settle(hass)
    assert hass.states.get("switch.hh_loznice_ventilation").state == "off"
    assert hass.states.get("switch.hh_obyvak_ventilation").state == "on"
    hass.states.async_set("input_boolean.cizi", "on")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "ventilate", {"entity_id": "input_boolean.cizi"}, blocking=True
        )


async def test_floor_airing(hass: HomeAssistant) -> None:
    floors = fr.async_get(hass)
    areas = ar.async_get(hass)
    upstairs = floors.async_create("2NP", level=1)
    ground = floors.async_create("1NP", level=0)
    areas.async_create("Ložnice", floor_id=upstairs.floor_id)
    areas.async_create("Obývák", floor_id=ground.floor_id)
    await _setup(hass)
    floor_switch = "switch.hh_ventilation_1np"
    assert hass.states.get(floor_switch).name == "Topení Airing 1NP"
    await _turn(hass, floor_switch)
    assert hass.states.get("switch.hh_obyvak_ventilation").state == "on"
    assert hass.states.get("switch.hh_loznice_ventilation").state == "off"
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    sections = dashboard["views"][0]["sections"]
    headings = [s["cards"][0].get("heading") for s in sections]
    # Rooms by floor in their order, each floor with its airing above its rooms.
    assert headings[-4:] == ["1NP", "Obývák", "2NP", "Ložnice"]
    # The floor section is only its heading; the airing is in its badges.
    floor_cards = sections[headings.index("1NP")]["cards"]
    assert len(floor_cards) == 1
    off, on, more = floor_cards[0]["badges"]
    assert (off["entity"], off["state_content"], off["tap_action"]) == (
        floor_switch,
        "state",
        {"action": "toggle"},
    )
    assert off["visibility"][0]["state"] == "off"
    assert off["hold_action"]["perform_action"] == "hydronic_heating.ventilate"
    assert (on["state_content"], on["visibility"][0]["state"]) == ("ends", "on")
    assert more["icon"] == "mdi:timer-plus-outline"
    assert more["tap_action"]["data"] == {"entity_id": floor_switch}
    # The room cards have no airing tile; the room switch stays as an entity.
    living = sections[headings.index("Obývák")]["cards"]
    assert "switch.hh_obyvak_ventilation" not in str(living)
    scheme = dashboard["views"][1]["sections"][0]["cards"][0]
    assert [(f["name"], f["ventilation"]) for f in scheme["floors"]] == [
        ("2NP", "switch.hh_ventilation_2np"),
        ("1NP", floor_switch),
    ]


async def test_new_floor_reloads_the_entry(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    runtime = entry.runtime_data
    assert hass.states.get("switch.hh_ventilation_2np") is None
    upstairs = fr.async_get(hass).async_create("2NP", level=1)
    ar.async_get(hass).async_create("Ložnice", floor_id=upstairs.floor_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data is not runtime  # reloaded with the floor switch
    assert hass.states.get("switch.hh_ventilation_2np") is not None
