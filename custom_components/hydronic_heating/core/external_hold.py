"""External hold of the boiler by a calendar or an on/off entity (FR-BOI-10).

Another integration tells when the boiler must not start, e.g. while a battery
inverter takes power from the grid and its transfer relay trips the burner. A
binary sensor or an input boolean holds while it is on, a calendar while an
event runs and `lead` before the next one starts, so a running boiler stops
before the window. After `max` of holding the boiler may run again and the
hold is reported. The calendar is read from its state: the attributes
`start_time` and `end_time` describe the running or the next event.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .model import EntityReading, SystemConfig
from .presence import parse_time

OFF = "off"
UPCOMING = "upcoming"
ACTIVE = "active"
EXPIRED = "expired"


class ExternalHold:
    """State of the external hold: off, upcoming, active or expired."""

    def __init__(self) -> None:
        """Start without a hold."""
        self._reset()

    def _reset(self) -> None:
        self.state = OFF
        self.since: datetime | None = None
        self.starts: datetime | None = None
        self.ends: datetime | None = None
        self.limit_at: datetime | None = None

    @property
    def holding(self) -> bool:
        """Whether the boiler must not run now."""
        return self.state in (UPCOMING, ACTIVE)

    def update(self, now: datetime, reading: EntityReading, cfg: SystemConfig) -> None:
        """Follow the entity; an unavailable entity does not hold the boiler."""
        entity = cfg.external_hold_entity
        active = reading.available and reading.state == "on"
        starts = ends = None
        if entity and entity.startswith("calendar.") and reading.available:
            starts = parse_time(reading.attributes.get("start_time"), cfg.timezone)
            ends = parse_time(reading.attributes.get("end_time"), cfg.timezone)
        upcoming = (
            not active
            and starts is not None
            and now < starts <= now + timedelta(seconds=cfg.external_hold_lead_s)
        )
        if not (active or upcoming):
            self._reset()
            return
        self.since = self.since or now
        self.starts = None if active else starts
        self.ends = ends
        self.limit_at = (
            self.since + timedelta(seconds=cfg.external_hold_max_s)
            if cfg.external_hold_max_s > 0
            else None
        )
        if self.limit_at is not None and now >= self.limit_at:
            self.state = EXPIRED
        else:
            self.state = ACTIVE if active else UPCOMING

    @property
    def until(self) -> datetime | None:
        """When the hold lets the boiler start at the latest known time."""
        known = [t for t in (self.ends, self.limit_at) if t is not None]
        return min(known) if known else None
