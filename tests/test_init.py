"""Tests for setting up and unloading the integration."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hydronic_heating.const import CONF_DEMO_MODE, DEMO_VIRTUAL_OUTPUTS

from .test_runtime import _setup


async def test_setup_and_unload(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """The entry loads and unloads cleanly."""
    assert config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_options_change_applies_without_reload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """New settings apply live, without restarting Home Assistant (NFR-13)."""
    runtime = config_entry.runtime_data
    with patch.object(hass.config_entries, "async_reload") as reload:
        hass.config_entries.async_update_entry(
            config_entry, options={**config_entry.options, "boiler_min_on": 10}
        )
        await hass.async_block_till_done()
    reload.assert_not_called()
    assert runtime.controller.cfg.boiler_min_on_s == 600


async def test_manual_durations_change_reloads(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Different manual durations need different buttons, so the entry reloads."""
    with patch.object(hass.config_entries, "async_reload") as reload:
        hass.config_entries.async_update_entry(
            config_entry, options={**config_entry.options, "manual_durations": [15, 45]}
        )
        await hass.async_block_till_done()
    reload.assert_called_once_with(config_entry.entry_id)


async def test_unload_runs_no_step_after_deactivation(hass: HomeAssistant) -> None:
    """Removing our own entities during unload triggers no step and no report."""
    entry = await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_OUTPUTS})
    runtime = entry.runtime_data
    with (
        patch.object(runtime.controller, "step", wraps=runtime.controller.step) as step,
        patch.object(runtime, "_report") as report,
    ):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    step.assert_not_called()
    report.assert_not_called()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_failed_unload_reactivates(hass: HomeAssistant) -> None:
    """If the platforms cannot unload, control continues."""
    entry = await _setup(hass)
    runtime = entry.runtime_data
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
        assert not await hass.config_entries.async_unload(entry.entry_id)
    with patch.object(runtime.controller, "step", wraps=runtime.controller.step) as step:
        hass.states.async_set("sensor.obyvak", "18.0", {"unit_of_measurement": "°C"})
        await hass.async_block_till_done()
    step.assert_called()
    # Home Assistant leaves an entry in FAILED_UNLOAD alone; stop the timers ourselves.
    runtime.deactivate()
