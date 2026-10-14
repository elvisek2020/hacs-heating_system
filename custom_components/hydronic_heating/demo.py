"""Demo mode: virtual outputs, optionally a whole virtual house.

`virtual_outputs`: real sensors and windows, but the boiler and valve commands
go to virtual switches owned by this integration.
`virtual_house`: additionally simulated room temperatures, windows, sensor
faults and outdoor temperature, driven by a thermal model in real time.

The runtime refuses any command to an entity that does not belong to this
integration while the demo is active, so real outputs cannot be switched.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    DEMO_VIRTUAL_HOUSE,
    DOMAIN,
    ENTITY_PREFIX,
    HEAT_SOURCE_SWITCH,
)
from .core.model import HeatSourceConfig, RoomConfig, SystemConfig
from .demo_model import RoomThermal, initial_room

SIM_INTERVAL_S = 10
DEFAULT_OUTDOOR = 5.0
BOILER_BEHAVIORS = ["normal", "unavailable", "ignore_commands"]


@dataclass(frozen=True, slots=True)
class DemoEntityId:
    """Key, unique ID and resolved entity ID of one demo entity."""

    key: str
    unique_id: str
    entity_id: str


@dataclass(frozen=True, slots=True)
class DemoValve:
    """Virtual switch that stands in for one real valve."""

    ids: DemoEntityId
    index: int
    real_entity: str
    normally_open: bool
    travel_s: float


@dataclass(frozen=True, slots=True)
class DemoRoom:
    """Demo entities of one room."""

    room: RoomConfig
    valves: tuple[DemoValve, ...]
    temperature: DemoEntityId
    window: DemoEntityId
    sensor_fault: DemoEntityId


@dataclass(frozen=True, slots=True)
class DemoLayout:
    """All demo entities and how they map to the real ones."""

    mode: str
    boiler: DemoEntityId
    boiler_behavior: DemoEntityId
    outdoor: DemoEntityId
    rooms: tuple[DemoRoom, ...]

    @property
    def house(self) -> bool:
        """Simulate temperatures, windows and outdoor as well."""
        return self.mode == DEMO_VIRTUAL_HOUSE


def build_layout(
    hass: HomeAssistant, entry_id: str, mode: str, rooms: list[RoomConfig]
) -> DemoLayout:
    """Compute demo entity IDs; renamed entities are found by unique ID."""
    registry = er.async_get(hass)

    def ids(domain: str, key: str, room: RoomConfig | None = None) -> DemoEntityId:
        if room is None:
            unique_id = f"{entry_id}_{key}"
            object_id = f"{ENTITY_PREFIX}_{key}"
        else:
            unique_id = f"{entry_id}_{room.room_id}_{key}"
            object_id = f"{ENTITY_PREFIX}_{room.slug}_{key}"
        entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        return DemoEntityId(key, unique_id, entity_id or f"{domain}.{object_id}")

    demo_rooms = []
    for room in rooms:
        valves = tuple(
            DemoValve(
                ids=ids("switch", f"demo_valve_{index}", room),
                index=index,
                real_entity=valve.entity_id,
                normally_open=valve.normally_open,
                travel_s=valve.travel_time_s,
            )
            for index, valve in enumerate(room.valves, start=1)
        )
        demo_rooms.append(
            DemoRoom(
                room=room,
                valves=valves,
                temperature=ids("sensor", "demo_temperature", room),
                window=ids("switch", "demo_window", room),
                sensor_fault=ids("switch", "demo_sensor_fault", room),
            )
        )
    return DemoLayout(
        mode=mode,
        boiler=ids("switch", "demo_boiler"),
        boiler_behavior=ids("select", "demo_boiler_behavior"),
        outdoor=ids("number", "demo_outdoor_temperature"),
        rooms=tuple(demo_rooms),
    )


def remap(
    system: SystemConfig, rooms: list[RoomConfig], layout: DemoLayout
) -> tuple[SystemConfig, list[RoomConfig]]:
    """Point the controller at the demo entities instead of the real ones."""
    system = replace(
        system,
        heat_source=HeatSourceConfig(type=HEAT_SOURCE_SWITCH, entity=layout.boiler.entity_id),
        shadow_mode=False,
        heartbeat_entity=None,
        mirror_timer_entity=None,
    )
    if layout.house:
        system = replace(system, outdoor_sensors=(layout.outdoor.entity_id,), weather_entity=None)
    remapped = []
    for room, demo in zip(rooms, layout.rooms, strict=True):
        valves = tuple(
            # The real pipes do not follow the virtual heads (FR-SAFE-09).
            replace(valve, entity_id=dv.ids.entity_id, temp_entity=None)
            for valve, dv in zip(room.valves, demo.valves, strict=True)
        )
        new = replace(room, valves=valves)
        if layout.house:
            new = replace(
                new,
                sensors=(demo.temperature.entity_id,),
                windows=(demo.window.entity_id,),
                window_invert=False,
            )
        remapped.append(new)
    return system, remapped


class DemoSimulator:
    """State of the virtual outputs and, in the virtual house, the rooms."""

    def __init__(self, hass: HomeAssistant, layout: DemoLayout, water_temp: float) -> None:
        """Start with de-energized valves and the boiler off."""
        self.hass = hass
        self.layout = layout
        self.water_temp = water_temp
        self.boiler_on = False
        self.boiler_behavior = "normal"
        self.valves: dict[str, bool] = {
            v.ids.key + room.room.room_id: False for room in layout.rooms for v in room.valves
        }
        self.windows: dict[str, bool] = {room.room.room_id: False for room in layout.rooms}
        self.sensor_faults: dict[str, bool] = {room.room.room_id: False for room in layout.rooms}
        self.outdoor = DEFAULT_OUTDOOR
        self.thermal: dict[str, RoomThermal] = {
            room.room.room_id: initial_room(index) for index, room in enumerate(layout.rooms)
        }
        self._listeners: list[Callable[[], None]] = []
        self._unsub: CALLBACK_TYPE | None = None
        self._last: datetime | None = None

    # --- Lifecycle ----------------------------------------------------------

    @callback
    def start(self) -> None:
        """Run the thermal model every few seconds (virtual house only)."""
        if not self.layout.house:
            return
        self._last = dt_util.utcnow()
        self._unsub = async_track_time_interval(
            self.hass, self._tick, timedelta(seconds=SIM_INTERVAL_S)
        )

    @callback
    def stop(self) -> None:
        """Stop the model."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a demo entity."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # --- Virtual outputs ------------------------------------------------------

    @staticmethod
    def valve_key(room_id: str, valve: DemoValve) -> str:
        """Key of a virtual valve in `valves`."""
        return valve.ids.key + room_id

    @property
    def boiler_available(self) -> bool:
        """The virtual boiler entity is available."""
        return self.boiler_behavior != "unavailable"

    @callback
    def command_boiler(self, on: bool) -> None:
        """Command from Home Assistant; ignored when simulating a deaf boiler."""
        if self.boiler_behavior == "ignore_commands":
            return
        self.boiler_on = on
        self._notify()

    @callback
    def command_valve(self, room_id: str, valve: DemoValve, energized: bool) -> None:
        """Command a virtual valve head."""
        self.valves[self.valve_key(room_id, valve)] = energized
        self._notify()

    @callback
    def set_value(self, attribute: str, room_id: str | None, value: Any) -> None:
        """Change a simulated input (window, sensor fault, outdoor, behavior)."""
        if attribute == "boiler_behavior":
            self.boiler_behavior = value
        elif attribute == "outdoor":
            self.outdoor = float(value)
        elif attribute == "window" and room_id:
            self.windows[room_id] = bool(value)
        elif attribute == "sensor_fault" and room_id:
            self.sensor_faults[room_id] = bool(value)
        self._notify()

    # --- Thermal model ----------------------------------------------------------

    def room_temperature(self, room_id: str) -> float | None:
        """Return the simulated temperature, None while a sensor fault is simulated."""
        if self.sensor_faults.get(room_id):
            return None
        return round(self.thermal[room_id].temperature, 1)

    @callback
    def _tick(self, now: datetime) -> None:
        dt_s = (now - self._last).total_seconds() if self._last else SIM_INTERVAL_S
        self._last = now
        self.advance(dt_s)
        self._notify()

    def advance(self, dt_s: float) -> None:
        """Move the virtual house forward by `dt_s` seconds."""
        heating = self.boiler_on and self.boiler_available
        for room in self.layout.rooms:
            room_id = room.room.room_id
            positions = [
                not self.valves[self.valve_key(room_id, v)]
                if v.normally_open
                else self.valves[self.valve_key(room_id, v)]
                for v in room.valves
            ]
            share = sum(positions) / len(positions) if positions else 0.0
            self.thermal[room_id].step(
                dt_s,
                valves_open=share,
                travel_s=max((v.travel_s for v in room.valves), default=120.0),
                water_temp=self.water_temp if heating else None,
                outdoor=self.outdoor,
                window_open=self.windows[room_id],
            )

    # --- Persistence --------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the virtual house."""
        return {
            "boiler_on": self.boiler_on,
            "valves": dict(self.valves),
            "outdoor": self.outdoor,
            "thermal": {room_id: t.to_dict() for room_id, t in self.thermal.items()},
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore; faults and windows always start cleared."""
        self.boiler_on = bool(data.get("boiler_on", False))
        for key, value in data.get("valves", {}).items():
            if key in self.valves:
                self.valves[key] = bool(value)
        self.outdoor = float(data.get("outdoor", DEFAULT_OUTDOOR))
        for room_id, thermal in data.get("thermal", {}).items():
            if room_id in self.thermal:
                self.thermal[room_id] = RoomThermal.from_dict(thermal)
