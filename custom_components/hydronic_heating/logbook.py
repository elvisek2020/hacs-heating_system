"""Logbook entries for the decisions of the controller (FR-SAFE-07)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_DECISION


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None],
) -> None:
    """Describe the decision event; the text is rendered when the event is fired."""

    @callback
    def describe(event: Event) -> dict[str, Any]:
        data = event.data
        entry: dict[str, Any] = {"name": data.get("name", ""), "message": data.get("message", "")}
        if entity_id := data.get("entity_id"):
            entry["entity_id"] = entity_id
        return entry

    async_describe_event(DOMAIN, EVENT_DECISION, describe)
