"""Diagnostics (NFR-06)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_NOTIFY_SERVICE, SUBENTRY_ROOM
from .runtime import HydronicConfigEntry

TO_REDACT = {CONF_NOTIFY_SERVICE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HydronicConfigEntry
) -> dict[str, Any]:
    """Return configuration and control state for a bug report."""
    ctrl = entry.runtime_data.controller
    return {
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "rooms": {
            sub.subentry_id: {"title": sub.title, "data": dict(sub.data)}
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_ROOM
        },
        "status": {
            "state": ctrl.state.value,
            "ready": ctrl.ready,
            "heat_request": ctrl.heat_request,
            "window_block": ctrl.window_block,
            "summer": ctrl.summer,
            "fault_reason": ctrl.fault_reason,
            "blocked_by": ctrl.blocked_by,
            "boiler_phase": ctrl.sequencer.phase.value,
            "problems": sorted(ctrl.problems),
            "would_command": ctrl.would_command(),
            "rooms": {
                room_id: {
                    "temperature": room.temperature,
                    "target": room.target,
                    "demand": room.demand,
                    "window": room.window.state.value,
                    "frost_active": room.frost_active,
                    "invalid_sources": list(room.invalid_sources),
                }
                for room_id, room in ctrl.rooms.items()
            },
        },
        "stored": ctrl.to_dict(),
    }
