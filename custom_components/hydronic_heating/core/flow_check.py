"""Check that a running boiler really heats the water (FR-SAFE-08).

While the boiler runs (with a feedback entity: while the burner runs), the
measured flow temperature must rise by `rise` °C above its lowest value of the
run within `check_s` seconds. Otherwise the problem stays until a later run
shows the rise again: a failed boiler, a closed circuit or air in the system.
"""

from __future__ import annotations

from datetime import datetime

FLOW_MIN = -20.0
FLOW_MAX = 120.0


class FlowCheck:
    """Rise of the measured flow temperature during one boiler run."""

    def __init__(self) -> None:
        """Start without a run and without a problem."""
        self.failed = False
        self.started: datetime | None = None
        self.baseline: float | None = None
        self.rise: float | None = None
        self.verified = False

    @property
    def state(self) -> str:
        """Off, idle, waiting (for the rise), ok or failed."""
        if self.failed:
            return "failed"
        if self.started is None:
            return "idle"
        return "ok" if self.verified else "waiting"

    def disable(self) -> None:
        """No sensor or no time limit: forget the run and the problem."""
        self.failed = False
        self._end_run()

    def _end_run(self) -> None:
        self.started = None
        self.baseline = None
        self.rise = None
        self.verified = False

    def update(
        self,
        now: datetime,
        *,
        running: bool,
        temperature: float | None,
        check_s: float,
        rise: float,
    ) -> None:
        """Follow the run; a step without a valid temperature changes nothing."""
        if not running:
            self._end_run()
            return
        if temperature is None or not FLOW_MIN <= temperature <= FLOW_MAX:
            return
        if self.started is None:
            self.started = now
            self.baseline = temperature
            self.verified = False
        assert self.baseline is not None
        self.baseline = min(self.baseline, temperature)
        self.rise = round(temperature - self.baseline, 1)
        if self.rise >= rise:
            self.verified = True
            self.failed = False
        elif not self.verified and (now - self.started).total_seconds() >= check_s:
            self.failed = True
