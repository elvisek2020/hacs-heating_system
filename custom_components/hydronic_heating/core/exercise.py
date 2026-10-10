"""Valve exercise (FR-VAL-06).

A valve that has not moved for `exercise_interval_days` is moved to the opposite
position for `exercise_duration`, at or after `exercise_time`, at most
`exercise_parallel` valves at once.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from .model import SystemConfig, ValveConfig
from .valve import ValveState


class ExerciseScheduler:
    """Chooses which valves are being exercised."""

    def __init__(self) -> None:
        """Start with no running exercise."""
        self.active: dict[str, datetime] = {}
        self.last_run: dict[str, datetime] = {}

    def step(
        self,
        now: datetime,
        cfg: SystemConfig,
        valves: Iterable[tuple[ValveConfig, ValveState, bool]],
    ) -> set[str]:
        """Return the valves to invert now. Each item is (config, state, eligible)."""
        for entity_id, ends_at in list(self.active.items()):
            if now >= ends_at:
                del self.active[entity_id]
        if cfg.exercise_interval_days <= 0:
            self.active.clear()
            return set()
        local = now.astimezone(cfg.timezone)
        in_window = local.time() >= cfg.exercise_time
        interval = timedelta(days=cfg.exercise_interval_days)
        for valve_cfg, state, eligible in valves:
            entity_id = valve_cfg.entity_id
            if entity_id in self.active:
                if not eligible:
                    del self.active[entity_id]
                continue
            if not eligible or not in_window or len(self.active) >= cfg.exercise_parallel:
                continue
            if state.changed_at is None or now - state.changed_at < interval:
                continue
            last = self.last_run.get(entity_id)
            if last is not None and last.astimezone(cfg.timezone).date() >= local.date():
                continue
            self.active[entity_id] = now + timedelta(seconds=cfg.exercise_duration_s)
            self.last_run[entity_id] = now
        return set(self.active)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the last exercise times."""
        return {"last_run": {k: v.isoformat() for k, v in self.last_run.items()}}

    def restore(self, data: dict[str, Any]) -> None:
        """Restore the last exercise times."""
        self.last_run = {k: datetime.fromisoformat(v) for k, v in data.get("last_run", {}).items()}
