"""Heating season from the 4-hour mean outdoor temperature (FR-EQ-03)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.hydronic_heating.core.controller import HydronicController
from custom_components.hydronic_heating.core.model import SystemMode, SystemState
from custom_components.hydronic_heating.core.season import HeatingSeason

from .helpers import T0, TZ, House, controller, room, system


def _feed(season: HeatingSeason, hours: float, value: float, start=T0) -> None:
    for minute in range(int(hours * 60)):
        season.update(start + timedelta(minutes=minute), value, 13.0, TZ)


def test_starts_as_soon_as_the_mean_drops_below() -> None:
    season = HeatingSeason()
    season.active = False
    _feed(season, 4, 16.0)
    assert not season.active
    # A cold evening: the 4 h mean falls under 13 °C, the season starts at once.
    _feed(season, 3, 8.0, start=T0 + timedelta(hours=4))
    assert season.mean_4h < 13
    assert season.active


def test_a_cold_evening_keeps_the_season() -> None:
    """Warm days with cold evenings never count as a whole day above the limit."""
    season = HeatingSeason()
    for day in range(5):
        start = T0 + timedelta(days=day)
        _feed(season, 8, 18.0, start=start)  # sunny day
        _feed(season, 6, 6.0, start=start + timedelta(hours=8))  # cold evening
    assert season.days_above == 0
    assert season.active


def test_manual_modes_and_storage() -> None:
    season = HeatingSeason()
    season.set_mode("off", T0)
    assert not season.active
    season.update(T0 + timedelta(minutes=1), 2.0, 13.0, TZ)
    assert not season.active  # by hand, the cold does not matter
    season.set_mode("on", T0)
    assert season.active
    restored = HeatingSeason()
    restored.restore(season.to_dict())
    assert (restored.mode, restored.active) == ("on", True)
    assert restored.samples == season.samples


def test_season_select_logs_the_change() -> None:
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.step()
    ctrl.set_season_mode("off", house.now)
    house.run(30)
    assert ctrl.state is SystemState.SUMMER
    season = [d for d in ctrl.decisions if d.kind == "season"]
    assert season[0].params["mode"] == "off"
    assert not house.boiler_on


def test_old_summer_mode_is_migrated() -> None:
    """Before 0.9 summer was a system mode; it becomes the off season."""
    ctrl = HydronicController(system(), [room("obyvak")])
    ctrl.restore(
        {"modes": {"mode": "summer", "mode_before_manual": "summer"}, "outdoor": {"summer": True}},
        T0,
    )
    assert ctrl.modes.mode is SystemMode.AUTO
    assert ctrl.modes.mode_before_manual is SystemMode.AUTO
    assert ctrl.season.mode == "off"
    assert not ctrl.season.active
