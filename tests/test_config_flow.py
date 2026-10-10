"""Tests for the initial config flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hydronic_heating.const import (
    CONF_BOILER_MIN_ON,
    CONF_FEEDBACK_ENTITY,
    CONF_HAS_BYPASS,
    CONF_HEAT_SOURCE_ENTITY,
    CONF_HEAT_SOURCE_SELECT_ENTITY,
    CONF_HEAT_SOURCE_SELECT_OFF,
    CONF_HEAT_SOURCE_SELECT_ON,
    CONF_HEAT_SOURCE_TYPE,
    CONF_OUTDOOR_SENSORS,
    CONF_SHADOW_MODE,
    CONF_WEATHER_ENTITY,
    DEFAULT_OPTIONS,
    DOMAIN,
)

from .conftest import form_input


async def _start(hass: HomeAssistant, heat_type: str) -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: " Topení ", CONF_SHADOW_MODE: True}
    )
    assert result["step_id"] == "heat_source"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HEAT_SOURCE_TYPE: heat_type}
    )
    assert result["step_id"] == f"heat_source_{heat_type}"
    return result


async def test_full_flow_with_switch(hass: HomeAssistant, entities: None) -> None:
    """The whole setup creates an entry with PRD defaults and the entered values."""
    result = await _start(hass, "switch")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HEAT_SOURCE_ENTITY: "switch.kotel"}
    )
    assert result["step_id"] == "outdoor"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_SENSORS: ["sensor.venku"]}
    )
    assert result["step_id"] == "protection"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_input(result, boiler_min_on=10, has_bypass=True)
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Topení"
    options = result["options"]
    assert options[CONF_HEAT_SOURCE_TYPE] == "switch"
    assert options[CONF_HEAT_SOURCE_ENTITY] == "switch.kotel"
    assert options[CONF_OUTDOOR_SENSORS] == ["sensor.venku"]
    assert CONF_WEATHER_ENTITY not in options
    assert CONF_FEEDBACK_ENTITY not in options
    assert options[CONF_BOILER_MIN_ON] == 10
    assert isinstance(options[CONF_BOILER_MIN_ON], int)
    assert options[CONF_HAS_BYPASS] is True
    # Parameters not asked during setup keep the PRD defaults.
    assert options["heating_limit"] == DEFAULT_OPTIONS["heating_limit"]


async def test_select_heat_source_validation(hass: HomeAssistant, entities: None) -> None:
    """Select options must exist on the entity and differ from each other."""
    result = await _start(hass, "select")
    base = {CONF_HEAT_SOURCE_SELECT_ENTITY: "select.kotel_rezim"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**base, CONF_HEAT_SOURCE_SELECT_ON: "Zap", CONF_HEAT_SOURCE_SELECT_OFF: "Vypnuto"},
    )
    assert result["errors"] == {CONF_HEAT_SOURCE_SELECT_ON: "invalid_select_option"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**base, CONF_HEAT_SOURCE_SELECT_ON: "Vypnuto", CONF_HEAT_SOURCE_SELECT_OFF: "Vypnuto"},
    )
    assert result["errors"] == {"base": "select_options_equal"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**base, CONF_HEAT_SOURCE_SELECT_ON: "Zapnuto", CONF_HEAT_SOURCE_SELECT_OFF: "Vypnuto"},
    )
    assert result["step_id"] == "outdoor"


async def test_outdoor_rejects_non_temperature(hass: HomeAssistant, entities: None) -> None:
    """A humidity sensor cannot be used as outdoor temperature."""
    result = await _start(hass, "switch")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HEAT_SOURCE_ENTITY: "switch.kotel"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_SENSORS: ["sensor.vlhkost"]}
    )
    assert result["errors"] == {CONF_OUTDOOR_SENSORS: "not_temperature_sensor"}


async def test_single_instance(hass: HomeAssistant) -> None:
    """Only one heating system can be configured."""
    MockConfigEntry(domain=DOMAIN, options=dict(DEFAULT_OPTIONS)).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
