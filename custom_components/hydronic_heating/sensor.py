"""Sensors of the system and of each room (PRD chapter 9)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .core.controller import HydronicController
from .core.model import SystemState, ValvePhysical
from .core.room import RoomController
from .entity import HydronicEntity
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SystemSensorDescription(SensorEntityDescription):
    """System sensor with a value function."""

    value_fn: Callable[[HydronicController], Any]
    attrs_fn: Callable[[HydronicController], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class RoomSensorDescription(SensorEntityDescription):
    """Room sensor with a value function."""

    value_fn: Callable[[RoomController, datetime | None], Any]
    attrs_fn: Callable[[RoomController], dict[str, Any]] | None = None


def _now(ctrl: HydronicController) -> datetime | None:
    return ctrl.last_step


SYSTEM_SENSORS: tuple[SystemSensorDescription, ...] = (
    SystemSensorDescription(
        key="manual_ends_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda ctrl: ctrl.modes.manual_ends_at,
    ),
    SystemSensorDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=[s.value for s in SystemState],
        value_fn=lambda ctrl: ctrl.state.value,
        attrs_fn=lambda ctrl: {"blocked_by": ctrl.blocked_by, "fault_reason": ctrl.fault_reason},
    ),
    SystemSensorDescription(
        key="demand_total",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ctrl: ctrl.arbitration.weighted,
        attrs_fn=lambda ctrl: {"rooms_calling": ctrl.arbitration.calling},
    ),
    SystemSensorDescription(
        key="outdoor_temperature_damped",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda ctrl: ctrl.outdoor.damped_rounded,
        attrs_fn=lambda ctrl: {
            "current": ctrl.outdoor.current,
            "source": ctrl.outdoor.source,
        },
    ),
    SystemSensorDescription(
        key="boiler_duty",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ctrl: ctrl.sequencer.duty_24h(_now(ctrl)) if _now(ctrl) else None,
    ),
    SystemSensorDescription(
        key="boiler_starts_today",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda ctrl: (
            ctrl.sequencer.starts_today(_now(ctrl), ctrl.cfg.timezone) if _now(ctrl) else None
        ),
    ),
    SystemSensorDescription(
        key="open_windows",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ctrl: ctrl.window_rooms(),
    ),
)

VALVE_STATES = [s.value for s in ValvePhysical] + ["mixed"]

ROOM_SENSORS: tuple[RoomSensorDescription, ...] = (
    RoomSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda room, now: room.temperature,
        attrs_fn=lambda room: {
            "sources": list(room.valid_sources),
            "invalid_sources": list(room.invalid_sources),
            "fallback_active": room.fallback_active,
        },
    ),
    RoomSensorDescription(
        key="demand",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda room, now: room.demand,
    ),
    RoomSensorDescription(
        key="valve_state",
        device_class=SensorDeviceClass.ENUM,
        options=VALVE_STATES,
        value_fn=lambda room, now: room.valve_summary(now) if now else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add system and room sensors."""
    runtime = entry.runtime_data
    async_add_entities(SystemSensor(runtime, d) for d in SYSTEM_SENSORS)
    for room in runtime.rooms:
        async_add_entities(
            (RoomSensor(runtime, d, room) for d in ROOM_SENSORS),
            config_subentry_id=room.room_id,
        )


class SystemSensor(HydronicEntity, SensorEntity):
    """Sensor of the heating system."""

    entity_description: SystemSensorDescription

    def __init__(self, runtime: HydronicHeatingRuntime, description: SystemSensorDescription):
        """Initialize."""
        super().__init__(runtime, "sensor", description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Current value."""
        return self.entity_description.value_fn(self.controller)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.controller)


class RoomSensor(HydronicEntity, SensorEntity):
    """Sensor of one room."""

    entity_description: RoomSensorDescription

    def __init__(
        self, runtime: HydronicHeatingRuntime, description: RoomSensorDescription, room: Any
    ) -> None:
        """Initialize."""
        super().__init__(runtime, "sensor", description.key, room)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Current value."""
        return self.entity_description.value_fn(self.room, self.controller.last_step)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.room)
