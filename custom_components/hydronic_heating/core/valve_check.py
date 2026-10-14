"""Check the valves by the temperature of the pipe at each valve (FR-SAFE-09).

Thermoelectric heads report no position. A temperature sensor on the pipe at
the valve tells whether hot water flows through it. The check runs only while
the boiler really heats with hot water, and only on a valve that is fully open
or fully closed by its modelled position:

- an open valve must warm its pipe by `rise` K above the lowest value within
  `check_s`, or above the hot-water limit; otherwise it does not open,
- a closed valve must keep its pipe cold: a rise above `closed_rise` K within
  `check_s` means it does not close. A pipe that is already hot when the check
  starts (the valve has just closed) is not judged.

Each check window gives one result. A failure stays until a later window of
the same valve passes.
"""

from __future__ import annotations

from datetime import datetime

OK = "ok"
NOT_OPENING = "not_opening"
NOT_CLOSING = "not_closing"
UNKNOWN = "unknown"
FAILURES = (NOT_OPENING, NOT_CLOSING)


class ValveCheck:
    """Pipe temperature check of one valve."""

    def __init__(self) -> None:
        """Start without a result."""
        self.result = UNKNOWN
        self.temperature: float | None = None
        self.rise: float | None = None
        self._expected: bool | None = None
        self._started: datetime | None = None
        self._baseline: float | None = None
        self._done = False

    @property
    def failed(self) -> bool:
        """The last finished check failed."""
        return self.result in FAILURES

    def disable(self) -> None:
        """No sensor or the check is off: forget everything."""
        self.result = UNKNOWN
        self.temperature = None
        self._stop()

    def _stop(self) -> None:
        self._expected = self._started = self._baseline = self.rise = None
        self._done = False

    def update(
        self,
        now: datetime,
        *,
        expected_open: bool | None,
        temperature: float | None,
        ready: bool,
        check_s: float,
        rise: float,
        closed_rise: float,
        hot: float,
    ) -> tuple[str, str] | None:
        """Follow one step; return (previous, new) result when it changed.

        `expected_open` is True for a fully open valve, False for a fully closed
        one and None while it moves.
        """
        self.temperature = temperature
        if not ready or expected_open is None or temperature is None:
            self._stop()
            return None
        if expected_open != self._expected or self._started is None:
            self._stop()
            self._expected, self._started, self._baseline = expected_open, now, temperature
        if self._done:
            return None
        assert self._baseline is not None
        self._baseline = min(self._baseline, temperature)
        self.rise = round(temperature - self._baseline, 1)
        elapsed = (now - self._started).total_seconds()
        if expected_open:
            if self.rise >= rise or temperature >= hot:
                return self._finish(OK)
            if elapsed >= check_s:
                return self._finish(NOT_OPENING)
            return None
        if self._baseline >= hot:
            self._done = True  # the valve has just closed, its pipe is still hot
            return None
        if self.rise > closed_rise:
            return self._finish(NOT_CLOSING)
        if elapsed >= check_s:
            return self._finish(OK)
        return None

    def _finish(self, result: str) -> tuple[str, str] | None:
        self._done = True
        previous, self.result = self.result, result
        return (previous, result) if previous != result else None
