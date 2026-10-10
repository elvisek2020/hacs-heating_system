"""A fake house for core tests: entity states that follow commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.controller import HydronicController
from custom_components.hydronic_heating.core.model import (
    Command,
    EntityReading,
    Plan,
    RoomConfig,
    Snapshot,
    SystemConfig,
)

TZ = ZoneInfo("Europe/Prague")
# A winter Thursday, 12:00 local time.
T0 = datetime(2026, 1, 15, 11, 0, tzinfo=UTC)
BOILER = "switch.kotel"


def system(**overrides: Any) -> SystemConfig:
    """System configuration with PRD defaults, out of shadow mode."""
    options = {
        **c.DEFAULT_OPTIONS,
        c.CONF_SHADOW_MODE: False,
        c.CONF_HEAT_SOURCE_ENTITY: BOILER,
        **overrides,
    }
    return SystemConfig.from_options(options, TZ)


def valve(entity_id: str, **overrides: Any) -> dict[str, Any]:
    """Return stored valve settings."""
    return {c.CONF_VALVE_ENTITY: entity_id, **c.DEFAULT_VALVE, **overrides}


def room(slug: str, **overrides: Any) -> RoomConfig:
    """Room with one temperature sensor and one NO valve."""
    data = {
        **c.DEFAULT_ROOM,
        c.CONF_ROOM_NAME: slug.capitalize(),
        c.CONF_SENSORS: [f"sensor.{slug}"],
        c.CONF_VALVES: [valve(f"switch.hlavice_{slug}")],
        **overrides,
    }
    return RoomConfig.from_data(f"id_{slug}", slug, data)


class House:
    """Entity states driven by the controller's commands."""

    def __init__(
        self,
        controller: HydronicController,
        *,
        now: datetime = T0,
        temperatures: dict[str, float] | None = None,
    ) -> None:
        """Create the house; valves start de-energized, the boiler off."""
        self.ctrl = controller
        self.now = now
        self.states: dict[str, EntityReading] = {}
        self.ignore: set[str] = set()
        self.commands: list[Command] = []
        self.fresh_sensors = True
        self.forecast: float | None = None
        self.set(BOILER, "off")
        for room_ctrl in controller.rooms.values():
            for v in room_ctrl.cfg.valves:
                self.set(v.entity_id, "open" if v.is_valve_domain else "off")
        for slug, temp in (temperatures or {}).items():
            self.temp(slug, temp)

    def set(self, entity_id: str, state: str | None, value: float | None = None, **attrs: Any):
        """Set an entity state."""
        self.states[entity_id] = EntityReading(
            state=state, value=value, last_reported=self.now, attributes=attrs
        )

    def event(self, entity_id: str, state: str, value: float | None = None) -> Plan:
        """Change a state and step at once, like a state change event in Home Assistant."""
        self.set(entity_id, state, value)
        return self.step()

    def temp(self, slug: str, value: float | None) -> None:
        """Set a room temperature (None = unavailable)."""
        if value is None:
            self.set(f"sensor.{slug}", "unavailable")
        else:
            self.set(f"sensor.{slug}", str(value), value)

    def state(self, entity_id: str) -> str | None:
        """Return the raw state of an entity."""
        return self.states[entity_id].state

    def step(self) -> Plan:
        """Run one controller step and execute its commands."""
        if self.fresh_sensors:
            for entity_id, reading in list(self.states.items()):
                if entity_id.startswith("sensor.") and reading.available:
                    self.states[entity_id] = EntityReading(
                        reading.state, reading.value, self.now, reading.attributes
                    )
        plan = self.ctrl.step(Snapshot(self.now, dict(self.states), self.forecast))
        for cmd in plan.commands:
            self.commands.append(cmd)
            if cmd.entity_id in self.ignore:
                continue
            current = self.states.get(cmd.entity_id)
            new = {
                "turn_on": "on",
                "turn_off": "off",
                "open": "open",
                "close": "closed",
                "select": cmd.option,
                "toggle": "off" if current and current.state == "on" else "on",
            }.get(cmd.action)
            if new is not None:
                self.set(cmd.entity_id, new)
        return plan

    def run(self, seconds: float, every: float = 30) -> None:
        """Advance time, stepping every `every` seconds."""
        end = self.now + timedelta(seconds=seconds)
        while self.now < end:
            self.now += timedelta(seconds=every)
            self.step()

    @property
    def boiler_on(self) -> bool:
        """The boiler entity is on."""
        return self.state(BOILER) == "on"


def controller(*rooms: RoomConfig, **options: Any) -> HydronicController:
    """Return a controller restored from empty storage before T0."""
    ctrl = HydronicController(system(**options), rooms)
    ctrl.restore(None, T0 - timedelta(hours=1))
    return ctrl
