"""Binary sensors of the system and of each room (PRD chapter 9)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .core.controller import HydronicController
from .core.room import RoomController
from .entity import HydronicEntity
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SystemBinaryDescription(BinarySensorEntityDescription):
    """System binary sensor."""

    is_on_fn: Callable[[HydronicController], bool]
    attrs_fn: Callable[[HydronicController], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class RoomBinaryDescription(BinarySensorEntityDescription):
    """Room binary sensor."""

    is_on_fn: Callable[[HydronicController, RoomController], bool]
    attrs_fn: Callable[[HydronicController, RoomController], dict[str, Any]] | None = None


def _room_valve_failures(ctrl: HydronicController, room: RoomController) -> list[str]:
    return [v.entity_id for v in room.cfg.valves if ctrl.tracker.failed(v.entity_id)]


SYSTEM_BINARY: tuple[SystemBinaryDescription, ...] = (
    SystemBinaryDescription(key="heat_demand", is_on_fn=lambda ctrl: ctrl.heat_request),
    SystemBinaryDescription(
        key="boiler_command",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda ctrl: (
            ctrl.last_step is not None and ctrl.sequencer.boiler_on and not ctrl.fault_safe
        ),
        attrs_fn=lambda ctrl: {"phase": ctrl.sequencer.phase.value},
    ),
    SystemBinaryDescription(key="window_block", is_on_fn=lambda ctrl: ctrl.window_block),
    SystemBinaryDescription(
        key="summer",
        is_on_fn=lambda ctrl: ctrl.outdoor.summer,
        attrs_fn=lambda ctrl: {"damped": ctrl.outdoor.damped_rounded},
    ),
    SystemBinaryDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda ctrl: bool(ctrl.problems),
        attrs_fn=lambda ctrl: {"problems": sorted(ctrl.problems)},
    ),
)

ROOM_BINARY: tuple[RoomBinaryDescription, ...] = (
    RoomBinaryDescription(
        key="window",
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=lambda ctrl, room: room.window.effective_open,
        attrs_fn=lambda ctrl, room: {"state": room.window.state.value},
    ),
    RoomBinaryDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda ctrl, room: bool(
            room.invalid_sources or room.not_reached or _room_valve_failures(ctrl, room)
        ),
        attrs_fn=lambda ctrl, room: {
            "invalid_sensors": list(room.invalid_sources),
            "sensor_failure": room.sensor_failure,
            "temperature_not_reached": room.not_reached,
            "valve_failures": _room_valve_failures(ctrl, room),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add system and room binary sensors."""
    runtime = entry.runtime_data
    async_add_entities(SystemBinarySensor(runtime, d) for d in SYSTEM_BINARY)
    for room in runtime.rooms:
        async_add_entities(
            (RoomBinarySensor(runtime, d, room) for d in ROOM_BINARY),
            config_subentry_id=room.room_id,
        )


class SystemBinarySensor(HydronicEntity, BinarySensorEntity):
    """Binary sensor of the heating system."""

    entity_description: SystemBinaryDescription

    def __init__(self, runtime: HydronicHeatingRuntime, description: SystemBinaryDescription):
        """Initialize."""
        super().__init__(runtime, "binary_sensor", description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Current state."""
        return self.entity_description.is_on_fn(self.controller)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.controller)


class RoomBinarySensor(HydronicEntity, BinarySensorEntity):
    """Binary sensor of one room."""

    entity_description: RoomBinaryDescription

    def __init__(
        self, runtime: HydronicHeatingRuntime, description: RoomBinaryDescription, room: Any
    ) -> None:
        """Initialize."""
        super().__init__(runtime, "binary_sensor", description.key, room)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Current state."""
        return self.entity_description.is_on_fn(self.controller, self.room)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.controller, self.room)
