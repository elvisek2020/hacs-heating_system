"""Thermal model of the virtual house used by the demo mode (pure Python).

Deliberately simple, but with the dynamics that matter for the controller:
valve heads open slowly, radiators warm up with a delay, rooms lose heat to
the outside and much faster with an open window.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

# Room cools down with a time constant of 20 h, a radiator at full power
# heats it with 1.5 times that conductance. With 40 °C water and 5 °C outside
# a fully open room settles around 26 °C and warms by roughly 1 K per hour.
LOSS_PER_S = 1 / 72000
GAIN_PER_S = 1.5 / 72000
WINDOW_LOSS_FACTOR = 10.0
RADIATOR_TAU_S = 600.0


@dataclass(slots=True)
class RoomThermal:
    """State of one simulated room."""

    temperature: float
    radiator: float
    opening: float = 1.0  # 0 = valves closed, 1 = fully open

    def step(
        self,
        dt_s: float,
        *,
        valves_open: float,
        travel_s: float,
        water_temp: float | None,
        outdoor: float,
        window_open: bool,
    ) -> None:
        """Advance the room by `dt_s` seconds.

        `valves_open` is the share of the room's valve heads commanded open,
        `water_temp` is None when the boiler is off.
        """
        rate = dt_s / max(travel_s, 1.0)
        if self.opening < valves_open:
            self.opening = min(valves_open, self.opening + rate)
        else:
            self.opening = max(valves_open, self.opening - rate)
        supply = self.temperature if water_temp is None else water_temp
        target = self.temperature + self.opening * (supply - self.temperature)
        self.radiator += (target - self.radiator) * (1 - math.exp(-dt_s / RADIATOR_TAU_S))
        loss = LOSS_PER_S * (WINDOW_LOSS_FACTOR if window_open else 1.0)
        change = GAIN_PER_S * (self.radiator - self.temperature) - loss * (
            self.temperature - outdoor
        )
        self.temperature += change * dt_s

    def to_dict(self) -> dict[str, float]:
        """Serialize."""
        return {"temperature": self.temperature, "radiator": self.radiator, "opening": self.opening}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomThermal:
        """Restore."""
        return cls(
            temperature=float(data["temperature"]),
            radiator=float(data["radiator"]),
            opening=float(data.get("opening", 1.0)),
        )


def initial_room(index: int) -> RoomThermal:
    """Different starting temperatures, so rooms do not move in lockstep."""
    temperature = 19.0 + (index % 4) * 0.7
    return RoomThermal(temperature=temperature, radiator=temperature)
