"""Check that a running boiler really heats the water (FR-SAFE-08)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.flow_check import FlowCheck

from .helpers import T0, House, controller, room

FLOW = "sensor.stoupacka"
BURNER = "binary_sensor.horak"


def _update(check: FlowCheck, minute: float, temperature: float | None, running: bool = True):
    check.update(
        T0 + timedelta(minutes=minute),
        running=running,
        temperature=temperature,
        check_s=15 * 60,
        rise=5.0,
    )


def test_rise_from_the_lowest_value_is_ok() -> None:
    check = FlowCheck()
    for minute, temperature in ((0, 30.0), (5, 29.0), (10, 34.5)):
        _update(check, minute, temperature)
    assert check.state == "ok"
    assert check.rise == 5.5
    _update(check, 20, 34.0)
    assert not check.failed


def test_no_rise_stays_a_problem_until_a_run_heats() -> None:
    check = FlowCheck()
    for minute in range(16):
        _update(check, minute, 30.0 + minute * 0.2)
    assert check.failed
    assert check.state == "failed"
    # The boiler stops: nothing is known, the problem stays.
    _update(check, 16, 33.0, running=False)
    assert check.failed
    # The next run warms the water: the problem is gone.
    _update(check, 60, 30.0)
    _update(check, 65, 36.0)
    assert not check.failed
    assert check.state == "ok"


def test_short_runs_and_invalid_values_are_not_judged() -> None:
    check = FlowCheck()
    _update(check, 0, 30.0)
    _update(check, 10, 31.0, running=False)
    _update(check, 20, None)
    _update(check, 40, 200.0)
    assert check.state == "idle"
    assert not check.failed


def _cold_house(**options):
    ctrl = controller(
        room("obyvak"), **{c.CONF_FLOW_TEMP_ENTITY: FLOW, c.CONF_HAS_BYPASS: True, **options}
    )
    house = House(ctrl, temperatures={"obyvak": 17.0})
    house.set(FLOW, "30.0", 30.0)
    return ctrl, house


def test_boiler_that_does_not_heat_is_a_problem() -> None:
    ctrl, house = _cold_house()
    house.run(5 * 60)
    assert house.boiler_on
    assert ctrl.flow_check.state == "waiting"
    house.run(15 * 60)
    problem = ctrl.problems["no_heat"]
    assert problem.repair
    assert dict(problem.placeholders) == {"minutes": "15", "rise": "5"}
    # The water warms up: the problem is gone at once.
    house.set(FLOW, "36.0", 36.0)
    house.step()
    assert "no_heat" not in ctrl.problems
    assert ctrl.flow_check.state == "ok"


def test_only_the_burner_time_counts_with_feedback() -> None:
    ctrl, house = _cold_house(**{c.CONF_FEEDBACK_ENTITY: BURNER})
    house.set(BURNER, "off")
    house.run(30 * 60)
    assert house.boiler_on
    assert ctrl.flow_check.state == "idle"
    assert "no_heat" not in ctrl.problems
    house.set(BURNER, "on")
    house.run(16 * 60)
    assert "no_heat" in ctrl.problems


def test_no_check_in_shadow_mode_or_when_switched_off() -> None:
    for options in ({c.CONF_SHADOW_MODE: True}, {c.CONF_FLOW_CHECK_TIME: 0}):
        ctrl, house = _cold_house(**options)
        house.run(30 * 60)
        assert "no_heat" not in ctrl.problems
        assert ctrl.flow_temperature == 30.0
