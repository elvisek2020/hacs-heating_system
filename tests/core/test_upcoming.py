"""What happens next, for the animated scheme (FR-UI-25)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.model import BoilerReason
from custom_components.hydronic_heating.core.upcoming import upcoming

from .helpers import House, controller, room


def test_boiler_waits_for_valves_then_runs_its_minimum() -> None:
    ctrl = controller(room("a"), room("b"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"a": 25.0, "b": 25.0})
    house.run(60)
    house.temp("a", 15.0)
    house.run(30)
    assert ctrl.boiler_status.reason is BoilerReason.PRE_CLOSE
    events = upcoming(ctrl, house.now)
    assert events[0].kind == "boiler_start"
    assert events[0].at == ctrl.boiler_status.until
    house.run(180)
    assert house.boiler_on
    first = upcoming(ctrl, house.now)[0]
    assert first.kind == "min_on_end"
    assert first.at == ctrl.sequencer.min_on_until(ctrl.cfg)


def test_overrun_ends_with_valves_at_rest() -> None:
    ctrl = controller(room("a"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"a": 15.0})
    house.run(10 * 60)
    house.temp("a", 25.0)
    house.run(60)
    assert ctrl.boiler_status.reason is BoilerReason.OVERRUN
    event = upcoming(ctrl, house.now)[0]
    assert (event.kind, event.params["policy"]) == ("valves_idle", "deenergize")


def test_rooms_by_schedule() -> None:
    ctrl = controller(room("a"), room("b"), **{c.CONF_HOUSE_SCHEDULE_ENTITY: "schedule.dum"})
    house = House(ctrl, temperatures={"a": 21.0, "b": 21.0})
    switch_off = house.now + timedelta(hours=2)
    house.set("schedule.dum", "on", next_event=switch_off.isoformat())
    house.run(60)
    events = upcoming(ctrl, house.now)
    assert [(e.kind, e.rooms) for e in events] == [("schedule_eco", ("A", "B"))]
    assert events[0].params["all_rooms"] is True
    assert events[0].at == switch_off


def test_manual_end_and_no_schedule_while_manual() -> None:
    ctrl = controller(room("a"), **{c.CONF_HOUSE_SCHEDULE_ENTITY: "schedule.dum"})
    house = House(ctrl, temperatures={"a": 21.0})
    house.set("schedule.dum", "on", next_event=(house.now + timedelta(hours=2)).isoformat())
    ctrl.start_manual(30, house.now)
    house.run(60)
    kinds = [e.kind for e in upcoming(ctrl, house.now)]
    assert "manual_end" in kinds
    assert "schedule_eco" not in kinds
