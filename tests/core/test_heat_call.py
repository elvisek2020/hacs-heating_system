"""Valves of rooms at the boiler threshold stay open for the whole run (FR-VAL-05)."""

from __future__ import annotations

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.model import BoilerPhase, ValveReason

from .helpers import House, controller, room

OPTIONS = {c.CONF_HAS_BYPASS: True}


def _open(house: House, slug: str) -> bool:
    """NO heads: without current the valve is open."""
    return house.state(f"switch.hlavice_{slug}") == "off"


def _reason(house: House, slug: str) -> ValveReason:
    return house.ctrl.valve_status[f"switch.hlavice_{slug}"].reason


def test_boiler_never_fires_into_closed_valves_only() -> None:
    """The case of 28 October: no room at 100 %, all valves closed at the period end.

    The rooms at 60 % and 36 % keep their valves open while the boiler fires; the
    warm room stays closed.
    """
    rooms = ("obyvak", "loznice", "pracovna")
    ctrl = controller(*(room(slug) for slug in rooms), **OPTIONS)
    house = House(ctrl, temperatures={"obyvak": 20.0, "loznice": 20.4, "pracovna": 22.0})
    house.run(5 * 60)
    assert house.boiler_on
    assert [ctrl.rooms[f"id_{slug}"].demand for slug in rooms] == [60.0, 36.0, 0.0]
    firing = 0
    for _ in range(4 * 60):  # two hours, four PWM periods
        house.run(30)
        if ctrl.sequencer.phase is not BoilerPhase.FIRING:
            continue
        firing += 1
        assert _open(house, "obyvak") and _open(house, "loznice")
        assert _reason(house, "obyvak") is ValveReason.HEAT_CALL
        assert _reason(house, "loznice") is ValveReason.HEAT_CALL
        assert ctrl.valve_status["switch.hlavice_obyvak"].until is None
        assert not _open(house, "pracovna")
    assert firing == 4 * 60


def test_running_boiler_keeps_rooms_open_down_to_the_hysteresis() -> None:
    """At 24 % a room joins the run: the running boiler needs 30 % less 10 %."""
    ctrl = controller(room("obyvak"), room("loznice"), **OPTIONS)
    house = House(ctrl, temperatures={"obyvak": 20.25, "loznice": 20.6})
    house.run(45 * 60)
    assert house.boiler_on
    assert ctrl.rooms["id_loznice"].demand == 24.0
    assert _open(house, "loznice")
    assert _reason(house, "loznice") is ValveReason.HEAT_CALL


def test_room_below_the_threshold_follows_its_pwm_period() -> None:
    """At 18 % a room opens for 5.4 minutes of the period, then closes until the next."""
    ctrl = controller(room("obyvak"), room("loznice"), **OPTIONS)
    house = House(ctrl, temperatures={"obyvak": 19.0, "loznice": 20.7})
    house.run(10 * 60)
    assert house.boiler_on
    assert ctrl.rooms["id_loznice"].demand == 18.0
    assert not _open(house, "loznice")
    assert _reason(house, "loznice") is ValveReason.PWM
    assert _open(house, "obyvak")
    house.run(25 * 60)  # 11:35, inside the open part of the second period
    assert _open(house, "loznice")
    assert _reason(house, "loznice") is ValveReason.PWM
