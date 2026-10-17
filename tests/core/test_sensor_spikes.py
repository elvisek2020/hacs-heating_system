"""Wrong samples of a sensor: jumps, 0.0 and frost (FR-ROOM-08, FR-FROST-03).

The samples are real: an IKEA Alpstuga (Matter over Thread) in the study on
17 October 2026. After a reconnect it sent 0.0, then a value with an offset of
about +3 K that settled back within minutes.
"""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.model import BoilerReason

from .helpers import House, controller, room

# 7:42:25 – 7:50:22, seconds from the first sample.
MORNING = [
    (0, 20.25), (29, 20.23), (40, 0.0), (41, 23.6), (61, 23.52), (91, 22.86), (121, 22.33),
    (150, 22.12), (180, 21.99), (210, 21.87), (239, 21.82), (269, 21.8), (299, 21.79),
    (328, 21.77), (358, 21.76), (388, 21.75), (418, 21.74), (447, 21.73), (477, 21.72),
]  # fmt: skip
# 8:12:39 – 8:25:13: a jump of +3.1 K, then 15 minutes back towards +0.8 K.
LATER = [
    (0, 21.91), (21, 25.04), (41, 24.92), (71, 24.32), (100, 23.96), (130, 23.7),
    (160, 23.47), (189, 23.33), (219, 23.27), (249, 23.23), (278, 23.2), (308, 23.17),
    (338, 23.14), (368, 23.11), (397, 23.08), (427, 23.05), (457, 23.03), (486, 23.0),
    (516, 22.98), (546, 22.96), (576, 22.94), (605, 22.92), (635, 22.9), (665, 22.88),
    (694, 22.87), (724, 22.85), (754, 22.83),
]  # fmt: skip
STUDY = {
    c.CONF_VENT_DETECT: True,
    c.CONF_SENSOR_SPIKE: 3,
    c.CONF_SENSOR_MIN: -20,  # the setting of that morning: 0.0 was a valid value
    c.CONF_COMFORT_TEMP: 19,
}


def _replay(house: House, slug: str, samples: list[tuple[int, float]]) -> list[dict]:
    """Feed the samples at their times with a tick every 30 s in between."""
    house.fresh_sensors = False  # a tick does not make a new sample
    start = house.now
    timeline = sorted(
        [(t, value) for t, value in samples]
        + [(t, None) for t in range(30, samples[-1][0] + 1, 30)],
        key=lambda item: (item[0], item[1] is None),
    )
    seen = []
    room_ctrl = house.ctrl.rooms[f"id_{slug}"]
    for t, value in timeline:
        house.now = start + timedelta(seconds=t)
        if value is not None:
            house.temp(slug, value)
        house.step()
        seen.append(
            {
                "t": t,
                "temperature": room_ctrl.temperature,
                "frost": room_ctrl.frost_active,
                "airing": room_ctrl.vent.active,
                "filtered": room_ctrl.filtered_sources,
                "boiler": house.ctrl.boiler_status.reason,
            }
        )
    return seen


def _warm_up(slug: str, value: float, **options: object) -> House:
    ctrl = controller(room(slug, **{**STUDY, **options}), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={slug: value})
    house.run(10 * 60)
    return house


def test_zero_and_offset_after_a_reconnect_start_nothing() -> None:
    """7:43: 20.23 → 0.0 → 23.6 → 22.1 is no frost, no boiler start and no airing."""
    house = _warm_up("pracovna", 20.25)
    seen = _replay(house, "pracovna", MORNING)
    assert not any(s["frost"] for s in seen)
    assert not any(s["airing"] for s in seen)
    assert {s["boiler"] for s in seen} == {BoilerReason.IDLE}
    temperatures = [s["temperature"] for s in seen]
    assert 0.0 not in temperatures
    assert 23.6 not in temperatures
    # The 0.0 and the first value with the offset wait; the next close sample confirms it.
    by_time = {s["t"]: s for s in seen}
    assert by_time[40]["temperature"] == 20.23
    assert by_time[40]["filtered"] == ("sensor.pracovna",)
    assert by_time[41]["temperature"] == 20.23
    assert by_time[61]["temperature"] == 23.52
    assert by_time[61]["filtered"] == ()


def test_an_offset_that_settles_back_is_no_airing() -> None:
    """8:13: +3.1 K, then back by 1.3 K in under 2 minutes; that day it was taken for airing."""
    house = _warm_up("pracovna", 21.91)
    seen = _replay(house, "pracovna", LATER)
    assert not any(s["airing"] for s in seen)
    assert seen[-1]["temperature"] == 22.83


def test_real_airing_is_still_noticed() -> None:
    """14. 10.: 19.8 → 15.8 °C within 4 minutes, a sample every 30 s."""
    house = _warm_up("pracovna", 19.8)
    samples = [(30 * i, round(19.8 - 0.5 * i, 1)) for i in range(9)]
    seen = _replay(house, "pracovna", samples)
    assert not any(s["filtered"] for s in seen)
    assert seen[-1]["airing"]


def test_frost_needs_two_samples() -> None:
    """Without the jump filter a single 0.0 still is no frost (FR-FROST-03)."""
    house = _warm_up("pracovna", 20.25, **{c.CONF_SENSOR_SPIKE: 0, c.CONF_VENT_DETECT: False})
    seen = _replay(house, "pracovna", [(0, 20.23), (11, 0.0), (12, 23.6), (32, 23.52)])
    assert any(s["temperature"] == 0.0 for s in seen)
    assert not any(s["frost"] for s in seen)
    # A real frost: the second sample below confirms it.
    seen = _replay(house, "pracovna", [(0, 4.0), (30, 3.9)])
    assert not seen[0]["frost"]
    assert seen[-1]["frost"]


def test_frost_after_a_while_without_new_samples() -> None:
    house = _warm_up("pracovna", 6.0, **{c.CONF_SENSOR_SPIKE: 0, c.CONF_VENT_DETECT: False})
    seen = _replay(house, "pracovna", [(0, 4.0), (90, 4.0)])
    assert not seen[0]["frost"]
    assert [s["frost"] for s in seen if s["t"] >= 60] == [True, True, True]


def test_a_jump_without_a_close_sample_counts_after_a_minute() -> None:
    house = _warm_up("pracovna", 20.0, **{c.CONF_VENT_DETECT: False})
    seen = _replay(house, "pracovna", [(0, 20.0), (10, 26.0), (90, 26.0)])
    by_time = {s["t"]: s for s in seen}
    assert by_time[10]["temperature"] == 20.0
    assert by_time[60]["temperature"] == 20.0
    assert by_time[90]["temperature"] == 26.0


def test_a_value_out_of_range_keeps_the_last_one() -> None:
    """With `sensor_min` 1 °C the 0.0 is invalid; the room keeps its last value.

    It does not switch to the backup sensor with its other offset (FR-ROOM-07).
    """
    data = {
        **STUDY,
        c.CONF_SENSORS: ["sensor.pracovna", "sensor.herna"],
        c.CONF_AGGREGATION: "priority",
        c.CONF_SENSOR_MIN: 1,
        c.CONF_SENSOR_SPIKE: 0,
    }
    ctrl = controller(room("pracovna", **data), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"pracovna": 20.23, "herna": 19.5})
    house.run(5 * 60)
    house.temp("pracovna", 0.0)
    house.step()
    study = ctrl.rooms["id_pracovna"]
    assert study.temperature == 20.23
    assert study.held_sources == ("sensor.pracovna",)


def test_a_change_of_settings_keeps_a_waiting_jump() -> None:
    """A jump waiting for its confirmation stays held back across a change of settings."""
    house = _warm_up("pracovna", 20.23)
    ctrl = house.ctrl
    house.fresh_sensors = False
    house.now += timedelta(seconds=10)
    house.temp("pracovna", 0.0)
    house.step()
    ctrl.reconfigure(ctrl.cfg, [r.cfg for r in ctrl.rooms.values()])
    house.now += timedelta(seconds=1)
    house.step()
    study = ctrl.rooms["id_pracovna"]
    assert study.temperature == 20.23
    assert study.filtered_sources == ("sensor.pracovna",)
    assert study.settle_until is not None
