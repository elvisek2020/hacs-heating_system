"""Climate entities: the system summary and one thermostat per room."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .core.model import BoilerPhase, RoomHvacMode, SystemMode, SystemState
from .entity import HydronicEntity
from .runtime import HydronicConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the system climate and one climate per room."""
    runtime = entry.runtime_data
    async_add_entities([SystemClimate(runtime)])
    for room in runtime.rooms:
        async_add_entities([RoomClimate(runtime, room)], config_subentry_id=room.room_id)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


class SystemClimate(HydronicEntity, ClimateEntity):
    """Summary of the whole system (`climate.hh_system`)."""

    _attr_name = None
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, runtime: Any) -> None:
        """Initialize."""
        super().__init__(runtime, "climate", "system")
        self._attr_translation_key = None

    @property
    def hvac_mode(self) -> HVACMode:
        """Map the system mode (FR-MODE-01)."""
        mode = self.controller.modes.mode
        if mode is SystemMode.OFF:
            return HVACMode.OFF
        if mode is SystemMode.MANUAL:
            return HVACMode.HEAT
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction:
        """What the boiler does now."""
        ctrl = self.controller
        if ctrl.sequencer.boiler_on and not ctrl.fault_safe:
            return HVACAction.HEATING
        if ctrl.sequencer.phase is BoilerPhase.PRE_OPEN:
            return HVACAction.PREHEATING
        if ctrl.state in (SystemState.OFF, SystemState.SUMMER, SystemState.FAULT_SAFE):
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Outdoor temperature, when configured."""
        return self.controller.outdoor.current

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes listed in PRD chapter 9.1."""
        ctrl = self.controller
        now = ctrl.last_step
        seq = ctrl.sequencer
        attrs: dict[str, Any] = {
            "mode": ctrl.modes.mode.value,
            "state": ctrl.state.value,
            "manual_ends_at": _iso(ctrl.modes.manual_ends_at),
            "manual_remaining_s": ctrl.modes.remaining_s(now) if now else None,
            "boiler_phase": seq.phase.value,
            "boiler_on_since": _iso(seq.on_since) if seq.boiler_on else None,
            "boiler_off_since": _iso(seq.off_since) if not seq.boiler_on else None,
            "next_allowed_start": _iso(seq.next_allowed_start(now, ctrl.cfg)) if now else None,
            "min_on_until": _iso(seq.min_on_until(ctrl.cfg)),
            "min_off_until": _iso(seq.min_off_until(ctrl.cfg)),
            "starts_last_hour": seq.starts_last_hour(now) if now else None,
            "boiler_reason": ctrl.boiler_status.reason.value,
            "hold_until": _iso(ctrl.boiler_status.until),
            "rooms_calling": ctrl.arbitration.calling,
            "blocked_by": ctrl.blocked_by,
            "fault_reason": ctrl.fault_reason,
            "burner_running": ctrl.burner_running,
            "last_transition": ctrl.modes.last_transition,
            "last_command_latency_ms": ctrl.tracker.state("boiler").latency_ms,
            "last_reverted_override": ctrl.last_revert,
            "presence": ctrl.presence_state,
            "expected_return": _iso(ctrl.expected_return),
        }
        if ctrl.cfg.shadow_mode:
            would = ctrl.would_command()
            attrs["would_command_boiler"] = would["boiler"]
            attrs["would_command_valves"] = would["valves"]
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Off, auto, or heat (= manual with the first duration)."""
        mode = {
            HVACMode.OFF: SystemMode.OFF,
            HVACMode.AUTO: SystemMode.AUTO,
            HVACMode.HEAT: SystemMode.MANUAL,
        }[hvac_mode]
        self.runtime.set_mode(mode.value)

    async def async_turn_on(self) -> None:
        """Switch the system to auto."""
        self.runtime.set_mode(SystemMode.AUTO.value)

    async def async_turn_off(self) -> None:
        """Switch the system off (frost protection stays active)."""
        self.runtime.set_mode(SystemMode.OFF.value)


class RoomClimate(HydronicEntity, ClimateEntity):
    """Thermostat of one room (`climate.hh_<room>`, FR-MODE-02)."""

    _attr_name = None
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY, PRESET_NONE]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 5
    _attr_max_temp = 30

    def __init__(self, runtime: Any, room: Any) -> None:
        """Initialize."""
        super().__init__(runtime, "climate", "", room)

    @property
    def current_temperature(self) -> float | None:
        """Aggregated room temperature."""
        return self.room.temperature

    @property
    def target_temperature(self) -> float | None:
        """Effective target; None when the room does not heat."""
        return self.room.target

    @property
    def hvac_mode(self) -> HVACMode:
        """Room HVAC mode."""
        return HVACMode(self.room.hvac_mode.value)

    @property
    def preset_mode(self) -> str:
        """Effective preset."""
        return self.room.effective_preset.value

    @property
    def hvac_action(self) -> HVACAction:
        """Heating when the room asks for heat, its valves are open and the boiler runs."""
        room = self.room
        ctrl = self.controller
        if room.hvac_mode is RoomHvacMode.OFF and not room.frost_active:
            return HVACAction.OFF
        if room.demand <= 0:
            return HVACAction.IDLE
        valves_open = any(ctrl.valve_desired.get(v.entity_id) for v in room.cfg.valves)
        if valves_open and ctrl.sequencer.boiler_on:
            return HVACAction.HEATING
        return HVACAction.PREHEATING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes listed in PRD chapter 9.2."""
        room = self.room
        ctrl = self.controller
        now = ctrl.last_step
        last_exercise = [
            ctrl.exercise.last_run[v.entity_id]
            for v in room.cfg.valves
            if v.entity_id in ctrl.exercise.last_run
        ]
        return {
            "demand": room.demand,
            "sources": list(room.valid_sources),
            "invalid_sources": list(room.invalid_sources),
            "aggregation": room.cfg.aggregation,
            "fallback_active": room.fallback_active,
            "valves": {
                v.entity_id: room.valves[v.entity_id].physical(v, now).value
                for v in room.cfg.valves
            }
            if now
            else {},
            "window_state": room.window.state.value,
            "window_since": _iso(room.window.since),
            "frost_active": room.frost_active,
            "schedule_entity": room.schedule_entity,
            "schedule_state": room.schedule_on,
            "schedule_next": _iso(room.schedule_next),
            "presence": room.present,
            "preheating": room.preheating,
            "preheat_until": _iso(room.preheat_until),
            "preheat_planned": _iso(room.preheat_planned),
            "heat_rate_k_h": room.heat_rate.rate(ctrl.outdoor.damped),
            "heat_rate_samples": room.heat_rate.count,
            "override_active": room.override_active,
            "override_since": _iso(room.override_since),
            "last_exercise": _iso(max(last_exercise)) if last_exercise else None,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Manual target; in auto this is a permanent override."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self.runtime.set_room_target(self.room_id, float(temperature))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Choose a preset; in auto this is a permanent override."""
        self.runtime.set_room_preset(self.room_id, preset_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Auto returns to the schedule."""
        self.runtime.set_room_hvac_mode(self.room_id, hvac_mode.value)

    async def async_turn_on(self) -> None:
        """Return the room to auto."""
        self.runtime.set_room_hvac_mode(self.room_id, RoomHvacMode.AUTO.value)

    async def async_turn_off(self) -> None:
        """Room off: frost protection only."""
        self.runtime.set_room_hvac_mode(self.room_id, RoomHvacMode.OFF.value)
