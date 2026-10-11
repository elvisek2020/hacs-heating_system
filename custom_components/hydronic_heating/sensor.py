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
from .core.model import BoilerReason, SystemState, ValvePhysical, ValveStatus
from .core.room import RoomController
from .demo import DemoRoom
from .entity import DemoEntity, HydronicEntity
from .explain import detail
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
    attrs_fn: Callable[[RoomController, HydronicController], dict[str, Any]] | None = None


def _now(ctrl: HydronicController) -> datetime | None:
    return ctrl.last_step


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _valve_attrs(room: RoomController, ctrl: HydronicController) -> dict[str, Any]:
    """Why the valves of a room are in their position and until when."""
    found: dict[str, ValveStatus] = {
        v.entity_id: status
        for v in room.cfg.valves
        if (status := ctrl.valve_status.get(v.entity_id)) is not None
    }
    if not found:
        return {}
    first = next(iter(found.values()))
    attrs: dict[str, Any] = {"reason": first.reason.value, "until": _iso(first.until)}
    if len(found) > 1:
        attrs["valves"] = {
            entity_id: {"reason": status.reason.value, "until": _iso(status.until)}
            for entity_id, status in found.items()
        }
    return attrs


SYSTEM_SENSORS: tuple[SystemSensorDescription, ...] = (
    SystemSensorDescription(
        key="manual_ends_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda ctrl: ctrl.modes.manual_ends_at,
    ),
    SystemSensorDescription(
        key="boiler_hold_ends_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda ctrl: ctrl.boiler_status.until,
        attrs_fn=lambda ctrl: {"reason": ctrl.boiler_status.reason.value},
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
            "forecast_24h": ctrl.outdoor.forecast,
            "effective": _round(ctrl.outdoor.effective),
        },
    ),
    SystemSensorDescription(
        key="flow_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda ctrl: ctrl.flow_setpoint,
        attrs_fn=lambda ctrl: {
            "outdoor_effective": _round(ctrl.outdoor.effective),
            "virtual": True,
        },
    ),
    SystemSensorDescription(
        key="duty_limit",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ctrl: None if ctrl.duty is None else round(ctrl.duty * 100),
        attrs_fn=lambda ctrl: {
            "enabled": ctrl.cfg.duty_enabled,
            "cycle_min": round(ctrl.cfg.boiler_cycle_period_s / 60),
            "run_per_cycle_min": None
            if ctrl.duty is None
            else round(
                max(ctrl.duty * ctrl.cfg.boiler_cycle_period_s, ctrl.cfg.boiler_min_on_s) / 60, 1
            ),
            "holding": ctrl.last_step is not None and ctrl.sequencer.duty_holding(ctrl.last_step),
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
        attrs_fn=lambda room, ctrl: {
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
        attrs_fn=_valve_attrs,
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
    async_add_entities([BoilerReasonSensor(runtime)])
    for room in runtime.rooms:
        async_add_entities(
            (RoomSensor(runtime, d, room) for d in ROOM_SENSORS),
            config_subentry_id=room.room_id,
        )
    if runtime.layout is not None and runtime.layout.house:
        for demo_room in runtime.layout.rooms:
            async_add_entities(
                [DemoTemperatureSensor(runtime, demo_room)],
                config_subentry_id=demo_room.room.room_id,
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
        return self.entity_description.attrs_fn(self.room, self.controller)


class BoilerReasonSensor(HydronicEntity, SensorEntity):
    """Why the boiler is on or off, with the end of the time rule (FR-SAFE-07)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [r.value for r in BoilerReason]
    # The countdown changes on every step; keep it out of the history.
    _unrecorded_attributes = frozenset({"remaining_s"})

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        """Initialize."""
        super().__init__(runtime, "sensor", "boiler_reason")

    @property
    def native_value(self) -> str:
        """Reason code, translated by the frontend."""
        return self.controller.boiler_status.reason.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """End of the rule, remaining time, the rule and a readable sentence."""
        status = self.controller.boiler_status
        now = self.controller.last_step
        remaining = (
            max(0, int((status.until - now).total_seconds()))
            if status.until is not None and now is not None
            else None
        )
        return {
            "until": _iso(status.until),
            "remaining_s": remaining,
            "rule": status.rule,
            "detail": detail(self.hass, status),
        }


class DemoTemperatureSensor(DemoEntity, SensorEntity):
    """Simulated room temperature of the virtual house."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, runtime: HydronicHeatingRuntime, demo_room: DemoRoom) -> None:
        """Initialize."""
        super().__init__(runtime, "sensor", "demo_temperature", demo_room.room)

    @property
    def available(self) -> bool:
        """Unavailable while a sensor fault is simulated."""
        return self.simulator.room_temperature(self.room_id) is not None

    @property
    def native_value(self) -> float | None:
        """Simulated temperature."""
        return self.simulator.room_temperature(self.room_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Internal state of the thermal model."""
        thermal = self.simulator.thermal[self.room_id]
        return {
            "radiator": round(thermal.radiator, 1),
            "valve_opening": round(thermal.opening, 2),
        }
