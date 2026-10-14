"""Integration tests: runtime, entities and services in Home Assistant."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hydronic_heating.const import (
    CONF_COMFORT_TEMP,
    CONF_FLOW_TEMP_ENTITY,
    CONF_HAS_BYPASS,
    CONF_HEAT_SOURCE_ENTITY,
    CONF_MIRROR_TIMER_ENTITY,
    CONF_ROOM_NAME,
    CONF_SENSORS,
    CONF_SHADOW_MODE,
    CONF_VALVES,
    DEFAULT_OPTIONS,
    DEFAULT_ROOM,
    DOMAIN,
    SUBENTRY_ROOM,
)
from custom_components.hydronic_heating.diagnostics import (
    async_get_config_entry_diagnostics,
)

CELSIUS = {"unit_of_measurement": "°C", "device_class": "temperature"}


def _room(name: str, slug: str) -> ConfigSubentryData:
    return ConfigSubentryData(
        data={
            **DEFAULT_ROOM,
            CONF_ROOM_NAME: name,
            CONF_SENSORS: [f"sensor.{slug}"],
            CONF_VALVES: [
                {
                    "entity_id": f"input_boolean.hlavice_{slug}",
                    "normally_open": True,
                    "valve_open_time": 120,
                    "valve_close_time": 120,
                }
            ],
        },
        subentry_type=SUBENTRY_ROOM,
        title=name,
        unique_id=slug,
    )


async def _setup(hass: HomeAssistant, **options: Any) -> MockConfigEntry:
    await async_setup_component(
        hass,
        "input_boolean",
        {"input_boolean": {"kotel": None, "hlavice_obyvak": None, "hlavice_loznice": None}},
    )
    await async_setup_component(hass, "timer", {"timer": {"manual": None}})
    hass.states.async_set("sensor.obyvak", "19.0", CELSIUS)
    hass.states.async_set("sensor.loznice", "22.5", CELSIUS)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Topení",
        data={},
        options={
            **DEFAULT_OPTIONS,
            CONF_HEAT_SOURCE_ENTITY: "input_boolean.kotel",
            CONF_HAS_BYPASS: True,
            **options,
        },
        subentries_data=[_room("Obývák", "obyvak"), _room("Ložnice", "loznice")],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _settle(hass: HomeAssistant) -> None:
    await hass.async_block_till_done(wait_background_tasks=True)


async def _wait(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int) -> None:
    """Let time pass in 30 s ticks."""
    for _ in range(seconds // 30):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await _settle(hass)


def _room_id(entry: MockConfigEntry, slug: str) -> str:
    return next(s.subentry_id for s in entry.subentries.values() if s.unique_id == slug)


async def test_entities_follow_prd_naming(hass: HomeAssistant) -> None:
    """Entity IDs use the `hh_` prefix from PRD chapter 9."""
    entry = await _setup(hass)
    expected = [
        "climate.hh_system",
        "select.hh_system_mode",
        "button.hh_manual_30",
        "button.hh_manual_180",
        "button.hh_stop",
        "sensor.hh_manual_ends_at",
        "sensor.hh_state",
        "sensor.hh_demand_total",
        "sensor.hh_outdoor_temperature",
        "sensor.hh_outdoor_temperature_damped",
        "sensor.hh_boiler_duty",
        "sensor.hh_boiler_starts_today",
        "sensor.hh_open_windows",
        "binary_sensor.hh_heat_demand",
        "binary_sensor.hh_boiler_command",
        "binary_sensor.hh_window_block",
        "binary_sensor.hh_heating_season",
        "select.hh_heating_season",
        "sensor.hh_outdoor_mean_4h",
        "binary_sensor.hh_problem",
        "switch.hh_shadow_mode",
        "climate.hh_obyvak",
        "sensor.hh_obyvak_temperature",
        "sensor.hh_obyvak_demand",
        "sensor.hh_obyvak_valve_state",
        "number.hh_obyvak_comfort",
        "number.hh_obyvak_eco",
        "number.hh_obyvak_away",
        "binary_sensor.hh_obyvak_window",
        "binary_sensor.hh_obyvak_problem",
        "climate.hh_loznice",
    ]
    for entity_id in expected:
        assert hass.states.get(entity_id) is not None, entity_id
    # The manual mode of a room is translated as "Manual", of the system as manual heating.
    registry = er.async_get(hass)
    assert registry.async_get("climate.hh_obyvak").translation_key == "room"
    assert registry.async_get("climate.hh_system").translation_key == "system"
    assert hass.states.get("climate.hh_obyvak").name == "Obývák"
    registry = er.async_get(hass)
    room_entry = registry.async_get("sensor.hh_obyvak_temperature")
    assert room_entry.config_subentry_id == _room_id(entry, "obyvak")
    assert hass.states.get("sensor.hh_obyvak_temperature").state == "19.0"
    assert hass.states.get("climate.hh_obyvak").attributes["current_temperature"] == 19.0


async def test_shadow_mode_does_not_switch(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Default shadow mode: everything is calculated, nothing is switched (FR-SAFE-05)."""
    await _setup(hass)
    assert hass.states.get("switch.hh_shadow_mode").state == "on"
    # Without stored history the boiler is assumed to have just stopped (FR-BOI-08).
    assert "anti_cycling" in hass.states.get("climate.hh_system").attributes["blocked_by"]
    await _wait(hass, freezer, 300)
    assert hass.states.get("input_boolean.kotel").state == "off"
    system = hass.states.get("climate.hh_system")
    assert system.attributes["would_command_boiler"] == "on"
    assert system.attributes["would_command_valves"] == {
        "input_boolean.hlavice_obyvak": "open",
        "input_boolean.hlavice_loznice": "closed",
    }
    assert hass.states.get("binary_sensor.hh_heat_demand").state == "on"


async def test_switching_shadow_off_controls_outputs(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Leaving shadow mode applies live and switches boiler and valves."""
    entry = await _setup(hass)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.hh_shadow_mode"}, blocking=True
    )
    await _wait(hass, freezer, 300)
    assert entry.options[CONF_SHADOW_MODE] is False
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("input_boolean.kotel").state == "on"
    assert hass.states.get("input_boolean.hlavice_obyvak").state == "off"  # NO: open
    assert hass.states.get("input_boolean.hlavice_loznice").state == "on"  # NO: closed
    assert hass.states.get("binary_sensor.hh_boiler_command").state == "on"
    assert hass.states.get("climate.hh_system").attributes["hvac_action"] == "heating"
    assert hass.states.get("climate.hh_obyvak").attributes["hvac_action"] == "heating"


async def test_manual_buttons_services_and_mirror_timer(hass: HomeAssistant) -> None:
    """Manual start, countdown and stop (FR-MAN-01 to 03)."""
    await _setup(hass, **{CONF_MIRROR_TIMER_ENTITY: "timer.manual"})
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.hh_manual_60"}, blocking=True
    )
    await _settle(hass)
    assert hass.states.get("select.hh_system_mode").state == "manual"
    assert hass.states.get("sensor.hh_manual_ends_at").state not in ("unknown", "unavailable")
    assert hass.states.get("climate.hh_system").state == "heat"
    assert hass.states.get("timer.manual").state == "active"

    await hass.services.async_call(DOMAIN, "stop", {}, blocking=True)
    await _settle(hass)
    assert hass.states.get("select.hh_system_mode").state == "auto"
    assert hass.states.get("timer.manual").state == "idle"

    await hass.services.async_call(DOMAIN, "start_manual", {"duration": 15}, blocking=True)
    await _settle(hass)
    assert 895 <= hass.states.get("climate.hh_system").attributes["manual_remaining_s"] <= 900
    await hass.services.async_call(DOMAIN, "stop", {}, blocking=True)
    await _settle(hass)


async def test_manual_expires_with_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The 30 s tick ends manual heating when the time is up."""
    await _setup(hass)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.hh_system_mode", "option": "manual"},
        blocking=True,
    )
    assert hass.states.get("select.hh_system_mode").state == "manual"
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await _settle(hass)
    assert hass.states.get("select.hh_system_mode").state == "auto"


async def test_room_climate_override(hass: HomeAssistant) -> None:
    """A setpoint change in auto is a permanent override (FR-MODE-02)."""
    await _setup(hass)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.hh_obyvak", "temperature": 23.5},
        blocking=True,
    )
    state = hass.states.get("climate.hh_obyvak")
    assert state.state == "heat"
    assert state.attributes["temperature"] == 23.5
    assert state.attributes["preset_mode"] == "none"
    assert state.attributes["override_active"] is True

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.hh_obyvak", "hvac_mode": "auto"},
        blocking=True,
    )
    state = hass.states.get("climate.hh_obyvak")
    assert state.attributes["temperature"] == 21.0
    assert state.attributes["override_active"] is False


async def test_number_updates_room_without_reload(hass: HomeAssistant) -> None:
    """Changing the comfort temperature is stored in the room and applied live."""
    entry = await _setup(hass)
    runtime = entry.runtime_data
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.hh_obyvak_comfort", "value": 22.5},
        blocking=True,
    )
    await _settle(hass)
    room_id = _room_id(entry, "obyvak")
    assert entry.subentries[room_id].data[CONF_COMFORT_TEMP] == 22.5
    assert entry.runtime_data is runtime  # no reload
    assert hass.states.get("number.hh_obyvak_comfort").state == "22.5"
    assert hass.states.get("climate.hh_obyvak").attributes["temperature"] == 22.5


async def test_room_temperatures_keep_their_order(hass: HomeAssistant) -> None:
    """Bounds as in the room settings: frost < eco <= comfort, frost < away."""
    await _setup(hass)
    comfort = hass.states.get("number.hh_obyvak_comfort").attributes
    eco = hass.states.get("number.hh_obyvak_eco").attributes
    away = hass.states.get("number.hh_obyvak_away").attributes
    assert (comfort["min"], comfort["max"]) == (19.0, 30.0)
    assert (eco["min"], eco["max"]) == (5.5, 21.0)
    assert (away["min"], away["max"]) == (5.5, 25.0)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": "number.hh_obyvak_eco", "value": 22}, blocking=True
        )
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.hh_obyvak_comfort", "value": 23}, blocking=True
    )
    await _settle(hass)
    assert hass.states.get("number.hh_obyvak_eco").attributes["max"] == 23.0
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.hh_obyvak_away", "value": 12}, blocking=True
    )
    await _settle(hass)
    assert hass.states.get("number.hh_obyvak_away").state == "12.0"


async def test_new_room_reloads_with_new_entities(hass: HomeAssistant) -> None:
    """Adding a room changes the entity set, so the entry reloads."""
    entry = await _setup(hass)
    hass.states.async_set("sensor.kuchyn", "20.0", CELSIUS)
    subentry_data = _room("Kuchyň", "kuchyn")
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=subentry_data["data"],
            subentry_type=SUBENTRY_ROOM,
            title="Kuchyň",
            unique_id="kuchyn",
        ),
    )
    await _settle(hass)
    assert hass.states.get("climate.hh_kuchyn") is not None


async def test_fault_creates_repair_and_recovers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Boiler unavailable: fault_safe, repair issue and notification; then recovery."""
    await _setup(hass, **{CONF_SHADOW_MODE: False})
    hass.states.async_set("input_boolean.kotel", "unavailable")
    await _settle(hass)
    assert hass.states.get("sensor.hh_state").state == "fault_safe"
    assert hass.states.get("binary_sensor.hh_problem").state == "on"
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, "fault_safe") is not None
    notifications = hass.data.get("persistent_notification", {})
    assert any("fault_safe" in key for key in notifications)

    hass.states.async_set("input_boolean.kotel", "off")
    await _settle(hass)
    for _ in range(11):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await _settle(hass)
    assert hass.states.get("sensor.hh_state").state == "auto"
    assert issues.async_get_issue(DOMAIN, "fault_safe") is None


async def test_boiler_without_heat_creates_repair(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The measured water does not warm up while the boiler runs (FR-SAFE-08)."""
    freezer.move_to("2026-01-15 11:00:00+00:00")
    hass.states.async_set("sensor.stoupacka", "30.0", CELSIUS)
    await _setup(hass, **{CONF_SHADOW_MODE: False, CONF_FLOW_TEMP_ENTITY: "sensor.stoupacka"})
    await _wait(hass, freezer, 5 * 60)
    command = hass.states.get("binary_sensor.hh_boiler_command")
    assert command.state == "on"
    assert command.attributes["flow_check"] == "waiting"
    await _wait(hass, freezer, 15 * 60)
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, "no_heat") is not None
    assert hass.states.get("binary_sensor.hh_problem").attributes["problems"] == ["no_heat"]
    hass.states.async_set("sensor.stoupacka", "36.0", CELSIUS)
    await _settle(hass)
    assert issues.async_get_issue(DOMAIN, "no_heat") is None
    command = hass.states.get("binary_sensor.hh_boiler_command")
    assert command.attributes["flow_check"] == "ok"


async def test_state_survives_reload(hass: HomeAssistant) -> None:
    """Manual mode and room overrides are stored (FR-MAN-05, NFR-11)."""
    entry = await _setup(hass)
    await hass.services.async_call(DOMAIN, "start_manual", {"duration": 120}, blocking=True)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.hh_loznice", "preset_mode": "eco"},
        blocking=True,
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await _settle(hass)
    assert hass.states.get("select.hh_system_mode").state == "manual"
    assert hass.states.get("climate.hh_loznice").attributes["preset_mode"] == "eco"


async def test_diagnostics(hass: HomeAssistant) -> None:
    """Diagnostics contain options, rooms and state; the notify service is redacted."""
    entry = await _setup(hass, notify_service="notify.mobile_app_telefon")
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["options"]["notify_service"] == "**REDACTED**"
    assert len(data["rooms"]) == 2
    assert data["status"]["state"] == "auto"
    assert "modes" in data["stored"]


async def test_service_without_entry_raises(hass: HomeAssistant) -> None:
    """Services fail clearly when the integration is not loaded."""
    entry = await _setup(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(Exception, match=r"not_loaded|není načtená|not loaded"):
        await hass.services.async_call(DOMAIN, "stop", {}, blocking=True)


async def test_stale_issue_and_notification_are_removed_at_start(hass: HomeAssistant) -> None:
    """Leftovers of a previous instance disappear when no fault is active."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "fault_safe",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="fault_safe",
        translation_placeholders={"reason": "x"},
    )
    persistent_notification.async_create(hass, "old", "old", f"{DOMAIN}_fault_safe")
    persistent_notification.async_create(hass, "old", "old", f"{DOMAIN}_window_long_obyvak")
    persistent_notification.async_create(hass, "keep", "keep", "something_else")
    await _setup(hass)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "fault_safe") is None
    notifications = hass.data.get("persistent_notification", {})
    assert f"{DOMAIN}_fault_safe" not in notifications
    assert f"{DOMAIN}_window_long_obyvak" not in notifications
    assert "something_else" in notifications
