"""Tests for the options flow (system settings menu)."""

from __future__ import annotations

from types import MappingProxyType

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hydronic_heating.const import (
    CONF_AREA_M2,
    CONF_AREA_WEIGHTING,
    CONF_BOILER_DEMAND_HYSTERESIS,
    CONF_BOILER_MIN_ON,
    CONF_DESIGN_FLOW_TEMP,
    CONF_EQUITHERMAL_DUTY_ENABLED,
    CONF_EXERCISE_DURATION,
    CONF_HEAT_SOURCE_ENTITY,
    CONF_HEAT_SOURCE_SELECT_ENTITY,
    CONF_HEAT_SOURCE_SELECT_OFF,
    CONF_HEAT_SOURCE_SELECT_ON,
    CONF_HEAT_SOURCE_TYPE,
    CONF_MANUAL_DURATIONS,
    CONF_NOTIFY_SERVICE,
    CONF_ROOM_NAME,
    CONF_VALVE_CLOSE_TIME,
    CONF_VALVE_ENTITY,
    CONF_VALVE_OPEN_TIME,
    CONF_VALVES,
    DEFAULT_ROOM,
    SUBENTRY_ROOM,
)

from .conftest import form_input


async def _open(hass: HomeAssistant, entry: MockConfigEntry, step: str) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    return result


def _add_room(hass: HomeAssistant, entry: MockConfigEntry, name: str, **data) -> None:
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType({**DEFAULT_ROOM, CONF_ROOM_NAME: name, **data}),
            subentry_type=SUBENTRY_ROOM,
            title=name,
            unique_id=slugify(name),
        ),
    )


async def test_menu_offers_all_sections(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Every parameter group is reachable from the menu (NFR-13)."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["menu_options"] == [
        "general",
        "heat_source",
        "outdoor",
        "boiler",
        "safety",
        "valves",
        "windows",
        "manual",
        "equithermal",
        "frost",
    ]


async def test_boiler_saves_and_keeps_other_options(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Saving one section keeps all other options."""
    result = await _open(hass, config_entry, "boiler")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, boiler_min_on=10)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_BOILER_MIN_ON] == 10
    assert config_entry.options[CONF_HEAT_SOURCE_ENTITY] == "switch.kotel"


async def test_boiler_validation(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Hysteresis below threshold; area weighting needs the area of every room."""
    _add_room(hass, config_entry, "Obývák", **{CONF_AREA_M2: 25})
    _add_room(hass, config_entry, "Koupelna")
    await hass.async_block_till_done()

    result = await _open(hass, config_entry, "boiler")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, boiler_demand_hysteresis=30)
    )
    assert result["errors"] == {CONF_BOILER_DEMAND_HYSTERESIS: "hysteresis_too_large"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, boiler_demand_hysteresis=10, area_weighting=True)
    )
    assert result["errors"] == {CONF_AREA_WEIGHTING: "area_missing"}
    assert result["description_placeholders"] == {"rooms": "Koupelna"}


async def test_heat_source_type_change_drops_old_keys(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Switching the heat source to a select removes the switch entity."""
    result = await _open(hass, config_entry, "heat_source")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HEAT_SOURCE_TYPE: "select"}
    )
    assert result["step_id"] == "heat_source_select"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HEAT_SOURCE_SELECT_ENTITY: "select.kotel_rezim",
            CONF_HEAT_SOURCE_SELECT_ON: "Zapnuto",
            CONF_HEAT_SOURCE_SELECT_OFF: "Vypnuto",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_HEAT_SOURCE_TYPE] == "select"
    assert CONF_HEAT_SOURCE_ENTITY not in config_entry.options


async def test_safety_notify_service(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """The notification service must exist."""

    async def _handler(call: ServiceCall) -> None:
        """Do nothing."""

    result = await _open(hass, config_entry, "safety")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, notify_service="notify.mobile_app_telefon")
    )
    assert result["errors"] == {CONF_NOTIFY_SERVICE: "notify_service_not_found"}

    hass.services.async_register("notify", "mobile_app_telefon", _handler)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, notify_service="notify.mobile_app_telefon")
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_NOTIFY_SERVICE] == "notify.mobile_app_telefon"


async def test_cleared_optional_field_is_removed(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Clearing an optional field removes it from the options."""
    hass.config_entries.async_update_entry(
        config_entry,
        options={**config_entry.options, CONF_NOTIFY_SERVICE: "notify.stary"},
    )
    await hass.async_block_till_done()
    result = await _open(hass, config_entry, "safety")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_NOTIFY_SERVICE not in config_entry.options


async def test_exercise_duration_follows_valve_time(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Exercise must last at least the longest valve travel time + 60 s."""
    valve = {CONF_VALVE_ENTITY: "switch.hlavice_obyvak", CONF_VALVE_OPEN_TIME: 600}
    _add_room(
        hass, config_entry, "Obývák", **{CONF_VALVES: [{**valve, CONF_VALVE_CLOSE_TIME: 120}]}
    )
    await hass.async_block_till_done()

    result = await _open(hass, config_entry, "valves")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, exercise_duration=600)
    )
    assert result["errors"] == {CONF_EXERCISE_DURATION: "exercise_too_short"}
    assert result["description_placeholders"] == {"minimum": "660"}


async def test_manual_durations(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Durations are stored as sorted unique integers."""
    result = await _open(hass, config_entry, "manual")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, manual_durations=["abc"])
    )
    assert result["errors"] == {CONF_MANUAL_DURATIONS: "invalid_durations"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, manual_durations=["90", "15", "90"])
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_MANUAL_DURATIONS] == [15, 90]


async def test_equithermal_confirm(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """A curve above the boiler water temperature asks for confirmation (FR-EQ-05)."""
    result = await _open(hass, config_entry, "equithermal")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, flow_temp_min=60, flow_temp_max=50)
    )
    assert result["errors"] == {"flow_temp_min": "flow_range"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        form_input(result, equithermal_duty_enabled=True, boiler_fixed_flow_temp=40),
    )
    assert result["step_id"] == "equithermal_confirm"
    assert result["description_placeholders"] == {
        "design_flow_temp": "65",
        "boiler_fixed_flow_temp": "40",
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_EQUITHERMAL_DUTY_ENABLED] is True

    result = await _open(hass, config_entry, "equithermal")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, design_flow_temp=40)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_DESIGN_FLOW_TEMP] == 40
