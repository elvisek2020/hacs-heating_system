"""Hydronic Heating Controller.

F0 provides the configuration only (system options and room subentries).
Control logic and entities follow in F1 (PRD chapter 14).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS, SUBENTRY_ROOM

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hydronic Heating Controller from a config entry."""
    rooms = [sub for sub in entry.subentries.values() if sub.subentry_type == SUBENTRY_ROOM]
    _LOGGER.debug("Setting up %s with %d room(s)", entry.title, len(rooms))
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after options or rooms change, so new settings apply without a restart."""
    await hass.config_entries.async_reload(entry.entry_id)
