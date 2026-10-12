"""Presence and preheating in Home Assistant (FR-SCH-02, FR-SCH-03)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
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
