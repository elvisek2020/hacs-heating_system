"""Demand arbitration and boiler sequencing (chapters 11.2 and 11.3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .model import BoilerPhase, SystemConfig

NO_FLOW_MARGIN_S = 60
DUTY_WINDOW_S = 24 * 3600


@dataclass(frozen=True, slots=True)
class RoomDemand:
    """What the arbiter needs to know about a room."""

    demand: float
    weight: float
    area_m2: float
    frost: bool
    # Whether the room calls, with its hysteresis; None = by the threshold alone.
    calling: bool | None = None


@dataclass(frozen=True, slots=True)
class Arbitration:
    """Result of the arbiter (FR-ARB-01, FR-ARB-02)."""

    request: bool
    weighted: float
    calling: int


def arbitrate(rooms: Sequence[RoomDemand], cfg: SystemConfig, prev_request: bool) -> Arbitration:
    """Decide whether the rooms need the boiler."""
    weights = [r.weight * (r.area_m2 if cfg.area_weighting else 1.0) for r in rooms]
    total = sum(weights)
    weighted = (
        sum(r.demand * w for r, w in zip(rooms, weights, strict=True)) / total if total else 0.0
    )
    calling = sum(
        1
        for r in rooms
        if (r.demand >= cfg.room_call_threshold if r.calling is None else r.calling)
    )
    if any(r.frost for r in rooms):
        return Arbitration(True, round(weighted, 1), calling)
    threshold = cfg.demand_threshold - (cfg.demand_hysteresis if prev_request else 0)
    a = weighted >= threshold and weighted > 0
    b = calling >= cfg.min_rooms_calling
    request = (a or b) if cfg.combine == "any" else (a and b)
    return Arbitration(request, round(weighted, 1), calling)


class BoilerSequencer:
    """Valve -> boiler -> overrun sequence with anti-cycling (FR-BOI-02, 03, 06, 08)."""

    def __init__(self) -> None:
        """Start idle; history is restored from storage."""
        self.phase = BoilerPhase.IDLE
        self.boiler_on = False
        self.on_since: datetime | None = None
        self.off_since: datetime | None = None
        self.starts: list[datetime] = []
        self.on_intervals: list[list[datetime | None]] = []
        self.pre_open_since: datetime | None = None
        self.overrun_since: datetime | None = None
        self.overrun_valves: set[str] = set()
        self.no_flow = False
        # FR-EQ-05: after a duty-limited stop the next start waits for the cycle end.
        self.duty_hold_until: datetime | None = None
        self.duty_stopped = False
        # Why the last run ended: no_demand, no_flow, duty_limit or fault.
        self.off_cause: str | None = None

    # --- Anti-cycling -----------------------------------------------------

    def starts_last_hour(self, now: datetime) -> int:
        """Return the number of starts within the last hour."""
        return sum(1 for s in self.starts if (now - s).total_seconds() < 3600)

    def min_on_until(self, cfg: SystemConfig) -> datetime | None:
        """End of the minimum run time of the current run."""
        if not self.boiler_on or self.on_since is None:
            return None
        return self.on_since + timedelta(seconds=cfg.boiler_min_on_s)

    def min_off_until(self, cfg: SystemConfig) -> datetime | None:
        """End of the minimum pause after the last stop."""
        if self.boiler_on or self.off_since is None:
            return None
        return self.off_since + timedelta(seconds=cfg.boiler_min_off_s)

    def max_starts_until(self, now: datetime, cfg: SystemConfig) -> datetime | None:
        """When a start is free again, if the starts per hour are used up."""
        recent = sorted(s for s in self.starts if (now - s).total_seconds() < 3600)
        if len(recent) < cfg.boiler_max_starts:
            return None
        return recent[len(recent) - cfg.boiler_max_starts] + timedelta(hours=1)

    def next_allowed_start(self, now: datetime, cfg: SystemConfig) -> datetime:
        """Earliest time the boiler may start again."""
        candidates = [now]
        if self.off_since is not None:
            candidates.append(self.off_since + timedelta(seconds=cfg.boiler_min_off_s))
        if (starts_free := self.max_starts_until(now, cfg)) is not None:
            candidates.append(starts_free)
        if self.duty_hold_until is not None:
            candidates.append(self.duty_hold_until)
        return max(candidates)

    def duty_holding(self, now: datetime) -> bool:
        """Return True while a duty-limited cycle keeps the boiler off."""
        return self.duty_hold_until is not None and now < self.duty_hold_until

    def can_start(self, now: datetime, cfg: SystemConfig) -> bool:
        """Minimum pause and starts per hour are respected."""
        return self.next_allowed_start(now, cfg) <= now

    def min_on_done(self, now: datetime, cfg: SystemConfig) -> bool:
        """Return True when the minimum run time has passed."""
        return self.on_since is None or (now - self.on_since).total_seconds() >= cfg.boiler_min_on_s

    # --- Step -------------------------------------------------------------

    def _turn_on(self, now: datetime) -> None:
        self.boiler_on = True
        self.on_since = now
        self.starts.append(now)
        self.on_intervals.append([now, None])
        self.phase = BoilerPhase.FIRING

    def _turn_off(self, now: datetime, open_valves: set[str], cause: str) -> None:
        self.off_cause = cause
        self.boiler_on = False
        self.off_since = now
        if self.on_intervals and self.on_intervals[-1][1] is None:
            self.on_intervals[-1][1] = now
        self.phase = BoilerPhase.OVERRUN
        self.overrun_since = now
        self.overrun_valves = set(open_valves)

    def force_off(self, now: datetime) -> None:
        """Switch off immediately (fault, safety), without overrun bookkeeping changes."""
        if self.boiler_on:
            self._turn_off(now, set(), "fault")
        self.phase = BoilerPhase.IDLE
        self.overrun_valves = set()

    def step(
        self,
        now: datetime,
        cfg: SystemConfig,
        *,
        request: bool,
        blocked: bool,
        stop_immediate: bool,
        flow_ok: bool,
        open_valves: set[str],
        max_travel_s: float,
        duty_run_s: float | None = None,
        valves_ready: bool = True,
    ) -> None:
        """Advance the sequence by one step.

        `duty_run_s` is the allowed run time per cycle (FR-EQ-05), None = no limit.
        `valves_ready` is False while valves of rooms without demand still close,
        so the first hot water does not go where nobody wants heat.
        """
        wants_heat = request and not blocked
        if self.duty_hold_until is not None and now >= self.duty_hold_until:
            self.duty_hold_until = None
            self.duty_stopped = False
        if self.phase is BoilerPhase.OVERRUN and wants_heat:
            self.phase = BoilerPhase.PRE_OPEN
            self.pre_open_since = now
            self.overrun_valves = set()
        if self.phase is BoilerPhase.IDLE and wants_heat:
            self.phase = BoilerPhase.PRE_OPEN
            self.pre_open_since = now
        if self.phase is BoilerPhase.PRE_OPEN:
            if not wants_heat:
                self.phase = BoilerPhase.IDLE
                self.no_flow = False
            elif flow_ok:
                self.no_flow = False
                if valves_ready and self.can_start(now, cfg):
                    self._turn_on(now)
            elif self._pre_open_s(now) > max_travel_s + NO_FLOW_MARGIN_S:
                # Waiting for anti-cycling is fine; only missing flow is a fault.
                self.no_flow = True
        elif self.phase is BoilerPhase.FIRING:
            if not flow_ok:
                # Safety overrides the minimum run time.
                self._turn_off(now, open_valves, "no_flow")
            elif not wants_heat and (stop_immediate or self.min_on_done(now, cfg)):
                self._turn_off(now, open_valves, "no_demand")
            elif (
                duty_run_s is not None
                and self.on_since is not None
                and (now - self.on_since).total_seconds() >= max(duty_run_s, cfg.boiler_min_on_s)
            ):
                # Duty limit reached: stop until the cycle ends (never before min_on).
                cycle_end = self.on_since + timedelta(seconds=cfg.boiler_cycle_period_s)
                self._turn_off(now, open_valves, "duty_limit")
                self.duty_hold_until = cycle_end
                self.duty_stopped = True
        if (
            self.phase is BoilerPhase.OVERRUN
            and (now - self.overrun_since).total_seconds() >= cfg.boiler_overrun_s  # type: ignore[operator]
        ):
            self.phase = BoilerPhase.IDLE
            self.overrun_valves = set()
        self._prune(now)

    def _pre_open_s(self, now: datetime) -> float:
        return (now - self.pre_open_since).total_seconds() if self.pre_open_since else 0.0

    def _prune(self, now: datetime) -> None:
        self.starts = [s for s in self.starts if (now - s).total_seconds() < 2 * DUTY_WINDOW_S]
        self.on_intervals = [
            i
            for i in self.on_intervals
            if i[1] is None or (now - i[1]).total_seconds() < DUTY_WINDOW_S
        ]

    # --- Statistics -------------------------------------------------------

    def duty_24h(self, now: datetime) -> float:
        """Share of the last 24 hours the boiler was on, in percent."""
        window_start = now - timedelta(seconds=DUTY_WINDOW_S)
        on_s = 0.0
        for start, end in self.on_intervals:
            begin = max(start, window_start)  # type: ignore[type-var]
            finish = end or now
            if finish > begin:
                on_s += (finish - begin).total_seconds()
        return round(on_s / DUTY_WINDOW_S * 100, 1)

    def starts_today(self, now: datetime, tz: ZoneInfo) -> int:
        """Return the number of starts since local midnight."""
        today = now.astimezone(tz).date()
        return sum(1 for s in self.starts if s.astimezone(tz).date() == today)

    # --- Persistence (FR-BOI-08) --------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize anti-cycling history."""

        def iso(value: datetime | None) -> str | None:
            return value.isoformat() if value else None

        return {
            "boiler_on": self.boiler_on,
            "on_since": iso(self.on_since),
            "off_since": iso(self.off_since),
            "starts": [s.isoformat() for s in self.starts],
            "on_intervals": [[iso(a), iso(b)] for a, b in self.on_intervals],
            "duty_hold_until": iso(self.duty_hold_until),
        }

    def restore(self, data: dict[str, Any], now: datetime) -> None:
        """Restore history; without it assume the boiler just stopped (FR-BOI-08)."""

        def parse(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        if not data:
            self.off_since = now
            return
        self.on_since = parse(data.get("on_since"))
        self.off_since = parse(data.get("off_since"))
        self.starts = [datetime.fromisoformat(s) for s in data.get("starts", [])]
        self.on_intervals = [[parse(a), parse(b)] for a, b in data.get("on_intervals", [])]
        self.duty_hold_until = parse(data.get("duty_hold_until"))
        self.duty_stopped = self.duty_hold_until is not None
        if data.get("boiler_on"):
            # Continue a run that was active before the restart.
            self.boiler_on = True
            self.phase = BoilerPhase.FIRING
        elif self.off_since is None:
            self.off_since = now
