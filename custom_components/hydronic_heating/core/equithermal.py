"""Outdoor temperature, damping and heating limit (FR-EQ-01 to FR-EQ-03).

The heating curve and duty limit (FR-EQ-04 and later) belong to phase F3.
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any

from .model import Snapshot, SystemConfig

OUTDOOR_MIN = -50.0
OUTDOOR_MAX = 60.0


class OutdoorEngine:
    """Outdoor source selection, exponential damping and summer/winter switching."""

    def __init__(self) -> None:
        """Start without history."""
        self.current: float | None = None
        self.source: str | None = None
        self.damped: float | None = None
        self.updated_at: datetime | None = None
        self.summer = False
        self.above_since: datetime | None = None

    def read(self, snap: Snapshot, cfg: SystemConfig) -> None:
        """Pick the first valid sensor, then the weather entity (FR-EQ-01)."""
        self.current, self.source = None, None
        for entity_id in cfg.outdoor_sensors:
            reading = snap.get(entity_id)
            value = reading.value
            if reading.available and value is not None and OUTDOOR_MIN <= value <= OUTDOOR_MAX:
                self.current, self.source = value, entity_id
                return
        weather = snap.get(cfg.weather_entity)
        temperature = weather.attributes.get("temperature") if weather.available else None
        if isinstance(temperature, int | float):
            self.current, self.source = float(temperature), cfg.weather_entity

    def update(self, snap: Snapshot, cfg: SystemConfig) -> None:
        """Read the source, update the EMA and the heating limit."""
        self.read(snap, cfg)
        now = snap.now
        if self.current is not None:
            if self.damped is None or self.updated_at is None:
                self.damped = self.current
            else:
                dt = max(0.0, (now - self.updated_at).total_seconds())
                tau = cfg.outdoor_damping_s
                alpha = 1.0 if tau <= 0 else 1.0 - math.exp(-dt / tau)
                self.damped += alpha * (self.current - self.damped)
            self.updated_at = now
        if self.damped is None:
            return
        # FR-EQ-03: summer after a delay above the limit, winter immediately below it.
        if self.damped > cfg.heating_limit:
            self.above_since = self.above_since or now
            if (now - self.above_since).total_seconds() >= cfg.summer_switch_delay_s:
                self.summer = True
        else:
            self.above_since = None
        if self.damped < cfg.heating_limit - cfg.heating_limit_hysteresis:
            self.summer = False

    @property
    def damped_rounded(self) -> float | None:
        """Damped temperature for display."""
        return None if self.damped is None else round(self.damped, 2)

    def to_dict(self) -> dict[str, Any]:
        """Serialize (FR-EQ-02: the damped value survives a restart)."""
        return {
            "damped": self.damped,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "summer": self.summer,
            "above_since": self.above_since.isoformat() if self.above_since else None,
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore from storage."""
        self.damped = data.get("damped")
        if updated := data.get("updated_at"):
            self.updated_at = datetime.fromisoformat(updated)
        self.summer = bool(data.get("summer", False))
        if above := data.get("above_since"):
            self.above_since = datetime.fromisoformat(above)
