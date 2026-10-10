"""Room controller: temperature, target, demand, windows and valve PWM.

Chapter 11.1 (demand), 11.4 (windows), FR-MODE-02 (presets and override).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .aggregation import aggregate
from .model import (
    EntityReading,
    Preset,
    RoomConfig,
    RoomHvacMode,
    Snapshot,
    ValvePhysical,
    WindowState,
)
from .valve import ValveState, pwm_open

FROST_HYSTERESIS_K = 2.0
NOT_REACHED_DEFICIT_K = 1.5
NOT_REACHED_AFTER_S = 3 * 3600
SENSOR_FAILURE_REPORT_S = 5 * 60

PRESENT_STATES = {"on", "home"}
ABSENT_STATES = {"off", "not_home", "away"}


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
        self.schedule_on: bool | None = None
        self.present: bool | None = None
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
        if self.present is False:
            return Preset.AWAY
        if self.schedule_on is False:
            return Preset.ECO
        return Preset.COMFORT

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
        reading = snap.get(self.cfg.presence_entity)
        if not reading.available:
            return None
        if reading.state in PRESENT_STATES:
            return True
        if reading.state in ABSENT_STATES:
            return False
        return None

    # --- Step -------------------------------------------------------------

    def target_temp(self, ctx: RoomContext) -> float | None:
        """Return the target temperature, None when the room should not heat."""
        cfg = self.cfg
        if self.hvac_mode is RoomHvacMode.OFF or not ctx.heating_allowed:
            return None
        if ctx.away:
            return cfg.away_temp
        if self.hvac_mode is RoomHvacMode.HEAT:
            if self.preset is Preset.NONE:
                return self.manual_target if self.manual_target is not None else cfg.comfort_temp
            return cfg.temp_for(self.preset)
        if self.present is False:
            return cfg.away_temp
        if self.schedule_on is False:
            return cfg.eco_temp
        return cfg.comfort_temp

    def update(self, snap: Snapshot, ctx: RoomContext) -> None:
        """Read inputs and compute target and demand."""
        self._read_temperature(snap)
        if self.cfg.schedule_entity:
            self.schedule_on = self._bool_state(snap.get(self.cfg.schedule_entity), {"on"})
        self.present = self._read_presence(snap) if self.cfg.presence_entity else None
        condition_ok = (
            not ctx.window_outdoor_condition
            or ctx.outdoor_now is None
            or self.temperature is None
            or ctx.outdoor_now < self.temperature
        )
        self.window.update(self._read_windows(snap), condition_ok, ctx)
        self.target = self.target_temp(ctx)
        self.demand = self._compute_demand(ctx)
        self._track_not_reached(ctx.now)

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
