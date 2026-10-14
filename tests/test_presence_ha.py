"""Presence and preheating in Home Assistant (FR-SCH-02, FR-SCH-03)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

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


async def test_czech_preheat_text_and_dashboard_badges(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Noon, so the return in an hour is today (a time after midnight says "zítra").
    freezer.move_to("2026-01-15 11:00:00+00:00")
    hass.config.language = "cs"
    hass.states.async_set("group.rodina", "not_home")
    hass.states.async_set("binary_sensor.dlouho_pryc", "off")
    await _setup(hass, **PRESENCE)
    events = async_capture_events(hass, EVENT_DECISION)
    back = dt_util.utcnow() + timedelta(hours=1)
    hass.states.async_set("sensor.navrat", back.isoformat(), {"device_class": "timestamp"})
    await _settle(hass)
    preheat = [e.data["message"] for e in events if e.data["kind"] == "preheat"]
    local = dt_util.as_local(back)
    clock = f"{local.hour}:{local:%M}"
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
    # The away temperature stays in the room settings, not in the room card.
    rooms = {s["cards"][0].get("heading"): s["cards"] for s in dashboard["views"][0]["sections"]}
    assert "number.hh_obyvak_away" not in str(rooms["Obývák"])
    eco = next(c for c in rooms["Obývák"] if c.get("entity") == "number.hh_obyvak_eco")
    assert eco["name"] == "ECO"
    # The badges of the top bar are explained too, with the same icons.
    assert badges["group.rodina"]["icon"] == "mdi:account-multiple"
    assert badges["binary_sensor.dlouho_pryc"]["icon"] == "mdi:bag-suitcase"
    rows = dashboard["views"][3]["sections"][0]["cards"][1]["content"].replace("\u00a0", " ")
    assert "**Pryč**" not in rows
    assert '<ha-icon icon="mdi:account-multiple"></ha-icon> | **Doma**' in rows
    assert '<ha-icon icon="mdi:bag-suitcase"></ha-icon> | **Dlouhodobě pryč**' in rows


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
    hass.states.async_set("person.elvisek", "home", {"friendly_name": "ElvisEK"})
    hass.states.async_set("person.ronny", "home", {"friendly_name": "Ronny"})
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
    # No text under the thermostat: the reason is in its attributes and the logbook.
    assert all(c["type"] != "markdown" for c in rooms["Obývák"])
    # Who is home: only people (the group stands for its members), by their names.
    operation = rooms["Boiler operation"]
    people = [
        (c["entity"], c["name"])
        for c in operation
        if c.get("state_content") == ["state", "last_changed"]
    ]
    assert people == [("person.elvisek", "ElvisEK"), ("person.ronny", "Ronny")]


async def test_who_is_home_from_a_presence_integration(hass: HomeAssistant) -> None:
    """Groups and counts of a presence integration stand for its people."""
    module = MockConfigEntry(domain="household_presence", title="Domácnost")
    module.add_to_hass(hass)
    devices = dr.async_get(hass)
    registry = er.async_get(hass)

    def sensor(key: str, device: str | None, attributes: dict) -> str:
        device_id = None
        if device is not None:
            device_id = devices.async_get_or_create(
                config_entry_id=module.entry_id,
                identifiers={("household_presence", device)},
                name=device,
            ).id
        entity = registry.async_get_or_create(
            "binary_sensor",
            "household_presence",
            key,
            config_entry=module,
            device_id=device_id,
            has_entity_name=True,
            original_device_class="presence",
            suggested_object_id=f"hp_{key}",
        )
        hass.states.async_set(entity.entity_id, "on", attributes)
        return entity.entity_id

    house = sensor("multiple_home", None, {"count": 2, "people": ["ElvisEK", "Adam"]})
    parents = sensor("rodice_home", "Rodiče", {"count": 1, "people": ["ElvisEK"]})
    elvisek = sensor("elvisek_home", "ElvisEK", {"friendly_name": "ElvisEK Doma"})
    adam = sensor("adam_home", "Adam", {"friendly_name": "Adam Doma"})
    # ElvisEK has the real time of the last change as a timestamp sensor.
    since = registry.async_get_or_create(
        "sensor",
        "household_presence",
        "elvisek_since",
        config_entry=module,
        device_id=registry.async_get(elvisek).device_id,
        has_entity_name=True,
        original_device_class="timestamp",
        translation_key="since",
        suggested_object_id="hp_elvisek_since",
    ).entity_id
    entry = await _setup(hass, **{CONF_HOUSE_PRESENCE_ENTITY: house})
    living = next(s for s in entry.subentries.values() if s.unique_id == "obyvak")
    hass.config_entries.async_update_subentry(
        entry, living, data={**living.data, "presence_entity": parents}
    )
    await _settle(hass)
    dashboard = await hass.services.async_call(
        "hydronic_heating", "generate_dashboard", {}, blocking=True, return_response=True
    )
    operation = dashboard["views"][0]["sections"][2]["cards"]
    people = [(c["entity"], c.get("name")) for c in operation if c.get("color") == "green"]
    assert people == [(elvisek, "ElvisEK"), (adam, "Adam")]
    cards = {c.get("entity"): c for c in operation}
    # With the real time of the change: the state and next to it the time.
    assert cards[elvisek]["state_content"] == ["state"]
    assert (cards[since]["name"], cards[since]["icon"]) == ("Changed", "mdi:clock-outline")
    # Without it the time of the last state change in Home Assistant.
    assert cards[adam]["state_content"] == ["state", "last_changed"]
