"""Controller: one deterministic control step from a Snapshot to a Plan."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from .. import const as c
from .equithermal import OutdoorEngine, duty_limit, flow_setpoint
from .exercise import ExerciseScheduler
from .heat_source import Arbitration, BoilerSequencer, RoomDemand, arbitrate
from .model import (
    BoilerPhase,
    Command,
    Plan,
    Problem,
    RoomConfig,
    RoomHvacMode,
    Snapshot,
    SystemConfig,
    SystemMode,
    SystemState,
    ValveConfig,
    ValvePhysical,
    WindowState,
)
from .modes import ModeManager
from .room import RoomContext, RoomController
from .safety import OutputTracker
from .valve import deenergized_open, observed_open

BOILER_KEY = "boiler"
CIRCULATION_S = 10 * 60
STORAGE_FORMAT = 1


class HydronicController:
    """Owns all control state; the runtime feeds snapshots and executes plans."""

    def __init__(self, system: SystemConfig, rooms: Iterable[RoomConfig]) -> None:
        """Create the controller from configuration."""
        self.cfg = system
        self.rooms: dict[str, RoomController] = {r.room_id: RoomController(r) for r in rooms}
        self.modes = ModeManager()
        self.outdoor = OutdoorEngine()
        self.sequencer = BoilerSequencer()
        self.exercise = ExerciseScheduler()
        self.tracker = OutputTracker()
        self.started_at: datetime | None = None
        self.ready = False
        self.state = SystemState.STARTUP
        self.summer = False
        self.flow_setpoint: float | None = None
        self.duty: float | None = None
        self.arbitration = Arbitration(False, 0.0, 0)
        self.heat_request = False
        self.window_block = False
        self._window_pending_since: datetime | None = None
        self.fault_safe = False
        self.fault_reason: str | None = None
        self._fault_clear_since: datetime | None = None
        self.boiler_observed: bool | None = None
        self.boiler_available = False
        self.burner_running: bool | None = None
        self.valve_desired: dict[str, bool] = {}
        self.exercising: set[str] = set()
        self.problems: dict[str, Problem] = {}
        self.blocked_by: list[str] = []
        self.last_step: datetime | None = None
        self._stop_immediate = False
        self._heartbeat_at: datetime | None = None
        self._circulation_until: datetime | None = None

    # --- Configuration ----------------------------------------------------

    def reconfigure(self, system: SystemConfig, rooms: Iterable[RoomConfig]) -> None:
        """Apply new configuration and keep the runtime state of existing rooms."""
        old = self.rooms
        self.cfg = system
        self.rooms = {}
        for room_cfg in rooms:
            room = RoomController(room_cfg)
            if previous := old.get(room_cfg.room_id):
                room.restore(previous.to_dict())
                room.frost_active = previous.frost_active
                room.calling = previous.calling
                room.window = previous.window
                room.valve_open_cmd = previous.valve_open_cmd
                room.valve_switched_at = previous.valve_switched_at
                room.valve_forced = previous.valve_forced
                room.heating_since = previous.heating_since
            self.rooms[room_cfg.room_id] = room
        if system.shadow_mode:
            self.tracker.reset()

    def watched_entities(self) -> set[str]:
        """Every entity whose state change should trigger a step."""
        cfg = self.cfg
        found: set[str] = {*cfg.heat_source.entities, *cfg.outdoor_sensors}
        for entity in (cfg.weather_entity, cfg.heat_source.feedback_entity):
            if entity:
                found.add(entity)
        for room in self.rooms.values():
            rc = room.cfg
            found.update(rc.sensors)
            found.update(rc.windows)
            found.update(v.entity_id for v in rc.valves)
            for entity in (rc.schedule_entity, rc.presence_entity):
                if entity:
                    found.add(entity)
        return found

    @property
    def valve_configs(self) -> list[tuple[RoomController, ValveConfig]]:
        """All valves with their room."""
        return [(room, v) for room in self.rooms.values() for v in room.cfg.valves]

    @property
    def simulating(self) -> bool:
        """Outputs are not switched: shadow mode or startup (FR-SAFE-01, FR-SAFE-05)."""
        return self.cfg.shadow_mode or not self.ready

    # --- User actions -----------------------------------------------------

    def set_mode(self, mode: SystemMode, now: datetime) -> None:
        """Select a system mode (FR-MODE-01)."""
        if mode is not SystemMode.MANUAL and self.modes.mode is SystemMode.MANUAL:
            self.stop(now, policy_override=mode)
            return
        self.modes.set_mode(mode, now, self.cfg.manual_durations[0])

    def start_manual(self, minutes: int, now: datetime) -> None:
        """Start manual heating (FR-MAN-01)."""
        self.modes.start_manual(minutes, now, self.cfg.manual_restart_policy)

    def stop(self, now: datetime, policy_override: SystemMode | None = None) -> None:
        """Stop manual heating (FR-MAN-03)."""
        if self.modes.stop(now, self.cfg.stop_policy):
            if policy_override is not None:
                self.modes.set_mode(policy_override, now, self.cfg.manual_durations[0])
            self._stop_immediate = not self.cfg.stop_respects_min_on

    # --- Step -------------------------------------------------------------

    def step(self, snap: Snapshot) -> Plan:
        """Run one control step."""
        now = snap.now
        cfg = self.cfg
        if self.started_at is None:
            self.started_at = now
        self.modes.tick(now)
        self.outdoor.update(snap, cfg)
        self._update_equithermal()
        self._update_ready(snap)

        mode = self.modes.mode
        manual = mode is SystemMode.MANUAL
        self.summer = mode is SystemMode.SUMMER or (
            mode in (SystemMode.AUTO, SystemMode.AWAY) and self.outdoor.summer
        )
        heating_allowed = manual or (not self.summer and mode is not SystemMode.OFF)

        ctx = RoomContext(
            now=now,
            heating_allowed=heating_allowed,
            away=mode is SystemMode.AWAY,
            outdoor_now=self.outdoor.current,
            outdoor_damped=self.outdoor.damped,
            window_open_delay_s=cfg.window_open_delay_s,
            window_close_delay_s=cfg.window_close_delay_s,
            window_outdoor_condition=cfg.window_outdoor_condition,
            window_max_block_s=cfg.window_max_block_s,
        )
        for room in self.rooms.values():
            room.update(snap, ctx)

        self._update_global_window(now)
        frost_request = self._frost_request(now)
        self.arbitration = arbitrate(
            [
                RoomDemand(r.demand, r.cfg.weight, r.cfg.area_m2, r.frost_active)
                for r in self.rooms.values()
            ],
            cfg,
            self.arbitration.request,
        )
        self.heat_request = self.arbitration.request or manual or frost_request
        # FR-MODE-03: frost and manual take priority over window block and summer.
        blocked = (
            (self.window_block or self.summer or mode is SystemMode.OFF)
            and not manual
            and not frost_request
        )

        self._observe_boiler(snap)
        self._observe_valves(snap)
        fully_open = self._valves_in(now, {ValvePhysical.OPEN})
        flow_ok = cfg.has_bypass or len(fully_open) >= cfg.min_open_valves
        self._update_fault(now)

        if self.fault_safe:
            self.sequencer.force_off(now)
        else:
            self.sequencer.step(
                now,
                cfg,
                request=self.heat_request,
                blocked=blocked,
                stop_immediate=self._stop_immediate,
                flow_ok=flow_ok,
                open_valves=self._valves_in(now, {ValvePhysical.OPEN, ValvePhysical.OPENING}),
                max_travel_s=max((v.travel_time_s for _, v in self.valve_configs), default=0),
                duty_run_s=self._duty_run_s(manual=manual),
            )
        self._stop_immediate = False

        self.valve_desired = self._plan_valves(now, manual=manual, heating_allowed=heating_allowed)
        boiler_on = self.sequencer.boiler_on and not self.fault_safe

        self.state = self._system_state(mode)
        self.blocked_by = self._blocked_by(now, blocked, flow_ok)
        self._collect_problems(now)
        self.last_step = now

        plan = Plan(boiler_on=boiler_on, valves_open=dict(self.valve_desired))
        if not self.simulating:
            plan.commands.extend(self._output_commands(snap, boiler_on))
        if heartbeat := self._heartbeat(now):
            plan.commands.append(heartbeat)
        return plan

    # --- Step helpers -----------------------------------------------------

    def _update_equithermal(self) -> None:
        """Heating curve and duty limit (FR-EQ-04, FR-EQ-05)."""
        outdoor = self.outdoor.effective
        if outdoor is None:
            self.flow_setpoint = self.duty = None
            return
        self.flow_setpoint = flow_setpoint(outdoor, self.cfg)
        self.duty = duty_limit(self.flow_setpoint, self.cfg)

    @property
    def duty_active(self) -> bool:
        """Return True when the duty limit restricts the boiler run time."""
        return self.cfg.duty_enabled and self.duty is not None and self.duty < 1.0

    def _duty_run_s(self, *, manual: bool) -> float | None:
        """Return the allowed run time per cycle; None in manual or without a curve."""
        if manual or not self.duty_active:
            return None
        return self.duty * self.cfg.boiler_cycle_period_s  # type: ignore[operator]

    def _update_ready(self, snap: Snapshot) -> None:
        """FR-SAFE-01: wait for required entities, at most startup_grace."""
        if self.ready:
            return
        required = [*self.cfg.heat_source.entities, *(v.entity_id for _, v in self.valve_configs)]
        elapsed = (snap.now - self.started_at).total_seconds()  # type: ignore[operator]
        if all(snap.get(e).available for e in required) or elapsed >= self.cfg.startup_grace_s:
            self.ready = True
            self.tracker.reset()
            # Decisions made while inputs were still loading must not hold the
            # valves for the minimum state time; start the valve logic afresh.
            for room in self.rooms.values():
                room.valve_open_cmd = None
                room.valve_switched_at = None
                room.valve_forced = False

    def _update_global_window(self, now: datetime) -> None:
        """FR-WIN-04: global window threshold with delay."""
        cfg = self.cfg
        rooms = list(self.rooms.values())
        counting = sum(1 for r in rooms if r.window.counts_for_global)
        if cfg.global_window_mode == "ratio":
            condition = bool(rooms) and counting / len(rooms) >= cfg.global_window_ratio
        elif cfg.global_window_mode == "any":
            condition = counting >= 1
        else:
            condition = counting >= cfg.global_window_count
        if not condition:
            self._window_pending_since = None
            self.window_block = False
            return
        self._window_pending_since = self._window_pending_since or now
        if (now - self._window_pending_since).total_seconds() >= cfg.global_window_delay_s:
            self.window_block = True

    def _frost_request(self, now: datetime) -> bool:
        """Room frost protection and optional circulation run (FR-FROST-01, 02)."""
        cfg = self.cfg
        if (
            cfg.frost_outdoor_protection
            and self.outdoor.current is not None
            and self.outdoor.current < cfg.frost_outdoor_temp
            and self.sequencer.phase is BoilerPhase.IDLE
            and self.sequencer.off_since is not None
            and (now - self.sequencer.off_since).total_seconds() >= cfg.frost_idle_max_s
            and self._circulation_until is None
        ):
            self._circulation_until = now + timedelta(seconds=CIRCULATION_S)
        if self._circulation_until is not None and now >= self._circulation_until:
            self._circulation_until = None
        return any(r.frost_active for r in self.rooms.values()) or (
            self._circulation_until is not None
        )

    def _observe_boiler(self, snap: Snapshot) -> None:
        hs = self.cfg.heat_source
        entities = hs.entities
        self.boiler_available = bool(entities) and all(snap.get(e).available for e in entities)
        feedback = snap.get(hs.feedback_entity)
        self.burner_running = feedback.state == "on" if feedback.available else None
        if self.simulating:
            self.boiler_observed = self.sequencer.boiler_on
            return
        reading = snap.get(hs.state_entity)
        if not reading.available:
            self.boiler_observed = None
        elif hs.type == c.HEAT_SOURCE_SELECT:
            if reading.state == hs.select_on:
                self.boiler_observed = True
            elif reading.state == hs.select_off:
                self.boiler_observed = False
            else:
                self.boiler_observed = None
        elif hs.type == c.HEAT_SOURCE_SWITCH:
            self.boiler_observed = reading.state == "on"
        else:
            self.boiler_observed = None

    def _observe_valves(self, snap: Snapshot) -> None:
        """Track valve positions; while simulating, assume commands are executed."""
        now = snap.now
        for room, valve in self.valve_configs:
            if self.simulating:
                position = self.valve_desired.get(valve.entity_id)
            else:
                position = observed_open(valve, snap.get(valve.entity_id))
            room.valves[valve.entity_id].observe(position, now)

    def _valves_in(self, now: datetime, states: set[ValvePhysical]) -> set[str]:
        """Valves whose modelled physical position is one of `states`."""
        return {
            valve.entity_id
            for room, valve in self.valve_configs
            if room.valves[valve.entity_id].physical(valve, now) in states
        }

    def _update_fault(self, now: datetime) -> None:
        """Enter and leave fault_safe (FR-SAFE-02)."""
        if not self.ready:
            return
        reason = None
        if not self.boiler_available:
            reason = "boiler_unavailable"
        elif not self.simulating and self.tracker.failed(BOILER_KEY):
            reason = "boiler_command"
        elif self.sequencer.no_flow:
            reason = "no_flow"
        if reason is not None:
            self.fault_reason = reason
            self.fault_safe = True
            self._fault_clear_since = None
            self.sequencer.no_flow = False
            return
        if not self.fault_safe:
            return
        healthy = self.boiler_available and (
            self.boiler_observed in (None, False) or self.simulating
        )
        valves_ok = not any(self.tracker.failed(v.entity_id) for _, v in self.valve_configs)
        if healthy and (self.fault_reason != "no_flow" or valves_ok):
            self._fault_clear_since = self._fault_clear_since or now
            if (now - self._fault_clear_since).total_seconds() >= self.cfg.fault_recovery_s:
                self.fault_safe = False
                self.fault_reason = None
                self._fault_clear_since = None
                self.tracker.reset()
                self.tracker.state(BOILER_KEY).failed = False
        else:
            self._fault_clear_since = None

    def _idle_position(self, valve: ValveConfig) -> bool:
        policy = self.cfg.idle_valve_policy
        if policy == "open":
            return True
        if policy == "closed":
            return False
        return deenergized_open(valve)

    def _plan_valves(
        self, now: datetime, *, manual: bool, heating_allowed: bool
    ) -> dict[str, bool]:
        """Desired valve positions (FR-VAL-05, FR-VAL-07, FR-MAN-04, chapter 11.3)."""
        cfg = self.cfg
        plan: dict[str, bool] = {}
        for room in self.rooms.values():
            forced = True
            want: bool | None
            if self.fault_safe:
                want = None
            elif room.frost_active:
                want = True
            elif room.window.effective_open:
                want = False
            elif manual:
                want = room.hvac_mode is not RoomHvacMode.OFF and (
                    cfg.manual_scope == "all_rooms" or room.demand > 0
                )
            elif not heating_allowed:
                want = None
            elif room.hvac_mode is RoomHvacMode.OFF:
                want = False
            else:
                want = room.pwm_want(now)
                forced = False
            decided = room.decide_open(want, now, forced=forced)
            for valve in room.cfg.valves:
                plan[valve.entity_id] = self._idle_position(valve) if decided is None else decided

        self._apply_exercise(now, plan, manual=manual)
        if self.sequencer.phase is BoilerPhase.OVERRUN:
            for entity_id in self.sequencer.overrun_valves:
                if entity_id in plan:
                    plan[entity_id] = True
        if not cfg.has_bypass and self.sequencer.phase is not BoilerPhase.IDLE:
            self._keep_min_open(now, plan)
        return plan

    def _apply_exercise(self, now: datetime, plan: dict[str, bool], *, manual: bool) -> None:
        idle_boiler = self.sequencer.phase is BoilerPhase.IDLE and not manual
        candidates = [
            (
                valve,
                room.valves[valve.entity_id],
                idle_boiler
                and not self.fault_safe
                and room.demand == 0
                and not room.frost_active
                and not room.window.effective_open,
            )
            for room, valve in self.valve_configs
        ]
        self.exercising = self.exercise.step(now, self.cfg, candidates)
        for entity_id in self.exercising:
            plan[entity_id] = not plan[entity_id]

    def _keep_min_open(self, now: datetime, plan: dict[str, bool]) -> None:
        """Never let the number of open valves drop below min_open_valves (chapter 11.3)."""
        needed = self.cfg.min_open_valves - sum(1 for want in plan.values() if want)
        if needed <= 0:
            return

        def rank(item: tuple[RoomController, ValveConfig]) -> tuple[int, int, float]:
            room, valve = item
            physical = room.valves[valve.entity_id].physical(valve, now)
            already_open = physical in (ValvePhysical.OPEN, ValvePhysical.OPENING)
            gap = (
                room.temperature - room.target
                if room.temperature is not None and room.target is not None
                else float("inf")
            )
            return (int(room.window.effective_open), int(not already_open), gap)

        for _room, valve in sorted(self.valve_configs, key=rank):
            if needed <= 0:
                break
            if not plan[valve.entity_id]:
                plan[valve.entity_id] = True
                needed -= 1

    def _system_state(self, mode: SystemMode) -> SystemState:
        if not self.ready:
            return SystemState.STARTUP
        if self.fault_safe:
            return SystemState.FAULT_SAFE
        if mode is SystemMode.MANUAL:
            return SystemState.MANUAL
        if self.summer:
            return SystemState.SUMMER
        if mode is SystemMode.OFF:
            return SystemState.OFF
        if mode is SystemMode.AWAY:
            return SystemState.AWAY
        return SystemState.AUTO

    def _blocked_by(self, now: datetime, blocked: bool, flow_ok: bool) -> list[str]:
        reasons = []
        if self.fault_safe:
            reasons.append("fault_safe")
        if self.heat_request and blocked:
            if self.window_block:
                reasons.append("window_block")
            if self.summer:
                reasons.append("summer")
        if self.sequencer.phase is BoilerPhase.PRE_OPEN:
            if not flow_ok:
                reasons.append("waiting_for_valves")
            elif self.sequencer.duty_holding(now):
                reasons.append("duty_limit")
            elif not self.sequencer.can_start(now, self.cfg):
                reasons.append("anti_cycling")
        return reasons

    def _collect_problems(self, now: datetime) -> None:
        """Active problems for notifications and repair issues (FR-SAFE-04)."""
        problems: dict[str, Problem] = {}
        if self.fault_safe:
            problems["fault_safe"] = Problem(
                "fault_safe", "fault_safe", {"reason": self.fault_reason or ""}, repair=True
            )
        if self.ready:
            for room in self.rooms.values():
                name = {"room": room.cfg.name}
                if room.sensor_failure_reported(now):
                    key = f"sensor_failure_{room.cfg.slug}"
                    problems[key] = Problem(key, "sensor_failure", name, repair=True)
                if room.window.long_block:
                    key = f"window_long_{room.cfg.slug}"
                    problems[key] = Problem(key, "window_long", name)
                if room.not_reached:
                    key = f"not_reached_{room.cfg.slug}"
                    problems[key] = Problem(key, "not_reached", name)
            for room, valve in self.valve_configs:
                if self.tracker.failed(valve.entity_id):
                    key = f"valve_command_{valve.entity_id}"
                    problems[key] = Problem(
                        key, "valve_command", {"room": room.cfg.name, "entity": valve.entity_id}
                    )
        self.problems = problems

    def _output_commands(self, snap: Snapshot, boiler_on: bool) -> list[Command]:
        """Commands needed to reach the plan, with verification (FR-VAL-04, FR-BOI-04)."""
        cfg = self.cfg
        now = snap.now
        commands: list[Command] = []
        for _room, valve in self.valve_configs:
            reading = snap.get(valve.entity_id)
            desired = self.valve_desired[valve.entity_id]
            if self.tracker.evaluate(
                valve.entity_id,
                now,
                desired=desired,
                observed=observed_open(valve, reading),
                available=reading.available,
                verifiable=True,
                verify_timeout_s=cfg.verify_timeout_s,
                retries=cfg.command_retries,
                keep_alive_s=cfg.keep_alive_s,
            ):
                commands.append(self._valve_command(valve, desired))

        if self.fault_safe:
            # FR-SAFE-02: keep repeating "off".
            commands.extend(self._boiler_commands(on=False))
            return commands
        if self.tracker.evaluate(
            BOILER_KEY,
            now,
            desired=boiler_on,
            observed=self.boiler_observed,
            available=self.boiler_available,
            verifiable=cfg.heat_source.verifiable,
            verify_timeout_s=cfg.verify_timeout_s,
            retries=cfg.command_retries,
            keep_alive_s=cfg.keep_alive_s,
        ):
            commands.extend(self._boiler_commands(on=boiler_on))
        return commands

    @staticmethod
    def _valve_command(valve: ValveConfig, want_open: bool) -> Command:
        if valve.is_valve_domain:
            return Command(valve.entity_id, "open" if want_open else "close")
        energized = not want_open if valve.normally_open else want_open
        return Command(valve.entity_id, "turn_on" if energized else "turn_off")

    def _boiler_commands(self, *, on: bool) -> list[Command]:
        hs = self.cfg.heat_source
        if hs.type == c.HEAT_SOURCE_SELECT and hs.select_entity:
            option = hs.select_on if on else hs.select_off
            return [Command(hs.select_entity, "select", option)]
        if hs.type == c.HEAT_SOURCE_ACTIONS:
            target = hs.on_entity if on else hs.off_entity
            return [Command(target, "run")] if target else []
        if hs.entity:
            return [Command(hs.entity, "turn_on" if on else "turn_off")]
        return []

    def _heartbeat(self, now: datetime) -> Command | None:
        """FR-SAFE-03: toggle the heartbeat output for a hardware watchdog."""
        entity = self.cfg.heartbeat_entity
        if not entity:
            return None
        due = (
            self._heartbeat_at is None
            or (now - self._heartbeat_at).total_seconds() >= self.cfg.heartbeat_interval_s
        )
        if not due:
            return None
        self._heartbeat_at = now
        return Command(entity, "toggle")

    # --- Status for entities ----------------------------------------------

    def window_rooms(self) -> int:
        """Return the number of rooms with an open window (any state except closed)."""
        return sum(1 for r in self.rooms.values() if r.window.state is not WindowState.CLOSED)

    def would_command(self) -> dict[str, Any]:
        """Return the outputs the controller wants, shown in shadow mode (FR-SAFE-05)."""
        return {
            "boiler": "on" if self.sequencer.boiler_on and not self.fault_safe else "off",
            "valves": {
                entity: "open" if want else "closed" for entity, want in self.valve_desired.items()
            },
        }

    # --- Persistence ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize everything that must survive a restart (NFR-11)."""
        return {
            "format": STORAGE_FORMAT,
            "modes": self.modes.to_dict(),
            "outdoor": self.outdoor.to_dict(),
            "boiler": self.sequencer.to_dict(),
            "exercise": self.exercise.to_dict(),
            "rooms": {room_id: room.to_dict() for room_id, room in self.rooms.items()},
        }

    def restore(self, data: dict[str, Any] | None, now: datetime) -> None:
        """Restore the state saved by `to_dict`."""
        data = data or {}
        self.modes.restore(data.get("modes", {}))
        self.outdoor.restore(data.get("outdoor", {}))
        self.sequencer.restore(data.get("boiler", {}), now)
        self.exercise.restore(data.get("exercise", {}))
        for room_id, room_data in data.get("rooms", {}).items():
            if room_id in self.rooms:
                self.rooms[room_id].restore(room_data)
