"""Sensor validation and aggregation (FR-ROOM-03, FR-ROOM-04)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import statistics

from .model import EntityReading


@dataclass(frozen=True, slots=True)
class Aggregate:
    """Aggregated temperature with the sensors that took part."""

    value: float | None
    valid: tuple[str, ...]
    invalid: tuple[str, ...]


def is_valid(
    reading: EntityReading,
    now: datetime,
    minimum: float,
    maximum: float,
    stale_timeout_s: float,
) -> bool:
    """Return True when a reading is available, in range and fresh enough."""
    if not reading.available or reading.value is None:
        return False
    if not minimum <= reading.value <= maximum:
        return False
    if stale_timeout_s > 0 and reading.last_reported is not None:
        return (now - reading.last_reported).total_seconds() <= stale_timeout_s
    return True


def combine(values: Sequence[float], method: str) -> float:
    """Combine valid values; `priority` keeps the first one in configured order."""
    if method == "min":
        return min(values)
    if method == "max":
        return max(values)
    if method == "median":
        return float(statistics.median(values))
    if method == "priority":
        return values[0]
    return sum(values) / len(values)


def aggregate(
    entity_ids: Sequence[str],
    readings: dict[str, EntityReading],
    now: datetime,
    *,
    method: str,
    minimum: float,
    maximum: float,
    stale_timeout_s: float,
) -> Aggregate:
    """Validate the sensors of a room and aggregate the valid ones."""
    valid: list[str] = []
    invalid: list[str] = []
    values: list[float] = []
    for entity_id in entity_ids:
        reading = readings.get(entity_id)
        if reading is not None and is_valid(reading, now, minimum, maximum, stale_timeout_s):
            valid.append(entity_id)
            values.append(float(reading.value))  # type: ignore[arg-type]
        else:
            invalid.append(entity_id)
    value = round(combine(values, method), 2) if values else None
    return Aggregate(value=value, valid=tuple(valid), invalid=tuple(invalid))
