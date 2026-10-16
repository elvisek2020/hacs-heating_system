"""Where the heat of the minimum run and of the overrun goes (FR-BOI-09, FR-MAN-06)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.model import BoilerReason, RoomHvacMode, ValveReason

from .helpers import House, controller, room

OPTIONS = {c.CONF_HAS_BYPASS: True, c.CONF_BOILER_MIN_ON: 10}
ROOMS = ("obyvak", "kuchyn", "loznice", "pracovna")


def _open(house: House, slug: str) -> bool:
    """NO heads: without current the valve is open."""
    return house.state(f"switch.hlavice_{slug}") == "off"


def _reason(house: House, slug: str) -> ValveReason:
    return house.ctrl.valve_status[f"switch.hlavice_{slug}"].reason


def _until_on(house: House) -> None:
    for _ in range(20):
        house.run(30)
        if house.boiler_on:
            return
    raise AssertionError("the boiler did not start")


def test_manual_then_stop_heats_all_rooms_in_the_min_run_and_the_overrun() -> None:
    """The case of 16 October: manual heating, Stop right away, every room warm.

    The minimum run and the overrun keep the valves of all rooms open; a room
    being aired and a room switched off stay closed.
    """
    ctrl = controller(*(room(slug) for slug in ROOMS), **OPTIONS)
    house = House(ctrl, temperatures=dict.fromkeys(ROOMS, 24.0))
    house.run(5 * 60)
    ctrl.ventilate(["id_loznice"], house.now)
    ctrl.rooms["id_pracovna"].set_hvac_mode(RoomHvacMode.OFF, house.now)
    ctrl.start_manual(30, house.now)
    _until_on(house)
    started = ctrl.sequencer.on_since
    assert ctrl.boiler_status.reason is BoilerReason.FIRING_MANUAL
    assert ctrl.boiler_status.params["heated"] == ("Obyvak", "Kuchyn")
    assert not ctrl.boiler_status.params["heated_all"]

    house.now += timedelta(seconds=6)
    ctrl.stop(house.now)
    house.step()
    house.run(60)
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.MIN_ON_HOLD
    assert status.params["heated"] == ("Obyvak", "Kuchyn")
    for slug in ("obyvak", "kuchyn"):
        assert _open(house, slug)
        assert _reason(house, slug) is ValveReason.MIN_RUN
        assert ctrl.valve_status[f"switch.hlavice_{slug}"].until == started + timedelta(minutes=10)
    assert not _open(house, "loznice")
    assert _reason(house, "loznice") is ValveReason.VENTILATION
    assert not _open(house, "pracovna")
    assert _reason(house, "pracovna") is ValveReason.ROOM_OFF

    house.run(9 * 60)
    assert not house.boiler_on
    assert ctrl.boiler_status.reason is BoilerReason.OVERRUN
    assert ctrl.boiler_status.params["heated"] == ("Obyvak", "Kuchyn")
    for slug in ("obyvak", "kuchyn"):
        assert _open(house, slug)
        assert _reason(house, slug) is ValveReason.OVERRUN
    assert not _open(house, "loznice")
    assert not _open(house, "pracovna")

    house.run(180)
    assert ctrl.boiler_status.reason is BoilerReason.IDLE
    assert _reason(house, "obyvak") is ValveReason.IDLE_POLICY


def test_all_rooms_after_manual_heating() -> None:
    ctrl = controller(room("obyvak"), room("kuchyn"), **OPTIONS)
    house = House(ctrl, temperatures={"obyvak": 24.0, "kuchyn": 24.0})
    house.run(5 * 60)
    ctrl.start_manual(30, house.now)
    _until_on(house)
    ctrl.stop(house.now)
    house.step()
    assert ctrl.boiler_status.reason is BoilerReason.MIN_ON_HOLD
    assert ctrl.boiler_status.params["heated_all"]


def test_normal_run_keeps_only_the_heated_rooms_open() -> None:
    """After an automatic run only the rooms that wanted heat get the rest of it."""
    ctrl = controller(room("obyvak"), room("kuchyn"), **OPTIONS)
    house = House(ctrl, temperatures={"obyvak": 18.0, "kuchyn": 24.0})
    _until_on(house)
    assert _open(house, "obyvak")
    assert not _open(house, "kuchyn")

    # The living room is warm before the minimum run is over.
    house.temp("obyvak", 23.0)
    house.run(60)
    assert ctrl.rooms["id_obyvak"].demand == 0
    assert ctrl.boiler_status.reason is BoilerReason.MIN_ON_HOLD
    assert ctrl.boiler_status.params["heated"] == ("Obyvak",)
    assert not _open(house, "kuchyn")
    # The valve keeps its minimum state time first, then the minimum run holds it.
    for _ in range(12):
        assert _open(house, "obyvak")
        if _reason(house, "obyvak") is ValveReason.MIN_RUN:
            break
        house.run(30)
    assert _reason(house, "obyvak") is ValveReason.MIN_RUN
    assert ctrl.boiler_status.reason is BoilerReason.MIN_ON_HOLD

    house.run(10 * 60)
    assert ctrl.boiler_status.reason is BoilerReason.OVERRUN
    assert ctrl.boiler_status.params["heated"] == ("Obyvak",)
    assert _open(house, "obyvak")
    assert _reason(house, "obyvak") is ValveReason.OVERRUN
    assert not _open(house, "kuchyn")


def test_overrun_through_the_bypass_only_without_heated_rooms() -> None:
    """A room aired at the end of the run gets no water; the overrun uses the bypass."""
    ctrl = controller(room("obyvak"), room("kuchyn"), **OPTIONS)
    house = House(ctrl, temperatures={"obyvak": 18.0, "kuchyn": 24.0})
    _until_on(house)
    house.run(10 * 60)
    ctrl.ventilate(["id_obyvak"], house.now)
    house.run(60)
    assert ctrl.boiler_status.reason is BoilerReason.OVERRUN
    assert ctrl.boiler_status.params["heated"] == ()
    assert not _open(house, "obyvak")
    assert not _open(house, "kuchyn")
