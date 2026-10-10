"""Switches: shadow mode and the virtual outputs and events of the demo mode."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .demo import DemoRoom, DemoValve
from .entity import DemoEntity, HydronicEntity
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the shadow mode switch and, in the demo, the virtual switches."""
    runtime = entry.runtime_data
    async_add_entities([ShadowModeSwitch(runtime)])
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
