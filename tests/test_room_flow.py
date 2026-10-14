"""Tests for the room subentry flow."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hydronic_heating.const import (
    CONF_COMFORT_TEMP,
    CONF_ECO_TEMP,
    CONF_FROST_TEMP,
    CONF_NORMALLY_OPEN,
    CONF_ROOM_NAME,
    CONF_SCHEDULE_ENTITY,
    CONF_SENSORS,
    CONF_VALVE_ENTITY,
    CONF_VALVE_MIN_STATE_TIME,
    CONF_VALVE_OPEN_TIME,
    CONF_VALVES,
    CONF_WINDOWS,
    SUBENTRY_ROOM,
)

from .conftest import form_input


async def _configure(hass: HomeAssistant, result: dict, step: str, **values: Any) -> dict:
    assert result["type"] is FlowResultType.FORM, result
    assert result["step_id"] == step
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], form_input(result, **values)
    )


async def _create_room(
    hass: HomeAssistant, entry: MockConfigEntry, name: str, valves: list[str]
) -> dict:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": SOURCE_USER}
    )
    result = await _configure(hass, result, "basics", name=name)
    result = await _configure(hass, result, "sensors", sensors=["sensor.obyvak_teplota"])
    result = await _configure(hass, result, "valves", valves=valves)
    for _ in valves:
        result = await _configure(hass, result, "valve")
    result = await _configure(hass, result, "windows")
    result = await _configure(hass, result, "schedule")
    return await _configure(hass, result, "control")


def _room(entry: MockConfigEntry, name: str):
    return next(sub for sub in entry.subentries.values() if sub.title == name)


async def test_create_room(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """A room with a NO switch valve and a `valve` entity is stored completely."""
    result = await _create_room(
        hass, config_entry, "Obývák", ["switch.hlavice_obyvak", "valve.loznice"]
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    room = _room(config_entry, "Obývák")
    assert room.unique_id == "obyvak"
    assert room.data[CONF_ROOM_NAME] == "Obývák"
    assert room.data[CONF_SENSORS] == ["sensor.obyvak_teplota"]
    assert room.data[CONF_WINDOWS] == []
    assert CONF_SCHEDULE_ENTITY not in room.data
    assert room.data[CONF_VALVES] == [
        {
            CONF_VALVE_ENTITY: "switch.hlavice_obyvak",
            CONF_NORMALLY_OPEN: True,
            CONF_VALVE_OPEN_TIME: 120,
            "valve_close_time": 120,
        },
        # `valve` entities report the physical state, NO/NC does not apply.
        {CONF_VALVE_ENTITY: "valve.loznice", CONF_VALVE_OPEN_TIME: 120, "valve_close_time": 120},
    ]


async def test_valve_with_pipe_sensor(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """A pipe temperature sensor is stored with its valve (FR-SAFE-09)."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_ROOM), context={"source": SOURCE_USER}
    )
    result = await _configure(hass, result, "basics", name="Pracovna")
    result = await _configure(hass, result, "sensors", sensors=["sensor.obyvak_teplota"])
    result = await _configure(hass, result, "valves", valves=["switch.hlavice_obyvak"])
    result = await _configure(hass, result, "valve", valve_temp_entity="sensor.trubka_pracovna")
    result = await _configure(hass, result, "windows")
    result = await _configure(hass, result, "schedule")
    result = await _configure(hass, result, "control")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    valve = _room(config_entry, "Pracovna").data[CONF_VALVES][0]
    assert valve["valve_temp_entity"] == "sensor.trubka_pracovna"


async def test_valve_step_hides_normally_open_for_valve_domain(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The NO/NC switch is only offered for switch-like valves."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_ROOM), context={"source": SOURCE_USER}
    )
    result = await _configure(hass, result, "basics", name="Ložnice")
    result = await _configure(hass, result, "sensors", sensors=["sensor.loznice_teplota"])
    result = await _configure(hass, result, "valves", valves=["valve.loznice"])
    assert result["step_id"] == "valve"
    assert CONF_NORMALLY_OPEN not in {str(key) for key in result["data_schema"].schema}
    assert result["description_placeholders"] == {"valve": "loznice"}


async def test_basics_validation(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Duplicate names and inconsistent temperatures are rejected."""
    await _create_room(hass, config_entry, "Obývák", ["switch.hlavice_obyvak"])
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_ROOM), context={"source": SOURCE_USER}
    )
    result = await _configure(hass, result, "basics", name="obývák")
    assert result["errors"] == {CONF_ROOM_NAME: "name_exists"}
    result = await _configure(hass, result, "basics", name="Kuchyň", eco_temp=22)
    assert result["errors"] == {CONF_ECO_TEMP: "eco_above_comfort"}
    result = await _configure(hass, result, "basics", name="Kuchyň", frost_temp=12, away_temp=12)
    assert result["errors"] == {CONF_FROST_TEMP: "frost_too_high"}
    result = await _configure(hass, result, "basics", name="Kuchyň")
    assert result["step_id"] == "sensors"


async def test_sensor_validation(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Only temperature sensors with a sane range are accepted."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_ROOM), context={"source": SOURCE_USER}
    )
    result = await _configure(hass, result, "basics", name="Pracovna")
    result = await _configure(hass, result, "sensors", sensors=["sensor.vlhkost"])
    assert result["errors"] == {CONF_SENSORS: "not_temperature_sensor"}
    result = await _configure(
        hass, result, "sensors", sensors=["sensor.obyvak_teplota"], sensor_min=30, sensor_max=20
    )
    assert result["errors"] == {"sensor_min": "sensor_range"}


async def test_min_state_time_follows_valve_time(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The minimum valve state time must cover the valve travel time (FR-VAL-05)."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_ROOM), context={"source": SOURCE_USER}
    )
    result = await _configure(hass, result, "basics", name="Pracovna")
    result = await _configure(hass, result, "sensors", sensors=["sensor.obyvak_teplota"])
    result = await _configure(hass, result, "valves", valves=["switch.hlavice_obyvak"])
    result = await _configure(hass, result, "valve", valve_open_time=400)
    result = await _configure(hass, result, "windows")
    result = await _configure(hass, result, "schedule")
    result = await _configure(hass, result, "control", valve_min_state_time=5)
    assert result["errors"] == {CONF_VALVE_MIN_STATE_TIME: "min_state_too_short"}
    assert result["description_placeholders"] == {"valve_time": "400"}
    result = await _configure(hass, result, "control", valve_min_state_time=7)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_airing_detection_settings(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Airing detection is on by default; the longest pause covers the shortest (FR-WIN-06)."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_ROOM), context={"source": SOURCE_USER}
    )
    result = await _configure(hass, result, "basics", name="Kuchyň")
    result = await _configure(hass, result, "sensors", sensors=["sensor.obyvak_teplota"])
    result = await _configure(hass, result, "valves", valves=["switch.hlavice_obyvak"])
    result = await _configure(hass, result, "valve")
    result = await _configure(hass, result, "windows", vent_pause=30, vent_max=20)
    assert result["errors"] == {"vent_max": "vent_max_below_pause"}
    result = await _configure(hass, result, "windows", vent_drop=0.5, vent_pause=30, vent_max=60)
    result = await _configure(hass, result, "schedule")
    result = await _configure(hass, result, "control")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = _room(config_entry, "Kuchyň").data
    assert data["vent_detect"] is True
    assert (data["vent_drop"], data["vent_time"], data["vent_pause"], data["vent_max"]) == (
        0.5,
        5,
        30,
        60,
    )


async def test_reconfigure_room(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Reconfigure keeps valve settings, can add a valve and rename the room."""
    await _create_room(hass, config_entry, "Obývák", ["switch.hlavice_obyvak"])
    await hass.async_block_till_done()
    room = _room(config_entry, "Obývák")

    result = await config_entry.start_subentry_reconfigure_flow(hass, room.subentry_id)
    result = await _configure(hass, result, "basics", name="Obývací pokoj", comfort_temp=22)
    result = await _configure(hass, result, "sensors")
    result = await _configure(
        hass, result, "valves", valves=["switch.hlavice_obyvak", "switch.hlavice_obyvak_2"]
    )
    # The existing valve is prefilled with its stored settings.
    result = await _configure(hass, result, "valve")
    result = await _configure(hass, result, "valve", normally_open=False)
    result = await _configure(hass, result, "windows")
    result = await _configure(hass, result, "schedule")
    result = await _configure(hass, result, "control")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    room = config_entry.subentries[room.subentry_id]
    assert room.title == "Obývací pokoj"
    assert room.unique_id == "obyvaci_pokoj"
    assert room.data[CONF_COMFORT_TEMP] == 22
    assert [valve[CONF_NORMALLY_OPEN] for valve in room.data[CONF_VALVES]] == [True, False]


async def test_schedule_by_the_house_or_own(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Item 5 of the to-do: the room follows the house schedule or its own."""
    hass.states.async_set("schedule.loznice", "on")
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_ROOM), context={"source": SOURCE_USER}
    )
    result = await _configure(hass, result, "basics", name="Ložnice")
    result = await _configure(hass, result, "sensors", sensors=["sensor.loznice_teplota"])
    result = await _configure(hass, result, "valves", valves=["switch.hlavice_obyvak"])
    result = await _configure(hass, result, "valve")
    result = await _configure(hass, result, "windows")
    assert result["data_schema"]({})["schedule_mode"] == "house"
    # Own without a schedule is refused.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"schedule_mode": "own"}
    )
    assert result["errors"] == {"schedule_entity": "schedule_required"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "schedule_mode": "own",
            "schedule_entity": "schedule.loznice",
            "expected_return_entity": "sensor.navrat_ronny",
        },
    )
    result = await _configure(hass, result, "control")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = _room(config_entry, "Ložnice").data
    assert data["schedule_mode"] == "own"
    assert data[CONF_SCHEDULE_ENTITY] == "schedule.loznice"
    assert data["expected_return_entity"] == "sensor.navrat_ronny"


async def test_schedule_by_the_house_drops_the_own_one(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _create_room(hass, config_entry, "Pokoj", ["switch.hlavice_obyvak"])
    await hass.async_block_till_done()
    room = _room(config_entry, "Pokoj")
    result = await config_entry.start_subentry_reconfigure_flow(hass, room.subentry_id)
    for step in ("basics", "sensors", "valves", "valve", "windows"):
        result = await _configure(hass, result, step)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"schedule_mode": "house", "schedule_entity": "schedule.pokoj"}
    )
    result = await _configure(hass, result, "control")
    await hass.async_block_till_done()
    data = config_entry.subentries[room.subentry_id].data
    assert data["schedule_mode"] == "house"
    assert CONF_SCHEDULE_ENTITY not in data
