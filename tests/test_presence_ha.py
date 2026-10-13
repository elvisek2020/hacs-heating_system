"""Presence and preheating in Home Assistant (FR-SCH-02, FR-SCH-03)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.hydronic_heating.const import (
    CONF_EXPECTED_RETURN_ENTITY,
    CONF_HOUSE_PRESENCE_ENTITY,
    CONF_HOUSE_SCHEDULE_ENTITY,
    CONF_LONG_AWAY_ENTITY,
    EVENT_DECISION,
)

from .test_runtime import _settle, _setup

PRESENCE = {
    CONF_HOUSE_PRESENCE_ENTITY: "group.rodina",
    CONF_LONG_AWAY_ENTITY: "binary_sensor.dlouho_pryc",
    CONF_EXPECTED_RETURN_ENTITY: "sensor.navrat",
}


async def test_presence_lowers_rooms_and_preheats(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-01-15 11:00:00+00:00")
    hass.states.async_set("group.rodina", "home")
    hass.states.async_set("binary_sensor.dlouho_pryc", "off")
    hass.states.async_set("sensor.navrat", "unknown", {"device_class": "timestamp"})
    await _setup(hass, **PRESENCE)
    assert hass.states.get("climate.hh_obyvak").attributes["temperature"] == 21.0
    assert hass.states.get("climate.hh_system").attributes["presence"] == "home"

    events = async_capture_events(hass, EVENT_DECISION)
    hass.states.async_set("group.rodina", "not_home")
    await _settle(hass)
    living = hass.states.get("climate.hh_obyvak")
    assert living.attributes["temperature"] == 19.0
    assert living.attributes["preset_mode"] == "eco"
    assert hass.states.get("climate.hh_system").attributes["presence"] == "absent"
    presence = [e.data for e in events if e.data["kind"] == "presence"]
    assert presence[0]["message"] == "[Shadow] Nobody home: rooms in auto use the setback."
    assert presence[0]["entity_id"] == "climate.hh_system"

    # Somebody is expected back in an hour: the cold living room preheats at once.
    back = dt_util.utcnow() + timedelta(hours=1)
    hass.states.async_set("sensor.navrat", back.isoformat(), {"device_class": "timestamp"})
    await _settle(hass)
    living = hass.states.get("climate.hh_obyvak")
    assert living.attributes["preheating"] is True
    assert living.attributes["temperature"] == 21.0
    assert living.attributes["heat_rate_k_h"] == 0.5
    preheat = [e.data for e in events if e.data["kind"] == "preheat"]
    assert len(preheat) == 1
    assert preheat[0]["entity_id"] == "climate.hh_obyvak"
    assert preheat[0]["message"].startswith("[Shadow] Preheating: Obývák to 21 °C by ")
    # The warm bedroom needs only the valve and boiler start time.
    bedroom = hass.states.get("climate.hh_loznice")
    assert bedroom.attributes["preheating"] is False
    assert bedroom.attributes["preheat_planned"] is not None


async def test_long_absence_sets_away_state(hass: HomeAssistant) -> None:
    hass.states.async_set("group.rodina", "not_home")
    hass.states.async_set("binary_sensor.dlouho_pryc", "off")
    await _setup(hass, **PRESENCE)
    events = async_capture_events(hass, EVENT_DECISION)
    hass.states.async_set("binary_sensor.dlouho_pryc", "on")
    await _settle(hass)
    assert hass.states.get("sensor.hh_state").state == "away"
    assert hass.states.get("select.hh_system_mode").state == "auto"
    assert hass.states.get("climate.hh_obyvak").attributes["temperature"] == 15.0
    messages = [e.data["message"] for e in events if e.data["kind"] == "presence"]
    assert messages == ["[Shadow] Long absence: the whole house uses the away temperatures."]


async def test_czech_preheat_text_and_dashboard_badges(hass: HomeAssistant) -> None:
    hass.config.language = "cs"
    hass.states.async_set("group.rodina", "not_home")
    hass.states.async_set("binary_sensor.dlouho_pryc", "off")
    await _setup(hass, **PRESENCE)
    events = async_capture_events(hass, EVENT_DECISION)
    back = dt_util.utcnow() + timedelta(hours=1)
    hass.states.async_set("sensor.navrat", back.isoformat(), {"device_class": "timestamp"})
    await _settle(hass)
    preheat = [e.data["message"] for e in events if e.data["kind"] == "preheat"]
    clock = dt_util.as_local(back).strftime("%H:%M")
    assert preheat == [
        f"[Shadow] Předtápění: Obývák na 21 °C do {clock} (očekávaný návrat), "
        "rychlost ohřevu 0,5 K/h."
    ]
    dashboard = await hass.services.async_call(
        "hydronic_heating", "generate_dashboard", {}, blocking=True, return_response=True
    )
    badges = {b["entity"]: b for b in dashboard["views"][0]["badges"]}
    assert badges["group.rodina"]["name"] == "Doma"
    assert badges["binary_sensor.dlouho_pryc"]["visibility"][0]["state"] == "on"


async def test_house_schedule_in_rooms_and_dashboard(hass: HomeAssistant) -> None:
    hass.states.async_set("schedule.dum", "off")
    await _setup(hass, **{CONF_HOUSE_SCHEDULE_ENTITY: "schedule.dum"})
    living = hass.states.get("climate.hh_obyvak")
    assert living.attributes["schedule_entity"] == "schedule.dum"
    assert living.attributes["temperature"] == 19.0
    hass.states.async_set("schedule.dum", "on")
    await _settle(hass)
    assert hass.states.get("climate.hh_obyvak").attributes["temperature"] == 21.0
    dashboard = await hass.services.async_call(
        "hydronic_heating", "generate_dashboard", {}, blocking=True, return_response=True
    )
    system = dashboard["views"][0]["sections"][0]["cards"]
    tile = next(c for c in system if c.get("entity") == "schedule.dum")
    assert tile["name"] == "House schedule"
    assert tile["state_content"] == ["state", "next_event"]


async def test_room_shows_what_it_follows(hass: HomeAssistant) -> None:
    """Presence group with members, schedule and the reason of the target."""
    hass.states.async_set(
        "binary_sensor.rodice_doma",
        "on",
        {"entity_id": ["person.elvisek", "person.ronny"], "friendly_name": "Rodiče doma"},
    )
    hass.states.async_set("person.elvisek", "home")
    hass.states.async_set("person.ronny", "home")
    hass.states.async_set(
        "binary_sensor.nekdo_doma",
        "on",
        {"people": ["Zdeněk", "Adam"], "friendly_name": "Někdo doma"},
    )
    hass.states.async_set("schedule.dum", "on", {"friendly_name": "Topení dům"})
    entry = await _setup(
        hass,
        **{
            CONF_HOUSE_PRESENCE_ENTITY: "binary_sensor.nekdo_doma",
            CONF_HOUSE_SCHEDULE_ENTITY: "schedule.dum",
        },
    )
    kitchen = next(s for s in entry.subentries.values() if s.unique_id == "obyvak")
    hass.config_entries.async_update_subentry(
        entry, kitchen, data={**kitchen.data, "presence_entity": "binary_sensor.rodice_doma"}
    )
    await _settle(hass)
    living = hass.states.get("climate.hh_obyvak").attributes
    assert living["presence_entity"] == "binary_sensor.rodice_doma"
    assert living["presence_source"] == "room"
    assert living["target_reason"] == "schedule_comfort"
    assert living["target_detail"] == "Comfort 21 °C by schedule (Topení dům)."
    bedroom = hass.states.get("climate.hh_loznice").attributes
    assert bedroom["presence_source"] == "house"

    events = async_capture_events(hass, EVENT_DECISION)
    hass.states.async_set(
        "binary_sensor.rodice_doma",
        "off",
        {"entity_id": ["person.elvisek", "person.ronny"], "friendly_name": "Rodiče doma"},
    )
    await _settle(hass)
    living = hass.states.get("climate.hh_obyvak").attributes
    assert living["target_reason"] == "absent"
    assert living["target_detail"] == "Setback 19 °C: nobody home (Rodiče doma)."
    logged = [e.data for e in events if e.data["kind"] == "room_target"]
    assert logged[0]["entity_id"] == "climate.hh_obyvak"
    assert logged[0]["message"] == ("[Shadow] Obývák: setback 19 °C, nobody home (Rodiče doma).")

    dashboard = await hass.services.async_call(
        "hydronic_heating", "generate_dashboard", {}, blocking=True, return_response=True
    )
    sections = dashboard["views"][0]["sections"]
    rooms = {s["cards"][0].get("heading"): s["cards"] for s in sections}
    living_cards = rooms["Obývák"]
    explanation = living_cards[2]["content"]
    assert "state_attr('climate.hh_obyvak', 'target_detail')" in explanation
    assert "**Home:**" in explanation
    assert "state_attr('binary_sensor.rodice_doma', 'entity_id')" in explanation
    assert "**House schedule:**" in explanation
    # Who is home: the people behind the presence entities, under the boiler operation.
    operation = rooms["Boiler operation"]
    people = [c["entity"] for c in operation if c.get("state_content") == ["state", "last_changed"]]
    assert people == ["binary_sensor.nekdo_doma", "person.elvisek", "person.ronny"]
    bedroom = rooms["Ložnice"][2]["content"]
    assert "**Home in the house:**" in bedroom
    assert "state_attr('binary_sensor.nekdo_doma', 'people')" in bedroom

    # The names come out of the templates as the frontend renders them.
    hass.states.async_set(
        "binary_sensor.rodice_doma",
        "on",
        {"entity_id": ["person.elvisek", "person.ronny"], "friendly_name": "Rodiče doma"},
    )
    hass.states.async_set("person.ronny", "not_home", {"friendly_name": "Ronny"})
    hass.states.async_set("person.elvisek", "home", {"friendly_name": "ElvisEK"})
    names = Template(explanation.split("**Home:** ", 1)[1].split("  \n")[0], hass)
    assert names.async_render() == "ElvisEK"
    names = Template(bedroom.split("**Home in the house:** ", 1)[1].split("  \n")[0], hass)
    assert names.async_render() == "Zdeněk, Adam"
