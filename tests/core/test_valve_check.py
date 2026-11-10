"""Check of the valves by the pipe temperature (FR-SAFE-09)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.valve_check import (
    NOT_CLOSING,
    NOT_OPENING,
    OK,
    UNKNOWN,
    ValveCheck,
)

from .helpers import T0, House, controller, room, valve

LIMITS = {"check_s": 600, "rise": 5.0, "closed_rise": 3.0, "hot": 40.0}
FLOW = "sensor.stoupacka"


def _step(check: ValveCheck, minute: float, temp: float | None, *, open_: bool | None, **kw):
    return check.update(
        T0 + timedelta(minutes=minute),
        expected_open=open_,
        temperature=temp,
        ready=kw.pop("ready", True),
        **{**LIMITS, **kw},
    )


def test_open_valve_must_warm_its_pipe() -> None:
    check = ValveCheck()
    assert _step(check, 0, 22.0, open_=True) is None
    assert _step(check, 4, 28.0, open_=True) == (UNKNOWN, OK)
    # A new window (the valve closed and opened again) without warming fails.
    _step(check, 5, 27.0, open_=False)
    _step(check, 6, 26.0, open_=True)
    assert _step(check, 15, 27.0, open_=True) is None
    assert _step(check, 16, 27.0, open_=True) == (OK, NOT_OPENING)
    assert check.failed
    # The problem stays until a later window passes.
    _step(check, 17, 27.0, open_=None)
    assert check.failed
    _step(check, 20, 26.0, open_=True)
    assert _step(check, 22, 41.0, open_=True) == (NOT_OPENING, OK)


def test_closed_valve_keeps_a_cold_pipe() -> None:
    check = ValveCheck()
    assert _step(check, 0, 22.0, open_=False) is None
    assert _step(check, 10, 23.0, open_=False) == (UNKNOWN, OK)
    check = ValveCheck()
    _step(check, 0, 22.0, open_=False)
    assert _step(check, 5, 26.0, open_=False) == (UNKNOWN, NOT_CLOSING)


def test_a_valve_that_just_closed_is_not_judged() -> None:
    check = ValveCheck()
    _step(check, 0, 48.0, open_=False)
    assert _step(check, 20, 30.0, open_=False) is None
    assert check.result == UNKNOWN


def test_nothing_is_judged_without_hot_water_or_while_moving() -> None:
    check = ValveCheck()
    for minute in range(0, 30, 2):
        assert _step(check, minute, 22.0, open_=True, ready=False) is None
        assert _step(check, minute + 1, 22.0, open_=None) is None
    assert check.result == UNKNOWN


def test_stuck_valve_is_reported_and_logged() -> None:
    """Bedroom warm, its valve closes before the boiler starts, but the pipe warms."""
    living = room(
        "obyvak",
        **{c.CONF_VALVES: [valve("switch.hlavice_obyvak", valve_temp_entity="sensor.t_o")]},
    )
    bedroom = room(
        "loznice",
        **{c.CONF_VALVES: [valve("switch.hlavice_loznice", valve_temp_entity="sensor.t_l")]},
    )
    ctrl = controller(
        living,
        bedroom,
        **{c.CONF_HAS_BYPASS: True, c.CONF_FLOW_TEMP_ENTITY: FLOW},
    )
    house = House(ctrl, temperatures={"obyvak": 17.0, "loznice": 23.0})
    house.set(FLOW, "50.0", 50.0)
    house.set("sensor.t_o", "22.0", 22.0)
    house.set("sensor.t_l", "22.0", 22.0)
    house.run(5 * 60)
    assert house.boiler_on
    # Hot water reaches the open living room valve; the bedroom pipe warms too.
    house.set("sensor.t_o", "45.0", 45.0)
    house.set("sensor.t_l", "27.0", 27.0)
    house.run(60)
    assert ctrl.valve_checks["switch.hlavice_obyvak"].result == OK
    problem = ctrl.problems["valve_not_closing_switch.hlavice_loznice"]
    assert problem.kind == "valve_not_closing"
    assert problem.repair
    assert ctrl.room_valve_check(ctrl.rooms["id_loznice"]) == (NOT_CLOSING, 27.0)
    assert ctrl.room_valve_check(ctrl.rooms["id_obyvak"]) == (OK, 45.0)


def test_logged_once_when_the_valve_fails() -> None:
    bedroom = room(
        "loznice",
        **{c.CONF_VALVES: [valve("switch.hlavice_loznice", valve_temp_entity="sensor.t_l")]},
    )
    ctrl = controller(room("obyvak"), bedroom, **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"obyvak": 17.0, "loznice": 23.0})
    house.set("sensor.t_l", "22.0", 22.0)
    logged = []
    firing = 0
    for _ in range(40):
        house.run(30)
        logged += [d for d in ctrl.decisions if d.kind == "valve_check"]
        firing = firing + 30 if house.boiler_on else 0
        if firing > 6 * 60:  # the check has started; now the closed pipe warms
            house.set("sensor.t_l", "30.0", 30.0)
    # Without a flow sensor the check starts after 5 min of firing.
    assert [d.params["result"] for d in logged] == [NOT_CLOSING]
    assert logged[0].params["room"] == "Loznice"


def _office(**options):
    """Pracovna: a valve with a pipe sensor, water around the 40 °C limit."""
    office = room(
        "pracovna",
        **{c.CONF_VALVES: [valve("switch.hlavice_pracovna", valve_temp_entity="sensor.t_p")]},
    )
    ctrl = controller(
        room("kuchyne"),
        office,
        **{c.CONF_HAS_BYPASS: True, c.CONF_FLOW_TEMP_ENTITY: FLOW, **options},
    )
    house = House(ctrl, temperatures={"kuchyne": 17.0, "pracovna": 23.0})
    house.set("sensor.t_p", "18.9", 18.9)
    return ctrl, house


def _run_at_the_limit(house: House, minutes: int, pipe=None) -> None:
    """Swing the water around 40 °C every minute, as in a house heated with 40 °C."""
    for minute in range(minutes):
        flow = 41.0 if minute % 2 else 39.5
        house.set(FLOW, str(flow), flow)
        if pipe is not None:
            house.set("sensor.t_p", str(pipe(minute)), pipe(minute))
        house.run(60)


def test_valve_that_does_not_open_is_found_with_water_at_the_limit() -> None:
    """10. 11.: manual heating, Pracovna open, water 38-42 °C, the pipe stayed at 18.9 °C.

    The check window started again whenever the water dipped below 40 °C, so it
    never ran its 10 min and the stuck valve was never reported.
    """
    ctrl, house = _office()
    ctrl.start_manual(60, house.now)
    house.set(FLOW, "41.0", 41.0)
    house.run(5 * 60)
    assert house.boiler_on
    assert house.state("switch.hlavice_pracovna") == "off"  # NO head: open
    _run_at_the_limit(house, 15)
    assert ctrl.valve_checks["switch.hlavice_pracovna"].result == NOT_OPENING
    assert "valve_not_opening_switch.hlavice_pracovna" in ctrl.problems


def test_working_valve_passes_with_water_at_the_limit() -> None:
    """A pipe that warms to 36 °C with 40 °C water is a working valve, no false alarm."""
    ctrl, house = _office()
    ctrl.start_manual(60, house.now)
    house.set(FLOW, "41.0", 41.0)
    house.set("sensor.t_p", "33.0", 33.0)  # already warm when the water reaches 40 °C
    house.run(5 * 60)
    _run_at_the_limit(house, 15, pipe=lambda minute: min(36.0, 33.0 + minute * 0.5))
    assert ctrl.valve_checks["switch.hlavice_pracovna"].result == OK
    assert not any(key.startswith("valve_") for key in ctrl.problems)


def test_closed_valve_that_lets_water_through_is_found_with_water_at_the_limit() -> None:
    """10. 11. 11:20: Pracovna closed, the pipe warmed from 19 to 31 °C, not reported."""
    ctrl, house = _office()
    house.set(FLOW, "41.0", 41.0)
    house.run(5 * 60)
    assert house.boiler_on
    assert house.state("switch.hlavice_pracovna") == "on"  # warm room: closed
    _run_at_the_limit(house, 12, pipe=lambda minute: min(31.0, 18.9 + minute))
    assert ctrl.valve_checks["switch.hlavice_pracovna"].result == NOT_CLOSING
