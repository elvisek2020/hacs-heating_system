"""Heating curve, duty limit and forecast (FR-EQ-04 to FR-EQ-06)."""

from __future__ import annotations

from datetime import timedelta
import itertools

import pytest

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.controller import HydronicController
from custom_components.hydronic_heating.core.equithermal import duty_limit, flow_setpoint
from custom_components.hydronic_heating.core.model import SystemMode

from .helpers import T0, House, controller, room, system

# The house from PRD chapter 10.3: water 40 °C, curve calibrated to it.
HOUSE = {
    c.CONF_DESIGN_FLOW_TEMP: 40,
    c.CONF_FLOW_TEMP_MIN: 25,
    c.CONF_BOILER_FIXED_FLOW_TEMP: 40,
    c.CONF_HAS_BYPASS: True,
    c.CONF_OUTDOOR_SENSORS: ["sensor.venku"],
}


# --- Heating curve (FR-EQ-04) -------------------------------------------------


@pytest.mark.parametrize(
    ("outdoor", "expected"),
    [
        (-12, 65.0),  # design point gives the design flow temperature
        (20, 30.0),  # no heating need: minimum
        (25, 30.0),  # above the reference temperature: no math error
        (-30, 75.0),  # limited to the maximum
        (0, 51.3),  # 20 + 45 * (20 / 32) ** (1 / 1.3)
    ],
)
def test_curve_defaults(outdoor: float, expected: float) -> None:
    assert flow_setpoint(outdoor, system()) == expected


def test_curve_offset_and_house_calibration() -> None:
    assert flow_setpoint(0, system(**{c.CONF_CURVE_OFFSET: 3})) == 54.3
    house = system(**HOUSE)
    assert flow_setpoint(-12, house) == 40.0
    assert flow_setpoint(5, house) == 31.2
    assert flow_setpoint(15, house) == 25.0


def test_curve_is_monotonic() -> None:
    cfg = system()
    values = [flow_setpoint(t, cfg) for t in range(-25, 25)]
    assert values == sorted(values, reverse=True)


# --- Duty limit (FR-EQ-05) ------------------------------------------------------


@pytest.mark.parametrize(
    ("flow", "expected"),
    [(31.2, 0.56), (25.0, 0.25), (21.0, 0.2), (40.0, 1.0), (55.0, 1.0)],
)
def test_duty_formula(flow: float, expected: float) -> None:
    assert duty_limit(flow, system(**HOUSE)) == expected


def _on_periods(house: House, seconds: int) -> list[tuple[float, float]]:
    """Run the house and return (start, length) of each boiler run in seconds."""
    runs: list[tuple[float, float]] = []
    started = None
    t = 0
    while t < seconds:
        house.run(30)
        t += 30
        if house.boiler_on and started is None:
            started = t
        elif not house.boiler_on and started is not None:
            runs.append((started, t - started))
            started = None
    return runs


def test_duty_limit_cycles_the_boiler() -> None:
    """With 5 °C outside the boiler runs 56 % of each 20 min cycle."""
    ctrl = controller(room("obyvak"), **{**HOUSE, c.CONF_EQUITHERMAL_DUTY_ENABLED: True})
    house = House(ctrl, temperatures={"obyvak": 18.0})
    house.set("sensor.venku", "5", 5.0)
    runs = _on_periods(house, 3600)
    assert ctrl.flow_setpoint == 31.2
    assert ctrl.duty == 0.56
    assert len(runs) >= 2
    for _, length in runs[:-1]:
        assert 672 <= length <= 702  # 0.56 * 1200 s, rounded to the 30 s step
    starts = [start for start, _ in runs]
    for a, b in itertools.pairwise(starts):
        assert 1200 <= b - a <= 1230  # one cycle


def test_duty_limit_never_shortens_below_min_on() -> None:
    """duty_min 0.2 * 20 min = 4 min, but the boiler keeps its 10 min minimum."""
    options = {
        **HOUSE,
        c.CONF_EQUITHERMAL_DUTY_ENABLED: True,
        c.CONF_BOILER_MIN_ON: 10,
        c.CONF_FLOW_TEMP_MIN: 20,
    }
    ctrl = controller(room("obyvak"), **options)
    house = House(ctrl, temperatures={"obyvak": 18.0})
    house.set("sensor.venku", "19", 19.0)
    runs = _on_periods(house, 3600)
    assert ctrl.duty == 0.2
    for _, length in runs[:-1]:
        assert 600 <= length <= 630


def test_duty_limit_reported_while_waiting() -> None:
    ctrl = controller(room("obyvak"), **{**HOUSE, c.CONF_EQUITHERMAL_DUTY_ENABLED: True})
    house = House(ctrl, temperatures={"obyvak": 18.0})
    house.set("sensor.venku", "5", 5.0)
    house.run(13 * 60)
    assert not house.boiler_on
    assert "duty_limit" in ctrl.blocked_by
    assert ctrl.sequencer.duty_holding(house.now)


@pytest.mark.parametrize(
    "options",
    [
        {**HOUSE},  # disabled (default)
        {**HOUSE, c.CONF_EQUITHERMAL_DUTY_ENABLED: True, c.CONF_OUTDOOR_SENSORS: []},  # no outdoor
    ],
)
def test_no_duty_limit(options: dict) -> None:
    ctrl = controller(room("obyvak"), **options)
    house = House(ctrl, temperatures={"obyvak": 18.0})
    house.set("sensor.venku", "5", 5.0)
    runs = _on_periods(house, 3600)
    assert runs == []  # one continuous run, never stopped
    assert house.boiler_on


def test_manual_ignores_duty_limit() -> None:
    ctrl = controller(room("obyvak"), **{**HOUSE, c.CONF_EQUITHERMAL_DUTY_ENABLED: True})
    house = House(ctrl, temperatures={"obyvak": 18.0})
    house.set("sensor.venku", "5", 5.0)
    ctrl.set_mode(SystemMode.MANUAL, T0)
    house.run(25 * 60)
    assert house.boiler_on


def test_duty_hold_survives_restart() -> None:
    options = {**HOUSE, c.CONF_EQUITHERMAL_DUTY_ENABLED: True}
    ctrl = controller(room("obyvak"), **options)
    house = House(ctrl, temperatures={"obyvak": 18.0})
    house.set("sensor.venku", "5", 5.0)
    house.run(13 * 60)
    hold = ctrl.sequencer.duty_hold_until
    assert hold is not None
    restarted = HydronicController(system(**options), [room("obyvak")])
    restarted.restore(ctrl.to_dict(), house.now)
    assert restarted.sequencer.duty_hold_until == hold
    assert not restarted.sequencer.can_start(house.now, restarted.cfg)
    assert restarted.sequencer.can_start(hold + timedelta(seconds=1), restarted.cfg)


# --- Forecast (FR-EQ-06) ------------------------------------------------------------


def test_forecast_complements_damped_temperature() -> None:
    """The effective temperature is the mean of the damped value and the forecast."""
    options = {
        c.CONF_OUTDOOR_SENSORS: ["sensor.venku"],
        c.CONF_USE_FORECAST: True,
        c.CONF_SUMMER_SWITCH_DELAY: 1,
    }
    ctrl = controller(room("obyvak"), **options)
    house = House(ctrl, temperatures={"obyvak": 21.0})
    house.set("sensor.venku", "12", 12.0)
    house.forecast = 22.0
    house.run(30)
    assert ctrl.outdoor.effective == 17.0
    assert ctrl.flow_setpoint == flow_setpoint(17.0, ctrl.cfg)
    house.run(3600)
    assert ctrl.outdoor.summer  # 17 °C > 15 °C, although the damped value is 12 °C

    house.forecast = None  # forecast unavailable: damped value alone
    house.run(30)
    assert ctrl.outdoor.effective == pytest.approx(12.0)


def test_forecast_ignored_when_disabled() -> None:
    ctrl = controller(room("obyvak"), outdoor_sensors=["sensor.venku"])
    house = House(ctrl, temperatures={"obyvak": 21.0})
    house.set("sensor.venku", "12", 12.0)
    house.forecast = 30.0
    house.run(30)
    assert ctrl.outdoor.effective == 12.0
