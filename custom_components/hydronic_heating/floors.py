"""Floors of the rooms from the area and floor registries (FR-UI-25, FR-WIN-07).

The area is the one of the room's device (or of its thermostat entity), else an
area with the room's name. Rooms without a floor have none.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)

from .const import DOMAIN
from .core.model import RoomConfig


@dataclass(frozen=True, slots=True)
class Floor:
    """A floor of the house."""

    floor_id: str
    name: str
    level: int | None


def room_floors(
    hass: HomeAssistant, entry_id: str, rooms: Iterable[RoomConfig]
) -> dict[str, Floor]:
    """Return the floor of each room that has one (room ID -> floor)."""
    entities, devices = er.async_get(hass), dr.async_get(hass)
    areas, floors = ar.async_get(hass), fr.async_get(hass)
    result: dict[str, Floor] = {}
    for room in rooms:
        entity_id = entities.async_get_entity_id(
            "climate", DOMAIN, f"{entry_id}_{room.room_id}_climate"
        )
        entry = entities.async_get(entity_id) if entity_id else None
        area_id = entry.area_id if entry else None
        if area_id is None and entry is not None and entry.device_id:
            device = devices.async_get(entry.device_id)
            area_id = device.area_id if device else None
        area = areas.async_get_area(area_id) if area_id else areas.async_get_area_by_name(room.name)
        if area is None or area.floor_id is None:
            continue
        if (floor := floors.async_get_floor(area.floor_id)) is not None:
            result[room.room_id] = Floor(floor.floor_id, floor.name, floor.level)
    return result


def floor_order(floors: Iterable[Floor]) -> list[Floor]:
    """Distinct floors, the highest first."""
    unique = {floor.floor_id: floor for floor in floors}
    return sorted(unique.values(), key=lambda f: -(f.level if f.level is not None else 0))
