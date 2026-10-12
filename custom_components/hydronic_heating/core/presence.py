"""Presence inputs and the learned heat-up rate for preheating (FR-SCH-02, FR-SCH-03).

The heating reads presence only through ordinary entities (a presence module,
a group of persons, `zone.home`), so nothing here knows where they come from.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from .model import EntityReading

PRESENT_STATES = {"on", "home"}
ABSENT_STATES = {"off", "not_home", "away"}
MIN_CONFIDENCE = 0.5

DEFAULT_RATE_K_H = 0.5
BAND_K = 5
SAMPLES_PER_BAND = 8
MIN_SAMPLES = 3
START_DEFICIT_K = 1.0
DONE_MARGIN_K = 0.2
MIN_EPISODE_S = 30 * 60
MIN_RISE_K = 0.5
MAX_EPISODE_S = 12 * 3600
# Water needs to reach the radiators after the valves open.
BOILER_START_S = 10 * 60
# A new expected time this close to the old one keeps a running preheat.
PREHEAT_TOLERANCE = timedelta(minutes=5)


def read_presence(reading: EntityReading) -> bool | None:
    """Return True/False for present/absent, None when unknown.

    Accepts on/off, home/not_home and numeric counts (`zone.home` > 0).
    """
    if not reading.available:
        return None
    if reading.state in PRESENT_STATES:
        return True
    if reading.state in ABSENT_STATES:
        return False
    if reading.value is not None:
        return reading.value > 0
    return None


def parse_time(value: Any, tz: ZoneInfo) -> datetime | None:
    """Parse a datetime or an ISO string; a time without zone is local."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=tz)


def read_expected_return(reading: EntityReading, now: datetime, tz: ZoneInfo) -> datetime | None:
    """Read the expected return from a timestamp entity; ignore past or unsure values."""
    if not reading.available:
        return None
    when = parse_time(reading.state, tz)
    if when is None or when <= now:
        return None
    confidence = reading.attributes.get("confidence")
    if isinstance(confidence, int | float) and confidence < MIN_CONFIDENCE:
        return None
    return when


def read_next_event(reading: EntityReading, tz: ZoneInfo) -> datetime | None:
    """Next change of a `schedule` helper (attribute `next_event`)."""
    if not reading.available:
        return None
    return parse_time(reading.attributes.get("next_event"), tz)


class HeatRate:
    """Learned heat-up rate of a room in K/h, per outdoor temperature band.

    A heat-up is measured from a deficit of at least 1 K until the target is
    reached. Only heat-ups longer than 30 min with a rise of at least 0.5 K
    count; the median of the last 8 in the band is used.
    """

    def __init__(self) -> None:
        """Start without samples."""
        self.samples: dict[int, list[float]] = {}
        self._episode: dict[str, Any] | None = None

    @staticmethod
    def band(outdoor: float | None) -> int:
        """Lower edge of the 5 K outdoor band (0 without an outdoor temperature)."""
        return 0 if outdoor is None else int(outdoor // BAND_K * BAND_K)

    def rate(self, outdoor: float | None) -> float:
        """Heat-up rate in K/h for this outdoor temperature."""
        band = self.samples.get(self.band(outdoor), [])
        if len(band) >= MIN_SAMPLES:
            return round(median(band), 2)
        everything = [rate for rates in self.samples.values() for rate in rates]
        if len(everything) >= MIN_SAMPLES:
            return round(median(everything), 2)
        return DEFAULT_RATE_K_H

    @property
    def count(self) -> int:
        """Number of stored heat-ups."""
        return sum(len(rates) for rates in self.samples.values())

    def update(
        self,
        now: datetime,
        *,
        temperature: float | None,
        target: float | None,
        heating: bool,
        outdoor: float | None,
    ) -> None:
        """Follow one heat-up; `heating` is False when the room cannot heat normally."""
        episode = self._episode
        if episode is not None:
            elapsed = (now - episode["start"]).total_seconds()
            if temperature is not None and temperature >= episode["target"] - DONE_MARGIN_K:
                rise = temperature - episode["temp"]
                if elapsed >= MIN_EPISODE_S and rise >= MIN_RISE_K:
                    self._add(episode["outdoor"], rise / (elapsed / 3600))
                self._episode = None
            elif (
                not heating
                or temperature is None
                or target != episode["target"]
                or elapsed > MAX_EPISODE_S
            ):
                self._episode = None
        if (
            self._episode is None
            and heating
            and temperature is not None
            and target is not None
            and target - temperature >= START_DEFICIT_K
        ):
            self._episode = {
                "start": now,
                "temp": temperature,
                "target": target,
                "outdoor": outdoor,
            }

    def _add(self, outdoor: float | None, rate: float) -> None:
        rates = self.samples.setdefault(self.band(outdoor), [])
        rates.append(round(rate, 3))
        del rates[:-SAMPLES_PER_BAND]

    def to_dict(self) -> dict[str, list[float]]:
        """Serialize the samples."""
        return {str(band): rates for band, rates in self.samples.items()}

    def restore(self, data: dict[str, list[float]] | None) -> None:
        """Restore the samples."""
        self.samples = {int(band): list(rates) for band, rates in (data or {}).items()}
