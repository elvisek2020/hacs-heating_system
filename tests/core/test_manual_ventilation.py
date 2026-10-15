"""Airing by hand and for the whole floor (FR-WIN-07)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.model import TargetReason, ValveReason

from .helpers import House, controller, room


def _events(ctrl):
    return [d.params["event"] for d in ctrl.decisions if d.kind == "ventilation"]


def test_airing_by_hand_pauses_extends_and_ends() -> None:
    # A cold bedroom keeps the boiler running, so the living room valve is really closed.
    ctrl = controller(room("obyvak"), room("loznice"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"obyvak": 19.0, "loznice": 16.0})
    house.run(5 * 60)
    living = ctrl.rooms["id_obyvak"]
    assert living.demand > 0
    ctrl.ventilate(["id_obyvak"], house.now)
    house.step()
    assert _events(ctrl) == ["manual_started"]
    assert living.window_open
    assert living.window_state == "open_manual"
    assert living.demand == 0
    assert living.target_reason is TargetReason.VENTILATION
    until = living.manual_vent_until
    assert living.target_until == until
    assert until - house.now == timedelta(minutes=15)
    house.run(60)
    assert ctrl.valve_status["switch.hlavice_obyvak"].reason is ValveReason.VENTILATION
    # Another press adds the time.
    ctrl.ventilate(["id_obyvak"], house.now)
    house.step()
    assert _events(ctrl) == ["manual_extended"]
    assert living.manual_vent_until == until + timedelta(minutes=15)
    logged = []
    for _ in range(60):
        house.run(30)
        logged += _events(ctrl)
        if not living.manual_vent:
            break
    assert logged == ["manual_ended"]
    assert living.demand > 0


def test_stop_and_quiet_after_airing() -> None:
    ctrl = controller(room("obyvak", **{c.CONF_VENT_DETECT: True}), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"obyvak": 20.0})
    house.run(5 * 60)
    living = ctrl.rooms["id_obyvak"]
    ctrl.ventilate(["id_obyvak"], house.now, minutes=5)
    house.run(60)
    ctrl.stop_ventilation(["id_obyvak"], house.now)
    house.step()
    assert _events(ctrl) == ["manual_ended"]
    assert not living.window_open
    # The aired room is cold; its next drop is not taken for airing for 10 minutes.
    for step in range(8):
        house.temp("obyvak", round(19.5 - step * 0.25, 2))
        house.run(30)
    assert not living.vent.active
    assert not living.window_open


def test_airing_noticed_in_one_room_airs_its_floor() -> None:
    ctrl = controller(
        room("kuchyn", **{c.CONF_VENT_DETECT: True}),
        room("obyvak"),
        room("loznice"),
        **{c.CONF_HAS_BYPASS: True},
    )
    ctrl.floors = {"id_kuchyn": "1np", "id_obyvak": "1np", "id_loznice": "2np"}
    house = House(ctrl, temperatures={"kuchyn": 19.7, "obyvak": 19.5, "loznice": 19.5})
    house.run(5 * 60)
    events = []
    for step in range(16):
        house.temp("kuchyn", round(19.7 - (step + 1) * 0.125, 3))
        house.run(30)
        events += [(d.params["room"], d.params["event"]) for d in ctrl.decisions]
    kitchen, living, bedroom = (ctrl.rooms[f"id_{r}"] for r in ("kuchyn", "obyvak", "loznice"))
    assert kitchen.vent.active
    assert living.manual_vent
    assert (living.vent_source, living.vent_trigger) == ("floor", "Kuchyn")
    assert not bedroom.window_open  # another floor
    assert ("Obyvak", "floor_started") in events
    assert living.manual_vent_until - kitchen.vent.since <= timedelta(minutes=20, seconds=30)
    assert ctrl.floor_rooms("id_obyvak") == ["id_kuchyn", "id_obyvak"]


def test_spreading_can_be_switched_off_and_airing_survives_a_restart() -> None:
    ctrl = controller(room("obyvak"), **{c.CONF_VENT_FLOOR_AUTO: False})
    house = House(ctrl, temperatures={"obyvak": 20.0})
    house.run(60)
    ctrl.ventilate(["id_obyvak"], house.now, minutes=30)
    data = ctrl.rooms["id_obyvak"].to_dict()
    again = controller(room("obyvak"))
    again.rooms["id_obyvak"].restore(data)
    assert again.rooms["id_obyvak"].manual_vent_until == ctrl.rooms["id_obyvak"].manual_vent_until
    assert again.rooms["id_obyvak"].vent_source == "manual"
