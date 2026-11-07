"""External hold of the boiler by a calendar or an on/off entity (FR-BOI-10)."""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.controller import HydronicController
from custom_components.hydronic_heating.core.model import BoilerReason, ValveReason
from custom_components.hydronic_heating.core.upcoming import upcoming

from .helpers import House, controller, room

HOLD = "binary_sensor.nabijeni"
CALENDAR = "calendar.nabijeni"


def _cold(entity: str = HOLD, **options) -> tuple[HydronicController, House]:
    ctrl = controller(
        room("obyvak"),
        **{c.CONF_HAS_BYPASS: True, c.CONF_EXTERNAL_HOLD_ENTITY: entity, **options},
    )
    return ctrl, House(ctrl, temperatures={"obyvak": 17.0})


def _local(ctrl: HydronicController, when: datetime) -> str:
    """Calendar attributes are local times without a zone."""
    return when.astimezone(ctrl.cfg.timezone).strftime("%Y-%m-%d %H:%M:%S")


def _until(house: House, done, limit_min: int = 60) -> list:
    """Step every 30 s until `done()`, collecting the decisions."""
    decisions = []
    for _ in range(limit_min * 2):
        if done():
            return decisions
        house.run(30)
        decisions += house.ctrl.decisions
    raise AssertionError("not reached")


def _window(house: House, ctrl: HydronicController, start: datetime, minutes: int, state: str):
    end = start + timedelta(minutes=minutes)
    house.set(CALENDAR, state, start_time=_local(ctrl, start), end_time=_local(ctrl, end))


def test_hold_keeps_the_boiler_off_until_it_ends() -> None:
    ctrl, house = _cold()
    house.set(HOLD, "on")
    house.step()
    held_at = house.now
    house.run(30 * 60)
    assert not house.boiler_on
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.EXTERNAL_HOLD
    assert status.until == held_at + timedelta(minutes=90)  # the limit, no known end
    assert status.params["hold_entity"] == HOLD
    assert status.params["hold_state"] == "active"
    assert ctrl.blocked_by == ["external_hold"]
    assert [(e.kind, e.at) for e in upcoming(ctrl, house.now)][:1] == [
        ("boiler_may_start", held_at + timedelta(minutes=90))
    ]
    # The boiler cannot start: the NO head stays without current.
    assert house.state("switch.hlavice_obyvak") == "off"
    assert ctrl.valve_status["switch.hlavice_obyvak"].reason is ValveReason.IDLE_POLICY

    house.set(HOLD, "off")
    house.run(5 * 60)
    assert house.boiler_on
    assert ctrl.external_hold.state == "off"


def test_calendar_stops_the_boiler_before_the_window_and_starts_it_after() -> None:
    ctrl, house = _cold(CALENDAR)
    house.set(CALENDAR, "off")
    house.run(15 * 60)
    assert house.boiler_on
    # A window in 15 min is outside the lead of 10 min.
    start = house.now + timedelta(minutes=15)
    _window(house, ctrl, start, 30, "off")
    house.run(4 * 60)
    assert house.boiler_on
    assert ctrl.external_hold.state == "off"

    decisions = _until(house, lambda: not house.boiler_on)
    assert house.now == start - timedelta(minutes=10)  # the minimum run is long over
    off = next(d for d in decisions if d.kind == "boiler_off")
    assert off.params["cause"] == "external_hold"
    assert off.params["hold_starts"] == start
    house.run(5 * 60)  # the overrun
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.EXTERNAL_HOLD
    assert status.params["hold_state"] == "upcoming"
    assert status.until == start + timedelta(minutes=30)  # the end of the window

    _window(house, ctrl, start, 30, "on")
    house.run((start + timedelta(minutes=30) - house.now).total_seconds())
    assert not house.boiler_on
    house.set(CALENDAR, "off")
    house.run(5 * 60)
    assert house.boiler_on


def test_running_boiler_keeps_its_minimum_run_before_the_window() -> None:
    """With a lead as long as the minimum run the boiler stops before the window."""
    ctrl, house = _cold(CALENDAR, **{c.CONF_BOILER_MIN_ON: 10})
    house.set(CALENDAR, "off")
    _until(house, lambda: house.boiler_on)
    house.run(2 * 60)
    # The window moved: it now starts within the lead.
    start = house.now + timedelta(minutes=10)
    _window(house, ctrl, start, 30, "off")
    house.step()
    status = ctrl.boiler_status
    assert status.reason is BoilerReason.MIN_ON_HOLD
    assert status.params["hold_state"] == "upcoming"
    _until(house, lambda: not house.boiler_on)
    assert house.now < start
    assert ctrl.sequencer.off_since == ctrl.sequencer.on_since + timedelta(minutes=10)


def test_long_hold_lets_the_boiler_run_and_is_reported() -> None:
    ctrl, house = _cold(**{c.CONF_EXTERNAL_HOLD_MAX: 30})
    house.set(HOLD, "on")
    house.run(29 * 60)
    assert not house.boiler_on
    assert "external_hold_long" not in ctrl.problems
    house.run(5 * 60)
    assert house.boiler_on
    assert ctrl.external_hold.state == "expired"
    problem = ctrl.problems["external_hold_long"]
    assert dict(problem.placeholders) == {"entity": HOLD, "minutes": "30"}
    house.set(HOLD, "off")
    house.step()
    assert "external_hold_long" not in ctrl.problems


def test_frost_overrides_the_hold_manual_heating_does_not() -> None:
    ctrl, house = _cold()
    house.set(HOLD, "on")
    ctrl.start_manual(60, house.now)
    house.run(10 * 60)
    assert not house.boiler_on
    assert ctrl.boiler_status.reason is BoilerReason.EXTERNAL_HOLD
    house.temp("obyvak", 3.0)
    house.run(5 * 60)
    assert house.boiler_on
    assert ctrl.external_hold.state == "active"
    assert ctrl.blocked_by == []


def test_unavailable_entity_or_none_set_does_not_hold() -> None:
    ctrl, house = _cold()
    house.set(HOLD, "unavailable")
    house.run(5 * 60)
    assert house.boiler_on
    assert ctrl.external_hold.state == "off"
    ctrl, house = _cold(None)
    house.run(5 * 60)
    assert house.boiler_on
    assert HOLD not in ctrl.watched_entities()


def test_shadow_mode_only_computes_the_hold() -> None:
    ctrl, house = _cold(**{c.CONF_SHADOW_MODE: True})
    house.set(HOLD, "on")
    house.run(10 * 60)
    assert ctrl.boiler_status.reason is BoilerReason.EXTERNAL_HOLD
    assert ctrl.would_command()["boiler"] == "off"
    house.set(HOLD, "off")
    house.run(5 * 60)
    assert ctrl.would_command()["boiler"] == "on"
    assert not house.boiler_on  # shadow mode switches nothing
