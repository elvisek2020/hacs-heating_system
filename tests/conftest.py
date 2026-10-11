"""Shared fixtures for Heating Controller tests."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hydronic_heating.const import (
    CONF_HEAT_SOURCE_ENTITY,
    DEFAULT_OPTIONS,
    DOMAIN,
)

CELSIUS = {"unit_of_measurement": "°C"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom integrations in all tests."""


@pytest.fixture
def entities(hass: HomeAssistant) -> None:
    """Entities the flows can point to."""
    hass.states.async_set("switch.kotel", "off")
    hass.states.async_set("sensor.venku", "5.0", {"device_class": "temperature", **CELSIUS})
    hass.states.async_set("sensor.vlhkost", "50", {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.obyvak_teplota", "21.3", CELSIUS)
    hass.states.async_set("sensor.loznice_teplota", "19.8", CELSIUS)
    hass.states.async_set("switch.hlavice_obyvak", "off")
    hass.states.async_set("switch.hlavice_obyvak_2", "off")
    hass.states.async_set("valve.loznice", "open")
    hass.states.async_set("select.kotel_rezim", "Vypnuto", {"options": ["Zapnuto", "Vypnuto"]})


@pytest.fixture
async def config_entry(hass: HomeAssistant, entities: None) -> MockConfigEntry:
    """Return a loaded config entry with default options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Topení",
        data={},
        options={**DEFAULT_OPTIONS, CONF_HEAT_SOURCE_ENTITY: "switch.kotel"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def form_input(result: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Fill a form with its defaults and apply overrides, like the frontend would."""
    return result["data_schema"](overrides)
