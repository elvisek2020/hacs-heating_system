"""Valve state model and PWM (FR-VAL-02, FR-VAL-03, FR-VAL-05)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .model import EntityReading, ValveConfig, ValvePhysical


def observed_open(cfg: ValveConfig, reading: EntityReading) -> bool | None:
    """Translate an entity state to "valve is commanded open" (NO/NC aware)."""
    if not reading.available:
        return None
    if cfg.is_valve_domain:
        return reading.state in ("open", "opening")
    energized = reading.state == "on"
    return not energized if cfg.normally_open else energized


def energized_for(cfg: ValveConfig, want_open: bool) -> bool:
    """Return whether the head must be energized to reach the wanted position."""
    return not want_open if cfg.normally_open else want_open


def deenergized_open(cfg: ValveConfig) -> bool:
    """Position of the valve without power (idle policy `deenergize`)."""
    return True if cfg.is_valve_domain else cfg.normally_open


@dataclass(slots=True)
class ValveState:
    """Tracks when a valve was last moved to model its physical position."""

    is_open: bool | None = None
    changed_at: datetime | None = None

    def observe(self, is_open: bool | None, now: datetime) -> None:
        """Record the commanded position seen on the entity (or simulated)."""
        if is_open is None:
            return
        if is_open != self.is_open:
            self.is_open = is_open
            self.changed_at = now

    def physical(self, cfg: ValveConfig, now: datetime) -> ValvePhysical:
        """Return the modelled physical position."""
        if self.is_open is None or self.changed_at is None:
            return ValvePhysical.UNKNOWN
        elapsed = (now - self.changed_at).total_seconds()
        if self.is_open:
            return ValvePhysical.OPEN if elapsed >= cfg.open_time_s else ValvePhysical.OPENING
        return ValvePhysical.CLOSED if elapsed >= cfg.close_time_s else ValvePhysical.CLOSING

    def transition_ends_at(self, cfg: ValveConfig) -> datetime | None:
        """Return when the current movement finishes."""
        if self.is_open is None or self.changed_at is None:
            return None
        travel = cfg.open_time_s if self.is_open else cfg.close_time_s
        return self.changed_at + timedelta(seconds=travel)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "is_open": self.is_open,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValveState:
        """Restore from storage."""
        changed = data.get("changed_at")
        return cls(
            is_open=data.get("is_open"),
            changed_at=datetime.fromisoformat(changed) if changed else None,
        )


def pwm_on_time(demand: float, period_s: float, min_state_s: float) -> float:
    """Return the open time within one period, rounded to the minimum state time."""
    on_time = max(0.0, min(100.0, demand)) / 100 * period_s
    if on_time < min_state_s:
        return 0.0
    if period_s - on_time < min_state_s:
        return period_s
    return on_time


def pwm_open(now: datetime, demand: float, period_s: float, min_state_s: float) -> bool:
    """Return whether the valve is in the open part of the PWM period.

    Periods of all rooms start at the same moment (aligned to the epoch), so open
    valves overlap as much as possible (FR-VAL-05 SHOULD).
    """
    on_time = pwm_on_time(demand, period_s, min_state_s)
    if on_time <= 0:
        return False
    if on_time >= period_s:
        return True
    return now.timestamp() % period_s < on_time
