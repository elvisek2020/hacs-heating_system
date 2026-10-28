"""What the scheme card reads from the core: flow and valve travel (FR-UI-25)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c

from .helpers import House, controller, room

OPTIONS = {c.CONF_HAS_BYPASS: True, c.CONF_BOILER_MIN_ON: 5}


def test_last_flow_is_the_end_of_the_flow_and_survives_a_restart() -> None:
    ctrl = controller(room("obyvak"), **OPTIONS)
    house = House(ctrl, temperatures={"obyvak": 18.0})
    living = ctrl.rooms["id_obyvak"]
    for _ in range(20):
        house.run(30)
        if living.flowing:
            break
    assert living.flowing
    assert living.last_flow is None  # no change of the attribute while water flows

    house.temp("obyvak", 23.0)
    for _ in range(40):
        house.run(30)
        if not living.flowing:
            break
    assert not living.flowing
    ended = living.last_flow
    assert ended is not None
    assert house.now - ended <= timedelta(seconds=30)
    house.run(10 * 60)
    assert living.last_flow == ended  # stays while nothing flows

    again = controller(room("obyvak"), **OPTIONS)
    again.rooms["id_obyvak"].restore(living.to_dict())
    assert again.rooms["id_obyvak"].last_flow == ended


def test_valve_travel_while_it_moves() -> None:
    ctrl = controller(room("obyvak"), room("kuchyn"), **OPTIONS)
    house = House(ctrl, temperatures={"obyvak": 18.0, "kuchyn": 23.0})
    kitchen = ctrl.rooms["id_kuchyn"]
    valve = kitchen.cfg.valves[0]
    # The warm kitchen closes its valve before the boiler starts for the living room.
    for _ in range(4):
        house.run(30)
        if kitchen.valves_moving(house.now):
            break
    since, until = kitchen.valves_moving(house.now)
    assert (until - since).total_seconds() == valve.close_time_s
    assert since <= house.now < until
    house.run(valve.close_time_s + 30)
    assert kitchen.valves_moving(house.now) is None
