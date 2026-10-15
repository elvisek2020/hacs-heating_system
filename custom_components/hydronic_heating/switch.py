"""Switches: shadow mode, airing by hand and the virtual outputs of the demo mode."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .demo import DemoRoom, DemoValve
from .entity import DemoEntity, HydronicEntity
from .explain import airing_end
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the shadow mode switch and, in the demo, the virtual switches."""
    runtime = entry.runtime_data
    async_add_entities([ShadowModeSwitch(runtime), HouseVentilationSwitch(runtime)])
    # FR-WIN-07: airing of each floor (from the areas) and of each room.
    floors = {f.floor_id: f for f in runtime.floors.values()}
    async_add_entities(FloorVentilationSwitch(runtime, f.floor_id, f.name) for f in floors.values())
    for room in runtime.rooms:
        async_add_entities([RoomVentilationSwitch(runtime, room)], config_subentry_id=room.room_id)
    layout = runtime.layout
    if layout is None:
        return
    async_add_entities([DemoBoilerSwitch(runtime)])
    for demo_room in layout.rooms:
        entities: list[SwitchEntity] = [
            DemoValveSwitch(runtime, demo_room, valve) for valve in demo_room.valves
        ]
        if layout.house:
            entities.append(DemoRoomEventSwitch(runtime, demo_room, "window"))
            entities.append(DemoRoomEventSwitch(runtime, demo_room, "sensor_fault"))
        async_add_entities(entities, config_subentry_id=demo_room.room.room_id)


class ShadowModeSwitch(HydronicEntity, SwitchEntity):
    """Calculate everything but switch no outputs."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        """Initialize."""
        super().__init__(runtime, "switch", "shadow_mode")

    @property
    def is_on(self) -> bool:
        """Shadow mode is active."""
        return self.runtime.real_system_config().shadow_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """In the demo, shadow mode is overridden by the virtual outputs."""
        if self.runtime.demo is None:
            return None
        return {"demo_mode": self.runtime.demo_mode}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Stop switching outputs."""
        self.runtime.set_shadow_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Start switching outputs."""
        self.runtime.set_shadow_mode(False)


class _VentilationSwitch(HydronicEntity, SwitchEntity):
    """Airing by hand of a set of rooms (FR-WIN-07): on starts, off ends it."""

    def _room_ids(self) -> list[str]:
        raise NotImplementedError

    def _rooms(self) -> list[Any]:
        rooms = self.controller.rooms
        return [rooms[room_id] for room_id in self._room_ids() if room_id in rooms]

    @property
    def is_on(self) -> bool:
        """Some of the rooms are being aired."""
        return any(room.manual_vent for room in self._rooms())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """When the airing ends; `ends` is a short text for the tile."""
        ends = [room.manual_vent_until for room in self._rooms() if room.manual_vent_until]
        until = max(ends) if ends else None
        return {
            "until": until.isoformat() if until else None,
            "ends": airing_end(self.hass, until),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the airing; when it already runs, add the time."""
        self.runtime.ventilate(self._room_ids())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """End the airing."""
        self.runtime.stop_ventilation(self._room_ids())


class HouseVentilationSwitch(_VentilationSwitch):
    """Airing of the whole house (`switch.hh_ventilation`)."""

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        """Initialize."""
        super().__init__(runtime, "switch", "ventilation")

    def _room_ids(self) -> list[str]:
        return list(self.controller.rooms)


class FloorVentilationSwitch(_VentilationSwitch):
    """Airing of one floor (`switch.hh_ventilation_<floor>`): the draught goes through it."""

    def __init__(self, runtime: HydronicHeatingRuntime, floor_id: str, name: str) -> None:
        """Initialize."""
        super().__init__(runtime, "switch", f"ventilation_{floor_id}")
        self.floor_id = floor_id
        self._attr_translation_key = "floor_ventilation"
        self._attr_translation_placeholders = {"floor": name}

    def _room_ids(self) -> list[str]:
        return self.runtime.floor_room_ids(self.floor_id)


class RoomVentilationSwitch(_VentilationSwitch):
    """Airing of a room (`switch.hh_<room>_ventilation`); by default it airs its floor."""

    def __init__(self, runtime: HydronicHeatingRuntime, room: Any) -> None:
        """Initialize."""
        super().__init__(runtime, "switch", "ventilation", room)

    def _room_ids(self) -> list[str]:
        assert self.room_id is not None
        return self.runtime.scope_room_ids(self.room_id)

    @property
    def is_on(self) -> bool:
        """The room is being aired."""
        return self.room.manual_vent

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """When the airing of this room ends, and why it airs (by hand or the floor)."""
        until = self.room.manual_vent_until
        return {
            "until": until.isoformat() if until else None,
            "ends": airing_end(self.hass, until),
            "source": self.room.vent_source if until else None,
        }


class DemoBoilerSwitch(DemoEntity, SwitchEntity):
    """Virtual boiler contact (`switch.hh_demo_boiler`)."""

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        """Initialize."""
        super().__init__(runtime, "switch", "demo_boiler")

    @property
    def available(self) -> bool:
        """Unavailable while the demo simulates a missing boiler."""
        return self.simulator.boiler_available

    @property
    def is_on(self) -> bool:
        """Virtual contact closed."""
        return self.simulator.boiler_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The real entity this switch stands in for."""
        return {
            "real_entity": self.runtime.real_system_config().heat_source.state_entity,
            "behavior": self.simulator.boiler_behavior,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Close the virtual contact."""
        self.simulator.command_boiler(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Open the virtual contact."""
        self.simulator.command_boiler(False)


class DemoValveSwitch(DemoEntity, SwitchEntity):
    """Virtual valve head; on = energized, like the real switch."""

    def __init__(
        self, runtime: HydronicHeatingRuntime, demo_room: DemoRoom, valve: DemoValve
    ) -> None:
        """Initialize."""
        super().__init__(runtime, "switch", valve.ids.key, demo_room.room)
        self._attr_translation_key = "demo_valve"
        self._attr_translation_placeholders = {"index": str(valve.index)}
        self.valve = valve

    @property
    def is_on(self) -> bool:
        """Head energized."""
        return self.simulator.valves[self.simulator.valve_key(self.room_id, self.valve)]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Mapping to the real valve."""
        energized = self.is_on
        return {
            "real_entity": self.valve.real_entity,
            "normally_open": self.valve.normally_open,
            "valve_open": not energized if self.valve.normally_open else energized,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Energize the virtual head."""
        self.simulator.command_valve(self.room_id, self.valve, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """De-energize the virtual head."""
        self.simulator.command_valve(self.room_id, self.valve, False)


class DemoRoomEventSwitch(DemoEntity, SwitchEntity):
    """Simulated window or sensor fault of a room (virtual house)."""

    def __init__(self, runtime: HydronicHeatingRuntime, demo_room: DemoRoom, event: str) -> None:
        """Initialize."""
        super().__init__(runtime, "switch", f"demo_{event}", demo_room.room)
        self.event = event

    @property
    def is_on(self) -> bool:
        """Window open, or sensor failure active."""
        store = self.simulator.windows if self.event == "window" else self.simulator.sensor_faults
        return store[self.room_id]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Open the window / fail the sensor."""
        self.simulator.set_value(self.event, self.room_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Close the window / restore the sensor."""
        self.simulator.set_value(self.event, self.room_id, False)
