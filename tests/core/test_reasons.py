"""Why the boiler and the valves are in their state, and until when (FR-SAFE-07)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.model import (
    BoilerReason,
    Decision,
    SystemMode,
    ValveReason,
)

from .helpers import BOILER, T0, House, controller, room
from .test_equithermal import HOUSE

BYPASS = {c.CONF_HAS_BYPASS: True}


def _step(house: House) -> list[Decision]:
    house.step()
    return list(house.ctrl.decisions)


def _run(house: House, seconds: float) -> list[Decision]:
    """Advance time and collect every decision made on the way."""
    found: list[Decision] = []
    end = house.now + timedelta(seconds=seconds)
    while house.now < end:
        house.now += timedelta(seconds=30)
        found.extend(_step(house))
    return found


def _kinds(decisions: list[Decision]) -> list[str]:
    return [d.kind for d in decisions]


def test_sequence_without_bypass_waits_for_valves() -> None:
    house = House(controller(room("obyvak")), temperatures={"obyvak": 19.0})
    house.step()
    status = house.ctrl.boiler_status
    assert status.reason is BoilerReason.PRE_OPEN
    assert status.until == T0 + timedelta(seconds=120)
    assert status.rule == "valve_open_time = 120 s"

    decisions = _run(house, 120)
    assert house.boiler_on
    assert house.ctrl.boiler_status.reason is BoilerReason.FIRING_DEMAND
    assert house.ctrl.boiler_status.until is None
    assert _kinds(decisions) == ["boiler_on"]


def test_manual_then_stop_holds_min_on_with_end_time() -> None:
    """The case from the to-do list: manual 30 min, stop after 16 s, rooms warm."""
    ctrl = controller(room("obyvak"), **{**BYPASS, c.CONF_BOILER_MIN_ON: 10})
    house = House(ctrl, temperatures={"obyvak": 25.0})
    house.step()
    assert ctrl.boiler_status.reason is BoilerReason.IDLE

    ctrl.start_manual(30, house.now)
    decisions = _step(house)
    started = house.now
    assert house.boiler_on
    assert ctrl.boiler_status.reason is BoilerReason.FIRING_MANUAL
    assert ctrl.boiler_status.params["manual_until"] == started + timedelta(minutes=30)
    assert _kinds(decisions) == ["boiler_on"]

    house.now += timedelta(seconds=16)
    ctrl.stop(house.now)
    decisions = _step(house)
    assert house.boiler_on
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.MIN_ON_HOLD
    assert status.until == started + timedelta(minutes=10)
    assert status.rule == "boiler_min_on = 10 min"
    assert _kinds(decisions) == ["hold"]
    assert decisions[0].status.until == started + timedelta(minutes=10)

    # Switching modes changes nothing, the minimum run time still holds.
    ctrl.set_mode(SystemMode.OFF, house.now)
    assert _step(house) == []
    assert ctrl.boiler_status.reason is BoilerReason.MIN_ON_HOLD

    decisions = _run(house, 10 * 60)
    assert not house.boiler_on
    off = [d for d in decisions if d.kind == "boiler_off"]
    assert len(off) == 1
    assert off[0].params["cause"] == "min_on_done"
    assert off[0].status.reason is BoilerReason.OVERRUN
    assert ctrl.boiler_status.reason is BoilerReason.OVERRUN

    _run(house, 180)
    assert ctrl.boiler_status.reason is BoilerReason.OFF


def test_min_off_and_start_limit_delay_the_start() -> None:
    ctrl = controller(room("obyvak"), **{**BYPASS, c.CONF_BOILER_MAX_STARTS: 1})
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.step()
    assert house.boiler_on
    house.temp("obyvak", 23.0)
    _run(house, 5 * 60)
    assert not house.boiler_on
    stopped = ctrl.sequencer.off_since

    house.temp("obyvak", 19.0)
    decisions = _step(house)
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.MAX_STARTS_HOLD
    assert status.until == T0 + timedelta(hours=1)
    assert status.rule == "boiler_max_starts = 1/h"
    assert _kinds(decisions) == ["hold"]
    assert stopped is not None

    decisions = _run(house, 3600)
    assert house.boiler_on
    assert "boiler_on" in _kinds(decisions)


def test_min_off_hold() -> None:
    ctrl = controller(room("obyvak"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.step()
    house.temp("obyvak", 23.0)
    _run(house, 5 * 60)
    assert not house.boiler_on
    stopped = ctrl.sequencer.off_since
    assert stopped is not None

    house.temp("obyvak", 19.0)
    house.now += timedelta(seconds=30)
    decisions = _step(house)
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.MIN_OFF_HOLD
    assert status.until == stopped + timedelta(minutes=5)
    assert status.params == {"minutes": 5}
    assert _kinds(decisions) == ["hold"]


def test_duty_limit_reason_and_off_cause() -> None:
    ctrl = controller(room("obyvak"), **{**HOUSE, c.CONF_EQUITHERMAL_DUTY_ENABLED: True})
    house = House(ctrl, temperatures={"obyvak": 18.0})
    house.set("sensor.venku", "5", 5.0)
    house.step()
    assert house.boiler_on
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.FIRING_DEMAND
    assert status.until == house.now + timedelta(seconds=0.56 * 1200)
    assert status.rule == "duty_limit = 56 % / 20 min"

    decisions = _run(house, 13 * 60)
    off = [d for d in decisions if d.kind == "boiler_off"]
    assert off and off[0].params["cause"] == "duty_limit"
    assert ctrl.boiler_status.reason is BoilerReason.DUTY_HOLD
    assert ctrl.boiler_status.until == ctrl.sequencer.duty_hold_until


def test_blocked_and_idle_reasons() -> None:
    ctrl = controller(room("obyvak"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 23.0})
    house.step()
    assert ctrl.boiler_status.reason is BoilerReason.IDLE
    ctrl.set_season_mode("off", house.now)
    house.step()
    assert ctrl.boiler_status.reason is BoilerReason.SUMMER
    ctrl.set_mode(SystemMode.OFF, house.now)
    house.step()
    assert ctrl.boiler_status.reason is BoilerReason.OFF


def test_fault_and_recovery_reasons() -> None:
    ctrl = controller(room("obyvak"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 23.0})
    house.step()
    house.set(BOILER, "unavailable")
    house.now += timedelta(seconds=30)
    house.step()
    assert ctrl.boiler_status.reason is BoilerReason.FAULT_SAFE
    assert ctrl.boiler_status.params == {"fault": "boiler_unavailable"}

    house.set(BOILER, "off")
    house.now += timedelta(seconds=30)
    decisions = _step(house)
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.FAULT_RECOVERY
    assert status.until == house.now + timedelta(seconds=300)
    assert _kinds(decisions) == ["hold"]
    _run(house, 300)
    assert ctrl.boiler_status.reason is BoilerReason.IDLE


def test_fault_switches_the_boiler_off_with_its_cause() -> None:
    ctrl = controller(room("obyvak"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 19.0})
    _run(house, 60)
    assert house.boiler_on
    house.set(BOILER, "unavailable")
    decisions = _step(house)
    off = [d for d in decisions if d.kind == "boiler_off"]
    assert len(off) == 1
    assert off[0].params["cause"] == "fault:boiler_unavailable"
    assert ctrl.boiler_status.reason is BoilerReason.FAULT_SAFE


def test_startup_reason() -> None:
    ctrl = controller(room("obyvak"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set(BOILER, "unavailable")
    house.step()
    assert ctrl.boiler_status.reason is BoilerReason.STARTUP
    assert ctrl.boiler_status.until == T0 + timedelta(seconds=120)
    assert ctrl.valve_status["switch.hlavice_obyvak"].reason is ValveReason.STARTUP


def test_boiler_switched_outside_is_reverted_and_reported() -> None:
    ctrl = controller(room("obyvak"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 19.0})
    _run(house, 60)
    assert house.boiler_on

    house.set(BOILER, "off")
    decisions = _step(house)
    assert house.boiler_on
    reverted = [d for d in decisions if d.kind == "reverted"]
    assert len(reverted) == 1
    assert reverted[0].params["entity_id"] == BOILER
    assert reverted[0].params["output"] == "boiler"
    assert (reverted[0].params["observed"], reverted[0].params["desired"]) == (False, True)
    assert ctrl.last_revert is not None
    assert ctrl.last_revert["entity_id"] == BOILER


def test_own_decisions_are_not_reported_as_reverted() -> None:
    ctrl = controller(room("obyvak"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 19.0})
    decisions = _run(house, 60)
    house.temp("obyvak", 23.0)
    decisions += _run(house, 20 * 60)
    house.temp("obyvak", 19.0)
    decisions += _run(house, 20 * 60)
    assert "reverted" not in _kinds(decisions)
    assert ctrl.last_revert is None


def test_valve_switched_outside_is_reverted_with_its_reason() -> None:
    ctrl = controller(room("obyvak"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 15.0})  # full demand, valve open
    _run(house, 60)
    house.set("switch.hlavice_obyvak", "on")  # NO head energized = closed
    decisions = _step(house)
    reverted = [d for d in decisions if d.kind == "reverted"]
    assert len(reverted) == 1
    params = reverted[0].params
    assert params["output"] == "valve"
    assert (params["observed"], params["desired"]) == (False, True)
    assert params["valve_reason"] == ValveReason.HEAT_CALL
    assert house.state("switch.hlavice_obyvak") == "off"


def test_valve_reasons() -> None:
    ctrl = controller(room("obyvak", windows=["binary_sensor.okno"]), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set("binary_sensor.okno", "off")
    house.step()
    status = ctrl.valve_status["switch.hlavice_obyvak"]
    assert status.reason is ValveReason.HEAT_CALL

    house.set("binary_sensor.okno", "on")
    _run(house, 90)  # window delay 60 s, the boiler still runs its minimum time
    assert ctrl.valve_status["switch.hlavice_obyvak"].reason is ValveReason.WINDOW
    _run(house, 10 * 60)  # boiler idle: no current, whatever the window says
    assert ctrl.valve_status["switch.hlavice_obyvak"].reason is ValveReason.IDLE_POLICY

    ctrl.set_season_mode("off", house.now)
    house.set("binary_sensor.okno", "off")
    _run(house, 5 * 60)
    assert ctrl.valve_status["switch.hlavice_obyvak"].reason is ValveReason.IDLE_POLICY


def test_pwm_reason_has_the_next_switching_time() -> None:
    # TPI is the default algorithm; the cold living room runs the boiler and the
    # bedroom below the boiler threshold follows its PWM period.
    ctrl = controller(room("obyvak"), room("loznice"), **BYPASS)
    house = House(ctrl, temperatures={"obyvak": 19.0, "loznice": 20.7})
    house.step()
    room_ctrl = ctrl.rooms["id_loznice"]
    assert 0 < room_ctrl.demand < 20  # threshold 30 % less the hysteresis of a running boiler
    status = ctrl.valve_status["switch.hlavice_loznice"]
    assert status.reason in (ValveReason.PWM, ValveReason.MIN_STATE_HOLD)
    assert status.until is not None
    assert status.until > house.now
