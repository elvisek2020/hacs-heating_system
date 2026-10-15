"""What happens next and when, for the animated scheme (FR-UI-25).

Collects the next events from the state of the controller: when the boiler
starts or stops, when its time rules end, when manual heating ends and what
the rooms do next (preheat, schedule, return, end of airing). The texts are
made by `explain.py`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from .model import BoilerReason, RoomHvacMode, TargetReason

if TYPE_CHECKING:
    from .controller import HydronicController

HORIZON = timedelta(hours=24)
MAX_EVENTS = 8
# Rooms whose target follows the schedule now; their next schedule change matters.
FOLLOWS_SCHEDULE = frozenset(
    {
        TargetReason.SCHEDULE_ECO,
        TargetReason.SCHEDULE_COMFORT,
        TargetReason.PREHEAT,
        TargetReason.COMFORT,
    }
)
BOILER_EVENTS = {
    BoilerReason.PRE_CLOSE: "boiler_start",
    BoilerReason.PRE_OPEN: "boiler_start",
    BoilerReason.MIN_OFF_HOLD: "boiler_may_start",
    BoilerReason.MAX_STARTS_HOLD: "boiler_may_start",
    BoilerReason.DUTY_HOLD: "boiler_may_start",
    BoilerReason.MIN_ON_HOLD: "boiler_off",
    BoilerReason.OVERRUN: "valves_idle",
    BoilerReason.FAULT_RECOVERY: "fault_recovery",
}
FIRING = frozenset(
    {BoilerReason.FIRING_DEMAND, BoilerReason.FIRING_MANUAL, BoilerReason.FIRING_FROST}
)


@dataclass(frozen=True, slots=True)
class Upcoming:
    """One next event; `rooms` are room names, empty for the boiler."""

    at: datetime
    kind: str
    rooms: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)


def upcoming(ctrl: HydronicController, now: datetime) -> list[Upcoming]:
    """Next events within 24 hours, the earliest first."""
    events = _boiler_events(ctrl, now)
    if (ends := ctrl.modes.manual_ends_at) is not None:
        events.append(Upcoming(ends, "manual_end"))
    events += _room_events(ctrl)
    events = [e for e in events if now <= e.at <= now + HORIZON]
    events.sort(key=lambda e: (e.at, e.kind))
    return events[:MAX_EVENTS]


def _boiler_events(ctrl: HydronicController, now: datetime) -> list[Upcoming]:
    status = ctrl.boiler_status
    events: list[Upcoming] = []
    if (kind := BOILER_EVENTS.get(status.reason)) is not None and status.until is not None:
        events.append(Upcoming(status.until, kind, params={"policy": ctrl.cfg.idle_valve_policy}))
    elif status.reason in FIRING:
        min_on = ctrl.sequencer.min_on_until(ctrl.cfg)
        if min_on is not None and min_on > now:
            events.append(Upcoming(min_on, "min_on_end"))
        if status.until is not None:
            events.append(Upcoming(status.until, "duty_stop"))
    return events


def _room_events(ctrl: HydronicController) -> list[Upcoming]:
    grouped: dict[tuple[datetime, str], list[str]] = defaultdict(list)
    extra: dict[tuple[datetime, str], dict[str, Any]] = {}
    for room in ctrl.rooms.values():
        name = room.cfg.name
        if room.preheat_planned is not None:
            key = (room.preheat_planned, "preheat")
            grouped[key].append(name)
            extra[key] = {"target_at": room.preheat_planned_for}
        if (pause := room.vent_pause_until) is not None:
            grouped[(pause, "ventilation_end")].append(name)
        if (aired := room.manual_vent_until) is not None:
            grouped[(aired, "manual_ventilation_end")].append(name)
        if room.hvac_mode is not RoomHvacMode.AUTO:
            continue
        if room.target_reason in (TargetReason.ABSENT, TargetReason.LONG_AWAY):
            if room.target_until is not None:
                grouped[(room.target_until, "return")].append(name)
        elif room.target_reason in FOLLOWS_SCHEDULE and room.schedule_next is not None:
            kind = "schedule_eco" if room.schedule_on else "schedule_comfort"
            grouped[(room.schedule_next, kind)].append(name)
    everyone = len(ctrl.rooms)
    return [
        Upcoming(
            at,
            kind,
            tuple(names),
            {**extra.get((at, kind), {}), "all_rooms": everyone > 1 and len(names) == everyone},
        )
        for (at, kind), names in grouped.items()
    ]
