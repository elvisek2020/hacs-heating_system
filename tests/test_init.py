"""Tests for setting up and unloading the integration."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_setup_and_unload(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """The entry loads and unloads cleanly."""
    assert config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_options_change_reloads(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """New settings apply without restarting Home Assistant (NFR-13)."""
    with patch.object(hass.config_entries, "async_reload") as reload:
        hass.config_entries.async_update_entry(
            config_entry, options={**config_entry.options, "boiler_min_on": 10}
        )
        await hass.async_block_till_done()
    reload.assert_called_once_with(config_entry.entry_id)
