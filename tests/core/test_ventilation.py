"""Airing detected by a fast temperature drop (FR-WIN-06)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.model import TargetReason, ValveReason
from custom_components.hydronic_heating.core.ventilation import VentDetector

from .helpers import T0, House, controller, room

SETTINGS = {"drop_k": 1.0, "window_s": 300, "hold_s": 1200, "max_s": 2700}
SOURCES = ("sensor.a",)


def _step(det: VentDetector, minute: float, temp: float | None, sources=SOURCES, **kw):
    return det.update(
        T0 + timedelta(minutes=minute), temp, sources, enabled=True, **{**SETTINGS, **kw}
    )


def test_fast_drop_starts_airing_after_confirmation() -> None:
    det = VentDetector()
    assert _step(det, 0, 20.0) is None
    assert _step(det, 2, 19.4) is None
    assert _step(det, 3, 18.9) is None  # 1.1 K within 5 min, not yet confirmed
    assert _step(det, 3.5, 18.8) == "started"
    assert det.active
    assert det.drop == 1.2


def test_slow_drop_is_no_airing() -> None:
    det = VentDetector()
    for minute in range(0, 30):
        assert _step(det, minute, 20.0 - minute * 0.05) is None
    assert not det.active


def test_a_new_sensor_is_no_drop() -> None:
    det = VentDetector()
    _step(det, 0, 21.0)
    assert _step(det, 1, 19.0, sources=("sensor.b",)) is None
    assert _step(det, 2, 19.0, sources=("sensor.b",)) is None
    assert not det.active


def test_airing_ends_when_warming_after_the_hold_or_at_the_latest() -> None:
    det = VentDetector()
    for minute, temp in ((0, 20.0), (2, 18.8), (2.5, 18.7)):
        _step(det, minute, temp)
    assert det.active
    # Warmer again before the minimum pause: the pause holds.
    assert _step(det, 10, 19.0) is None
    assert _step(det, 22.5, 19.0) == "ended"
    # Still cold (window open): the pause ends at the latest after max_s.
    det = VentDetector()
    for minute, temp in ((0, 20.0), (2, 18.8), (2.5, 18.7)):
        _step(det, minute, temp)
    assert _step(det, 30, 18.0) is None
    assert _step(det, 47.5, 18.0) == "ended"


def test_switched_off_detection_ends_quietly() -> None:
    det = VentDetector()
    for minute, temp in ((0, 20.0), (2, 18.8), (2.5, 18.7)):
        _step(det, minute, temp)
    assert det.update(T0, 18.7, SOURCES, enabled=False, **SETTINGS) is None
    assert not det.active


def test_morning_airing_pauses_the_room_like_an_open_window() -> None:
    """Kitchen 14. 10.: 19.7 -> 17.7 °C in 8 min while the room wanted heat."""
    # A cold bedroom keeps the boiler running, so the kitchen valve is really closed.
    ctrl = controller(
        room("kuchyn", **{c.CONF_VENT_DETECT: True}), room("loznice"), **{c.CONF_HAS_BYPASS: True}
    )
    house = House(ctrl, temperatures={"kuchyn": 19.7, "loznice": 16.0})
    house.run(5 * 60)
    kitchen = ctrl.rooms["id_kuchyn"]
    assert kitchen.demand > 0
    decisions = []
    for step in range(16):  # 0.125 K per 30 s
        house.temp("kuchyn", round(19.7 - (step + 1) * 0.125, 3))
        house.run(30)
        decisions += [d for d in ctrl.decisions if d.kind == "ventilation"]
    assert kitchen.window_open
    assert kitchen.window_state == "open_detected"
    assert kitchen.demand == 0
    assert kitchen.target_reason is TargetReason.VENTILATION
    assert ctrl.valve_status["switch.hlavice_kuchyn"].reason is ValveReason.VENTILATION
    assert ctrl.window_rooms() == 1
    assert not ctrl.window_block  # airing never blocks the whole boiler
    started = decisions[0].params
    assert started["event"] == "started"
    assert started["pause_until"] == kitchen.vent.since + timedelta(minutes=20)
    # Window closed: the room warms up, after the minimum pause it heats again.
    house.temp("kuchyn", 18.2)
    house.run(20 * 60)
    assert not kitchen.window_open
    assert kitchen.demand > 0
