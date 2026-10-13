"""Equithermal engine (FR-EQ-01 to FR-EQ-06).

Outdoor source, exponential damping, optional forecast, heating limit,
the heating curve (virtual flow temperature) and the boiler duty limit.
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any

from .model import Snapshot, SystemConfig

OUTDOOR_MIN = -50.0
OUTDOOR_MAX = 60.0


def flow_setpoint(outdoor: float, cfg: SystemConfig) -> float:
    """Heating curve (FR-EQ-04): flow temperature for a damped outdoor temperature.

    T_flow = T_ref + (T_design - T_ref) * ratio^(1/n) + offset, where
    ratio = (T_ref - T_out) / (T_ref - T_out_design), limited to >= 0.
    """
    span = cfg.reference_room_temp - cfg.design_outdoor_temp
    ratio = max(0.0, (cfg.reference_room_temp - outdoor) / span) if span > 0 else 0.0
    exponent = 1.0 / cfg.radiator_exponent if cfg.radiator_exponent > 0 else 1.0
    value = (
        cfg.reference_room_temp
        + (cfg.design_flow_temp - cfg.reference_room_temp) * ratio**exponent
        + cfg.curve_offset
    )
    return round(min(cfg.flow_temp_max, max(cfg.flow_temp_min, value)), 1)


def duty_limit(flow: float, cfg: SystemConfig) -> float:
    """Maximum share of a cycle the boiler may run (FR-EQ-05)."""
    span = cfg.boiler_fixed_flow_temp - cfg.reference_room_temp
    if span <= 0:
        return 1.0
    duty = (flow - cfg.reference_room_temp) / span
    return round(min(1.0, max(cfg.duty_min, duty)), 3)


class OutdoorEngine:
    """Outdoor source selection, damping and forecast (the season is in season.py)."""

    def __init__(self) -> None:
        """Start without history."""
        self.current: float | None = None
        self.source: str | None = None
        self.damped: float | None = None
        self.forecast: float | None = None
        self.use_forecast = False
        self.updated_at: datetime | None = None

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

    @property
    def effective(self) -> float | None:
        """Temperature used for the heating limit and the curve.

        With the forecast enabled (FR-EQ-06) it is the mean of the damped value
        and the average forecast for the next 24 hours.
        """
        if self.damped is None:
            return self.forecast if self.use_forecast else None
        if self.use_forecast and self.forecast is not None:
            return (self.damped + self.forecast) / 2
        return self.damped

    def update(self, snap: Snapshot, cfg: SystemConfig) -> None:
        """Read the source and update the EMA."""
        self.read(snap, cfg)
        self.use_forecast = cfg.use_forecast
        self.forecast = snap.forecast_24h if cfg.use_forecast else None
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

    @property
    def damped_rounded(self) -> float | None:
        """Damped temperature for display."""
        return None if self.damped is None else round(self.damped, 2)

    def to_dict(self) -> dict[str, Any]:
        """Serialize (FR-EQ-02: the damped value survives a restart)."""
        return {
            "damped": self.damped,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore from storage."""
        self.damped = data.get("damped")
        if updated := data.get("updated_at"):
            self.updated_at = datetime.fromisoformat(updated)
