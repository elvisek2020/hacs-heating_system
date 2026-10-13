"""Room controller: temperature, target, demand, windows and valve PWM.

Chapter 11.1 (demand), 11.4 (windows), FR-MODE-02 (presets and override),
FR-SCH-02 (presence) and FR-SCH-03 (preheating).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .aggregation import aggregate
from .model import (
    EntityReading,
    Preset,
    RoomConfig,
    RoomHvacMode,
    Snapshot,
    TargetReason,
    ValvePhysical,
    WindowState,
)
from .presence import BOILER_START_S, PREHEAT_TOLERANCE, HeatRate, read_next_event, read_presence
from .valve import ValveState, pwm_open

FROST_HYSTERESIS_K = 2.0
NOT_REACHED_DEFICIT_K = 1.5
NOT_REACHED_AFTER_S = 3 * 3600
SENSOR_FAILURE_REPORT_S = 5 * 60
UTC_ZONE = ZoneInfo("UTC")


@dataclass(frozen=True, slots=True)
class RoomContext:
    """System-level inputs a room needs for one step."""

    now: datetime
    heating_allowed: bool
    away: bool
    outdoor_now: float | None
    outdoor_damped: float | None
    window_open_delay_s: float
    window_close_delay_s: float
    window_outdoor_condition: bool
    window_max_block_s: float
    # FR-SCH-01: schedule of the whole house, used by rooms without their own.
    house_schedule_entity: str | None = None
    house_presence_entity: str | None = None
    house_present: bool | None = None
    long_away: bool = False
    expected_return: datetime | None = None
    absence_preset: str = "eco"
    preheat_enabled: bool = False
    preheat_max_s: float = 4 * 3600
    timezone: ZoneInfo = UTC_ZONE
    manual: bool = False
    # Why heating is not allowed: "summer" or "off" (None = allowed).
    no_heat_reason: str | None = None

    @property
    def house_absent(self) -> bool:
        """Nobody is home (short or long absence)."""
        return self.house_present is False or self.long_away


@dataclass(slots=True)
class WindowMachine:
    """Window state machine of one room (chapter 11.4)."""

    state: WindowState = WindowState.CLOSED
    since: datetime | None = None
    blocked_since: datetime | None = None
    condition_ok: bool = True
    long_block: bool = False

    @property
    def effective_open(self) -> bool:
        """Heating of the room is blocked."""
        return self.state in (WindowState.BLOCKED, WindowState.PENDING_CLOSE)

    @property
    def counts_for_global(self) -> bool:
        """The room counts towards the global window threshold (FR-WIN-04)."""
        return self.state is WindowState.BLOCKED or (
            self.state is WindowState.PENDING_OPEN and self.condition_ok
        )

    def _enter(self, state: WindowState, now: datetime) -> None:
        self.state = state
        self.since = now

    def update(self, raw_open: bool, condition_ok: bool, ctx: RoomContext) -> None:
        """Advance the state machine."""
        now = ctx.now
        self.condition_ok = condition_ok
        elapsed = (now - self.since).total_seconds() if self.since else 0.0
        if self.state is WindowState.CLOSED:
            if raw_open:
                self._enter(WindowState.PENDING_OPEN, now)
        elif self.state is WindowState.PENDING_OPEN:
            if not raw_open:
                self._enter(WindowState.CLOSED, now)
            elif elapsed >= ctx.window_open_delay_s and condition_ok:
                self._enter(WindowState.BLOCKED, now)
                self.blocked_since = now
        elif self.state is WindowState.BLOCKED:
            if not raw_open:
                self._enter(WindowState.PENDING_CLOSE, now)
        elif self.state is WindowState.PENDING_CLOSE:
            if raw_open:
                self._enter(WindowState.BLOCKED, now)
            elif elapsed >= ctx.window_close_delay_s:
                self._enter(WindowState.CLOSED, now)
                self.blocked_since = None
        # FR-WIN-05: report a long block; the room then only keeps frost protection.
        self.long_block = (
            self.blocked_since is not None
            and self.effective_open
            and (now - self.blocked_since).total_seconds() >= ctx.window_max_block_s
        )


class RoomController:
    """State and decisions of one room."""

    def __init__(self, cfg: RoomConfig) -> None:
        """Initialize with defaults; persistent state is restored separately."""
        self.cfg = cfg
        # User state (persisted)
        self.hvac_mode = RoomHvacMode.AUTO
        self.preset = Preset.COMFORT
        self.manual_target: float | None = None
        self.override_since: datetime | None = None
        self.last_valid_temp: float | None = None
        self.last_valid_at: datetime | None = None
        # Derived state
        self.temperature: float | None = None
        self.valid_sources: tuple[str, ...] = ()
        self.invalid_sources: tuple[str, ...] = ()
        self.sensor_failure = False
        self.sensor_failure_since: datetime | None = None
        self.fallback_active = False
        self.frost_active = False
        self.calling = False
        self.demand = 0.0
        self.target: float | None = None
        self.schedule_entity: str | None = None
        self.schedule_on: bool | None = None
        self.schedule_next: datetime | None = None
        self.present: bool | None = None
        # Preset whose temperature the room uses in auto (shown on the climate).
        self.auto_preset = Preset.COMFORT
        # Preheating (FR-SCH-03): learned rate, latched target time, next start.
        self.heat_rate = HeatRate()
        self.preheat_until: datetime | None = None
        self.preheat_source: str | None = None
        self.preheat_planned: datetime | None = None
        # Why the room has its target, which presence entity it follows and until when.
        self.target_reason = TargetReason.COMFORT
        self.target_until: datetime | None = None
        self.presence_entity: str | None = None
        self.presence_source = "none"
        self.window = WindowMachine()
        self.valves: dict[str, ValveState] = {v.entity_id: ValveState() for v in cfg.valves}
        self.valve_open_cmd: bool | None = None
        self.valve_switched_at: datetime | None = None
        self.valve_forced = False
        self.heating_since: datetime | None = None
        self.not_reached = False

    # --- User actions (FR-MODE-02) ----------------------------------------

    def set_hvac_mode(self, mode: RoomHvacMode, now: datetime) -> None:
        """Set the HVAC mode; `auto` returns the room to its schedule."""
        self.hvac_mode = mode
        if mode is RoomHvacMode.HEAT:
            self.override_since = self.override_since or now
        else:
            self.override_since = None

    def set_preset(self, preset: Preset, now: datetime) -> None:
        """Choose a preset; in `auto` this is a permanent override (heat)."""
        if preset is Preset.NONE and self.manual_target is None:
            self.manual_target = self.target or self.cfg.comfort_temp
        self.preset = preset
        if self.hvac_mode is not RoomHvacMode.HEAT:
            self.set_hvac_mode(RoomHvacMode.HEAT, now)

    def set_target(self, temperature: float, now: datetime) -> None:
        """Set a manual target; in `auto` this is a permanent override (heat)."""
        self.manual_target = temperature
        self.preset = Preset.NONE
        if self.hvac_mode is not RoomHvacMode.HEAT:
            self.set_hvac_mode(RoomHvacMode.HEAT, now)

    def sensor_failure_reported(self, now: datetime) -> bool:
        """Return True when all sensors failed long enough to report it.

        Sensors that load slowly after a restart do not cause a notification.
        """
        return (
            self.sensor_failure_since is not None
            and (now - self.sensor_failure_since).total_seconds() >= SENSOR_FAILURE_REPORT_S
        )

    @property
    def override_active(self) -> bool:
        """The schedule is not followed because of a manual change."""
        return self.hvac_mode is RoomHvacMode.HEAT

    @property
    def effective_preset(self) -> Preset:
        """Preset shown on the climate entity."""
        if self.hvac_mode is RoomHvacMode.HEAT:
            return self.preset
        return self.auto_preset

    @property
    def preheating(self) -> bool:
        """The room heats to comfort ahead of a schedule change or a return."""
        return self.preheat_until is not None

    # --- Inputs -----------------------------------------------------------

    def _read_temperature(self, snap: Snapshot) -> None:
        cfg = self.cfg
        agg = aggregate(
            cfg.sensors,
            dict(snap.entities),
            snap.now,
            method=cfg.aggregation,
            minimum=cfg.sensor_min,
            maximum=cfg.sensor_max,
            stale_timeout_s=cfg.stale_timeout_s,
        )
        self.valid_sources, self.invalid_sources = agg.valid, agg.invalid
        if agg.value is not None:
            self.temperature = agg.value
            self.last_valid_temp, self.last_valid_at = agg.value, snap.now
            self.sensor_failure = self.fallback_active = False
            self.sensor_failure_since = None
            return
        # FR-ROOM-05: last known value for fallback_hold, then the configured fallback.
        self.sensor_failure = self.fallback_active = True
        self.sensor_failure_since = self.sensor_failure_since or snap.now
        within_hold = (
            self.last_valid_at is not None
            and (snap.now - self.last_valid_at).total_seconds() <= cfg.fallback_hold_s
        )
        if within_hold or cfg.sensor_fallback == "last_known":
            self.temperature = self.last_valid_temp
        else:
            self.temperature = None

    @staticmethod
    def _bool_state(reading: EntityReading, true_states: set[str]) -> bool | None:
        if not reading.available:
            return None
        return reading.state in true_states

    def _read_windows(self, snap: Snapshot) -> bool:
        open_state = "off" if self.cfg.window_invert else "on"
        return any(snap.get(e).state == open_state for e in self.cfg.windows)

    def _read_presence(self, snap: Snapshot) -> bool | None:
        return read_presence(snap.get(self.cfg.presence_entity))

    # --- Step -------------------------------------------------------------

    def target_temp(self, ctx: RoomContext) -> float | None:
        """Return the target temperature without preheating, None when not heating.

        Priority: system away > permanent manual change > long absence >
        absence > schedule (FR-SCH-02).
        """
        cfg = self.cfg
        self.auto_preset = Preset.COMFORT
        if self.hvac_mode is RoomHvacMode.OFF or not ctx.heating_allowed:
            return None
        if ctx.away:
            self.auto_preset = Preset.AWAY
            return cfg.away_temp
        if self.hvac_mode is RoomHvacMode.HEAT:
            if self.preset is Preset.NONE:
                return self.manual_target if self.manual_target is not None else cfg.comfort_temp
            return cfg.temp_for(self.preset)
        if ctx.long_away:
            self.auto_preset = Preset.AWAY
            return cfg.away_temp
        if self.present is False or ctx.house_present is False:
            self.auto_preset = Preset(ctx.absence_preset)
            return cfg.temp_for(self.auto_preset)
        if self.schedule_on is False:
            self.auto_preset = Preset.ECO
            return cfg.eco_temp
        return cfg.comfort_temp

    # --- Preheating (FR-SCH-03) ----------------------------------------------

    def preheat_lead_s(self, outdoor: float | None, temperature: float, max_s: float) -> float:
        """Time needed to reach comfort: valve travel, boiler start and the heat-up."""
        dead_s = max((v.open_time_s for v in self.cfg.valves), default=0) + BOILER_START_S
        deficit = max(0.0, self.cfg.comfort_temp - temperature)
        return min(max_s, dead_s + deficit / self.heat_rate.rate(outdoor) * 3600)

    def _comfort_at(self, when: datetime, ctx: RoomContext) -> bool:
        """Whether the room will want comfort at `when` (schedule and presence)."""
        if self.schedule_entity and self.schedule_on is not None:
            following = self.schedule_next
            if self.schedule_on and following is not None and following <= when:
                return False
            if not self.schedule_on and (following is None or following > when):
                return False
        if self.present is False:
            return False
        if ctx.house_absent:
            return ctx.expected_return is not None and ctx.expected_return <= when
        return True

    def _update_preheat(self, ctx: RoomContext, base: float | None) -> None:
        """Start heating to comfort early enough for the next comfort period."""
        now = ctx.now
        self.preheat_planned = None
        if (
            not ctx.preheat_enabled
            or ctx.away
            or base is None
            or self.hvac_mode is not RoomHvacMode.AUTO
            or base >= self.cfg.comfort_temp
            or self.temperature is None
            or self.window.effective_open
        ):
            self.preheat_until = self.preheat_source = None
            return
        candidates: list[tuple[datetime, str]] = []
        if self.schedule_on is False and self.schedule_next is not None:
            candidates.append((self.schedule_next, "schedule"))
        if ctx.house_absent and ctx.expected_return is not None:
            candidates.append((ctx.expected_return, "return"))
        valid = [(t, src) for t, src in candidates if t > now and self._comfort_at(t, ctx)]
        if not valid:
            self.preheat_until = self.preheat_source = None
            return
        when, source = min(valid)
        if (
            self.preheat_until is not None
            and now < self.preheat_until
            and abs(when - self.preheat_until) <= PREHEAT_TOLERANCE
        ):
            return  # keep a running preheat; the shrinking lead must not stop it
        lead = self.preheat_lead_s(ctx.outdoor_damped, self.temperature, ctx.preheat_max_s)
        start = when - timedelta(seconds=lead)
        if now >= start:
            self.preheat_until, self.preheat_source = when, source
        else:
            self.preheat_until = self.preheat_source = None
            self.preheat_planned = start

    def update(self, snap: Snapshot, ctx: RoomContext) -> None:
        """Read inputs and compute target and demand."""
        self._read_temperature(snap)
        # The room's own schedule wins over the schedule of the house.
        self.schedule_entity = self.cfg.schedule_entity or ctx.house_schedule_entity
        if self.schedule_entity:
            reading = snap.get(self.schedule_entity)
            self.schedule_on = self._bool_state(reading, {"on"})
            self.schedule_next = read_next_event(reading, ctx.timezone)
        else:
            self.schedule_on = self.schedule_next = None
        self.present = self._read_presence(snap) if self.cfg.presence_entity else None
        condition_ok = (
            not ctx.window_outdoor_condition
            or ctx.outdoor_now is None
            or self.temperature is None
            or ctx.outdoor_now < self.temperature
        )
        self.window.update(self._read_windows(snap), condition_ok, ctx)
        base = self.target_temp(ctx)
        self._update_preheat(ctx, base)
        if self.preheating:
            self.auto_preset = Preset.COMFORT
        self.target = self.cfg.comfort_temp if self.preheating else base
        self.demand = self._compute_demand(ctx)
        self._track_not_reached(ctx.now)
        self._explain_target(ctx)

    def _explain_target(self, ctx: RoomContext) -> None:
        """Reason of the target, in the priority the controller applies it."""
        if self.cfg.presence_entity:
            self.presence_entity, self.presence_source = self.cfg.presence_entity, "room"
        elif ctx.house_presence_entity:
            self.presence_entity, self.presence_source = ctx.house_presence_entity, "house"
        else:
            self.presence_entity, self.presence_source = None, "none"
        reason, until = self._target_reason(ctx)
        self.target_reason, self.target_until = reason, until

    def _target_reason(self, ctx: RoomContext) -> tuple[TargetReason, datetime | None]:
        if self.frost_active:
            return TargetReason.FROST, None
        if self.window.effective_open:
            return TargetReason.WINDOW, None
        if ctx.manual:
            return TargetReason.MANUAL, None
        if self.hvac_mode is RoomHvacMode.OFF:
            return TargetReason.ROOM_OFF, None
        if not ctx.heating_allowed:
            return (
                TargetReason.SUMMER if ctx.no_heat_reason == "summer" else TargetReason.SYSTEM_OFF
            ), None
        if ctx.away:
            return TargetReason.SYSTEM_AWAY, None
        if self.hvac_mode is RoomHvacMode.HEAT:
            return TargetReason.OVERRIDE, None
        if self.preheating:
            return TargetReason.PREHEAT, self.preheat_until
        if ctx.long_away:
            return TargetReason.LONG_AWAY, ctx.expected_return
        if self.present is False or ctx.house_present is False:
            return TargetReason.ABSENT, ctx.expected_return
        if self.schedule_on is False:
            return TargetReason.SCHEDULE_ECO, self.schedule_next
        if self.schedule_on:
            return TargetReason.SCHEDULE_COMFORT, self.schedule_next
        return TargetReason.COMFORT, None

    def _compute_demand(self, ctx: RoomContext) -> float:
        cfg = self.cfg
        t = self.temperature
        # 1) Frost protection first, it overrides windows and modes (FR-FROST-01).
        if t is not None:
            if t < cfg.frost_temp:
                self.frost_active = True
            elif t > cfg.frost_temp + FROST_HYSTERESIS_K:
                self.frost_active = False
        if self.frost_active:
            return 100.0
        # 2) No heating into an open window, not even on sensor failure.
        if self.window.effective_open:
            return 0.0
        target = self.target
        if target is None:
            self.calling = False
            return 0.0
        # 3) All sensors failed (FR-ROOM-05).
        if t is None:
            return 100.0 if cfg.sensor_fallback == "valve_open" else cfg.fallback_demand
        if cfg.algorithm == "hysteresis":
            if t < target - cfg.cold_tolerance:
                self.calling = True
            elif t > target + cfg.hot_tolerance:
                self.calling = False
            return 100.0 if self.calling else 0.0
        t_out = ctx.outdoor_damped if ctx.outdoor_damped is not None else target
        power = cfg.tpi_coef_int * (target - t) + cfg.tpi_coef_ext * (target - t_out)
        return round(max(0.0, min(100.0, power * 100.0)), 1)

    def _track_not_reached(self, now: datetime) -> None:
        """Deviation > 1.5 K after 3 h of heating (FR-SAFE-04)."""
        deficit = (
            self.target - self.temperature
            if self.target is not None and self.temperature is not None
            else None
        )
        if self.demand > 0 and deficit is not None and deficit > NOT_REACHED_DEFICIT_K:
            self.heating_since = self.heating_since or now
            self.not_reached = (now - self.heating_since).total_seconds() >= NOT_REACHED_AFTER_S
        else:
            self.heating_since = None
            self.not_reached = False

    # --- Valves -----------------------------------------------------------

    def decide_open(self, want: bool | None, now: datetime, *, forced: bool) -> bool | None:
        """Apply the minimum valve state time to a room-level decision (FR-VAL-05).

        Only PWM decisions wait for the minimum state time. Forced decisions
        (window, frost, manual, modes) and the return from them apply at once.
        """
        current = self.valve_open_cmd
        if (
            want is None
            or current is None
            or forced
            or self.valve_forced
            or want == current
            or self.valve_switched_at is None
            or (now - self.valve_switched_at).total_seconds() >= self.cfg.min_state_s
        ):
            if want != current:
                self.valve_switched_at = now
            self.valve_open_cmd = want
            self.valve_forced = forced
            return want
        return current

    def pwm_want(self, now: datetime) -> bool:
        """Open or closed according to the demand and the PWM period."""
        return pwm_open(now, self.demand, self.cfg.pwm_period_s, self.cfg.min_state_s)

    def valve_summary(self, now: datetime) -> str:
        """Summary state of all valves of the room."""
        states = {self.valves[v.entity_id].physical(v, now) for v in self.cfg.valves}
        if len(states) == 1:
            return next(iter(states)).value
        if states <= {ValvePhysical.OPEN, ValvePhysical.OPENING}:
            return ValvePhysical.OPENING.value
        if states <= {ValvePhysical.CLOSED, ValvePhysical.CLOSING}:
            return ValvePhysical.CLOSING.value
        return "mixed"

    # --- Persistence ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize user state and valve positions."""
        return {
            "hvac_mode": self.hvac_mode.value,
            "preset": self.preset.value,
            "manual_target": self.manual_target,
            "override_since": self.override_since.isoformat() if self.override_since else None,
            "last_valid_temp": self.last_valid_temp,
            "last_valid_at": self.last_valid_at.isoformat() if self.last_valid_at else None,
            "valves": {key: state.to_dict() for key, state in self.valves.items()},
            "heat_rate": self.heat_rate.to_dict(),
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore user state and valve positions."""
        self.hvac_mode = RoomHvacMode(data.get("hvac_mode", RoomHvacMode.AUTO))
        self.preset = Preset(data.get("preset", Preset.COMFORT))
        self.manual_target = data.get("manual_target")
        if since := data.get("override_since"):
            self.override_since = datetime.fromisoformat(since)
        self.last_valid_temp = data.get("last_valid_temp")
        if at := data.get("last_valid_at"):
            self.last_valid_at = datetime.fromisoformat(at)
        for key, valve in data.get("valves", {}).items():
            if key in self.valves:
                self.valves[key] = ValveState.from_dict(valve)
        self.heat_rate.restore(data.get("heat_rate"))
