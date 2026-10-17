"""Airing detected by a fast drop of the room temperature (FR-WIN-06).

Without window contacts a room still notices airing: its temperature drops by
at least `drop_k` within `window_s`. The room then behaves as with an open
window for at least `hold_s`, afterwards until the temperature rises again, at
most for `max_s`. A change of the temperature sources (a sensor fails, another
one takes over) restarts the history, so a jump between sensors is no airing.
After a jump of a sensor (FR-ROOM-08) detection waits one window: the offset of
a reconnected Matter sensor settles back like a fast drop.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# The temperature rises again: the window is closed, the room recovers.
RISE_K = 0.2
# The drop must last this long, a single wrong reading is no airing.
CONFIRM_S = 30


class VentDetector:
    """Airing of one room, from its temperature."""

    def __init__(self) -> None:
        """Start without history."""
        self.samples: list[tuple[datetime, float]] = []
        self.sources: tuple[str, ...] = ()
        self.since: datetime | None = None
        self.lowest: float | None = None
        self.drop: float | None = None
        self._pending_since: datetime | None = None

    @property
    def active(self) -> bool:
        """The room is being aired."""
        return self.since is not None

    def update(
        self,
        now: datetime,
        temperature: float | None,
        sources: tuple[str, ...],
        *,
        enabled: bool,
        drop_k: float,
        window_s: float,
        hold_s: float,
        max_s: float,
        settling: bool = False,
    ) -> str | None:
        """Follow the temperature; return `started` or `ended` on a change."""
        if not enabled:
            self._end()
            return None
        if sources != self.sources:
            # Another sensor took over: the jump between them is no drop.
            self.sources = sources
            self.samples = []
            self._pending_since = None
        if self.active:
            return self._follow(now, temperature, hold_s, max_s)
        if settling:
            # A sensor just jumped; its way back is no airing.
            self.samples = []
            self._pending_since = None
            return None
        if temperature is None:
            return None
        cutoff = now - timedelta(seconds=window_s)
        self.samples = [s for s in self.samples if s[0] >= cutoff]
        self.samples.append((now, temperature))
        self.drop = round(max(value for _, value in self.samples) - temperature, 2)
        if self.drop < drop_k:
            self._pending_since = None
            return None
        self._pending_since = self._pending_since or now
        if (now - self._pending_since).total_seconds() < CONFIRM_S:
            return None
        self.since, self.lowest = now, temperature
        self._pending_since = None
        return "started"

    def _follow(
        self, now: datetime, temperature: float | None, hold_s: float, max_s: float
    ) -> str | None:
        assert self.since is not None
        if temperature is not None:
            self.lowest = temperature if self.lowest is None else min(self.lowest, temperature)
        elapsed = (now - self.since).total_seconds()
        rising = (
            temperature is not None
            and self.lowest is not None
            and temperature >= self.lowest + RISE_K
        )
        if elapsed >= max_s or (elapsed >= hold_s and rising):
            self._end()
            return "ended"
        return None

    def _end(self) -> None:
        self.since = self.lowest = self.drop = None
        self.samples = []
        self._pending_since = None
