"""Heating season from the 4-hour mean outdoor temperature (FR-EQ-03).

The season starts as soon as the 4-hour mean drops below the limit. It ends
after three whole days in a row in which the 4-hour mean never dropped below
the limit. A daily average would hide cold evenings after sunny days.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

WINDOW = timedelta(hours=4)
SAMPLE_EVERY_S = 60
END_DAYS = 3
KEEP_DAYS = 10
SEASON_MODES = ("auto", "on", "off")


class HeatingSeason:
    """Whether heating is allowed by the outdoor temperature (or set by hand)."""

    def __init__(self) -> None:
        """Start in the heating season; the outdoor history decides from there."""
        self.mode = "auto"
        self.active = True
        self.since: datetime | None = None
        self.samples: list[tuple[datetime, float]] = []
        # Local date -> the 4-hour mean was below the limit at least once that day.
        self.below_days: dict[date, bool] = {}
        self.mean_4h: float | None = None
        self.days_above = 0
        self.limit: float | None = None

    def set_mode(self, mode: str, now: datetime) -> None:
        """Automatic, heating season or off season, chosen by the user."""
        self.mode = mode if mode in SEASON_MODES else "auto"
        self._apply(now)

    def update(self, now: datetime, outdoor: float | None, limit: float, tz: ZoneInfo) -> None:
        """Add the outdoor temperature and re-evaluate the season."""
        if outdoor is not None and (
            not self.samples or (now - self.samples[-1][0]).total_seconds() >= SAMPLE_EVERY_S
        ):
            self.samples.append((now, outdoor))
        cutoff = now - WINDOW
        self.samples = [s for s in self.samples if s[0] >= cutoff]
        values = [value for _, value in self.samples]
        self.mean_4h = round(sum(values) / len(values), 2) if values else None
        today = now.astimezone(tz).date()
        if self.mean_4h is not None:
            self.below_days[today] = self.below_days.get(today, False) or self.mean_4h < limit
        self.below_days = {
            day: below for day, below in self.below_days.items() if (today - day).days <= KEEP_DAYS
        }
        self.days_above = self._whole_days_above(today)
        self.limit = limit
        self._apply(now)

    def _whole_days_above(self, today: date) -> int:
        """Finished days in a row (before today) without a 4-hour mean below the limit."""
        count = 0
        day = today - timedelta(days=1)
        while self.below_days.get(day) is False:
            count += 1
            day -= timedelta(days=1)
        return count

    def _apply(self, now: datetime) -> None:
        before = self.active
        if self.mode == "on":
            self.active = True
        elif self.mode == "off":
            self.active = False
        elif self.mean_4h is not None and self.limit is not None and self.mean_4h < self.limit:
            self.active = True
        elif self.days_above >= END_DAYS:
            self.active = False
        if self.active != before or self.since is None:
            self.since = now

    def to_dict(self) -> dict[str, Any]:
        """Serialize the mode, the state and the history the season needs."""
        return {
            "mode": self.mode,
            "active": self.active,
            "since": self.since.isoformat() if self.since else None,
            "samples": [[t.isoformat(), value] for t, value in self.samples],
            "below_days": {day.isoformat(): below for day, below in self.below_days.items()},
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore from storage."""
        self.mode = data.get("mode", "auto")
        self.active = bool(data.get("active", True))
        if since := data.get("since"):
            self.since = datetime.fromisoformat(since)
        self.samples = [(datetime.fromisoformat(t), float(v)) for t, v in data.get("samples", [])]
        self.below_days = {
            date.fromisoformat(day): bool(below)
            for day, below in data.get("below_days", {}).items()
        }
