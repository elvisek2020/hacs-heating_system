"""Presence of the household and preheating (FR-SCH-02, FR-SCH-03)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.controller import HydronicController
from custom_components.hydronic_heating.core.model import (
    Preset,
    RoomHvacMode,
    SystemMode,
    SystemState,
    TargetReason,
    ValveReason,
)
from custom_components.hydronic_heating.core.presence import HeatRate

from .helpers import T0, House, controller, room, valve

FAMILY = "group.rodina"
LONG_AWAY = "binary_sensor.dlouho_pryc"
RETURN = "sensor.navrat"
PRESENCE = {
    c.CONF_HAS_BYPASS: True,
    c.CONF_HOUSE_PRESENCE_ENTITY: FAMILY,
    c.CONF_LONG_AWAY_ENTITY: LONG_AWAY,
    c.CONF_EXPECTED_RETURN_ENTITY: RETURN,
}


def _house(temp: float = 20.0, **options) -> tuple[HydronicController, House]:
    ctrl = controller(room("obyvak"), room("loznice"), **{**PRESENCE, **options})
    house = House(ctrl, temperatures={"obyvak": temp, "loznice": temp})
    house.set(FAMILY, "home")
    house.set(LONG_AWAY, "off")
    house.set(RETURN, "unknown")
    return ctrl, house


def _targets(ctrl: HydronicController) -> set[float | None]:
    return {r.target for r in ctrl.rooms.values()}


def test_nobody_home_lowers_to_eco_and_logs_it() -> None:
    ctrl, house = _house()
    house.step()
    assert _targets(ctrl) == {21.0}
    assert ctrl.presence_state == "home"

    house.set(FAMILY, "not_home")
    house.now += timedelta(seconds=30)
    house.step()
    assert _targets(ctrl) == {19.0}
    assert {r.effective_preset for r in ctrl.rooms.values()} == {Preset.ECO}
    assert ctrl.state is SystemState.AUTO
    presence = [d for d in ctrl.decisions if d.kind == "presence"]
    assert len(presence) == 1
    assert presence[0].params["state"] == "absent"

    house.set(FAMILY, "home")
    house.now += timedelta(seconds=30)
    house.step()
    assert _targets(ctrl) == {21.0}
    assert [d.params["state"] for d in ctrl.decisions if d.kind == "presence"] == ["home"]


def test_absence_preset_away() -> None:
    ctrl, house = _house(**{c.CONF_ABSENCE_PRESET: "away"})
    house.set(FAMILY, "not_home")
    house.step()
    assert _targets(ctrl) == {15.0}


def test_zone_count_and_unavailable_entity() -> None:
    ctrl, house = _house(**{c.CONF_HOUSE_PRESENCE_ENTITY: "zone.home"})
    house.set("zone.home", "0", 0.0)
    house.step()
    assert ctrl.house_present is False
    house.set("zone.home", "2", 2.0)
    house.run(30)
    assert ctrl.house_present is True
    # An unavailable entity keeps the last known state, it is not an absence.
    house.set("zone.home", "unavailable")
    house.run(30)
    assert ctrl.house_present is True
    assert _targets(ctrl) == {21.0}


def test_long_away_uses_away_without_changing_the_mode() -> None:
    ctrl, house = _house()
    house.step()
    house.set(FAMILY, "not_home")
    house.set(LONG_AWAY, "on")
    house.run(30)
    assert _targets(ctrl) == {15.0}
    assert ctrl.state is SystemState.AWAY
    assert ctrl.modes.mode is SystemMode.AUTO
    assert ctrl.presence_state == "long_away"
    assert "long_away" in [d.params["state"] for d in ctrl.decisions if d.kind == "presence"]


def test_permanent_room_change_wins_over_absence() -> None:
    ctrl, house = _house()
    ctrl.rooms["id_obyvak"].set_target(22.0, T0)
    house.set(FAMILY, "not_home")
    house.step()
    assert ctrl.rooms["id_obyvak"].hvac_mode is RoomHvacMode.HEAT
    assert ctrl.rooms["id_obyvak"].target == 22.0
    assert ctrl.rooms["id_loznice"].target == 19.0


def test_preheat_before_expected_return() -> None:
    """PRD acceptance: 1 K/h, dead time 15 min, eco 17 °C, comfort 20 °C."""
    options = {
        c.CONF_COMFORT_TEMP: 20.0,
        c.CONF_ECO_TEMP: 17.0,
        c.CONF_VALVES: [valve("switch.hlavice_obyvak", valve_open_time=300)],
    }
    ctrl = controller(room("obyvak", **options), **PRESENCE)
    obyvak = ctrl.rooms["id_obyvak"]
    obyvak.heat_rate.samples = {0: [1.0, 1.0, 1.0]}
    house = House(ctrl, temperatures={"obyvak": 17.0})
    back = datetime(2026, 1, 15, 16, 0, tzinfo=UTC)
    house.set(FAMILY, "not_home")
    house.set(LONG_AWAY, "off")
    house.set(RETURN, back.isoformat())
    house.step()
    assert obyvak.target == 17.0
    assert not obyvak.preheating
    # 3 K at 1 K/h + 15 min = 3 h 15 min before 16:00.
    assert obyvak.preheat_planned == datetime(2026, 1, 15, 12, 45, tzinfo=UTC)

    house.run(105 * 60 - 30)
    assert not obyvak.preheating
    house.run(30)
    assert obyvak.preheating
    assert obyvak.target == 20.0
    assert obyvak.preheat_until == back
    started = [d for d in ctrl.decisions if d.kind == "preheat"]
    assert len(started) == 1
    assert started[0].params["source"] == "return"
    assert ctrl.valve_status["switch.hlavice_obyvak"].reason is ValveReason.PREHEAT

    # The room warms up, the lead gets shorter, the preheat still runs.
    house.temp("obyvak", 19.0)
    house.run(60 * 60)
    assert obyvak.preheating
    # Nobody came: once the expected return is over, the room goes back to eco.
    house.run(3 * 3600)
    assert not obyvak.preheating
    assert obyvak.target == 17.0


def test_preheat_before_schedule_change() -> None:
    ctrl = controller(
        room("obyvak", **{c.CONF_SCHEDULE_ENTITY: "schedule.obyvak"}),
        **{c.CONF_HAS_BYPASS: True, c.CONF_PREHEAT_MAX: 1},
    )
    obyvak = ctrl.rooms["id_obyvak"]
    house = House(ctrl, temperatures={"obyvak": 19.0})
    comfort_from = T0 + timedelta(hours=2)
    house.set("schedule.obyvak", "off", next_event=comfort_from)
    house.step()
    assert obyvak.target == 19.0
    # Default 0.5 K/h would need 4 h, limited to preheat_max = 1 h.
    assert obyvak.preheat_planned == comfort_from - timedelta(hours=1)
    house.run(3600)
    assert obyvak.preheating
    assert obyvak.target == 21.0
    assert obyvak.preheat_source == "schedule"


def test_no_preheat_when_disabled_or_somebody_is_home_anyway() -> None:
    ctrl = controller(
        room("obyvak", **{c.CONF_SCHEDULE_ENTITY: "schedule.obyvak"}),
        **{c.CONF_HAS_BYPASS: True, c.CONF_PREHEAT_ENABLED: False},
    )
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set("schedule.obyvak", "off", next_event=T0 + timedelta(minutes=30))
    house.step()
    assert not ctrl.rooms["id_obyvak"].preheating
    assert ctrl.rooms["id_obyvak"].target == 19.0


def test_heat_rate_is_learned_from_a_heat_up() -> None:
    ctrl = controller(room("obyvak"), **{c.CONF_HAS_BYPASS: True})
    obyvak = ctrl.rooms["id_obyvak"]
    house = House(ctrl, temperatures={"obyvak": 18.0})
    house.step()
    temp = 18.0
    while temp < 21.0:
        house.run(30 * 60)
        temp += 0.5
        house.temp("obyvak", temp)
    house.run(30)
    assert obyvak.heat_rate.samples == {0: [pytest.approx(1.0, abs=0.01)]}
    # One sample is not enough yet, the default rate stays.
    assert obyvak.heat_rate.rate(None) == 0.5


def test_heat_rate_bands_and_storage() -> None:
    rate = HeatRate()
    rate.samples = {0: [0.8, 1.0, 1.2], -10: [0.3]}
    assert rate.rate(2.0) == 1.0
    assert rate.rate(-7.0) == 0.9  # too few in the band: median of everything
    restored = HeatRate()
    restored.restore(rate.to_dict())
    assert restored.samples == rate.samples


def test_house_schedule_applies_to_rooms_without_their_own() -> None:
    """FR-SCH-01: one schedule for the house; a room schedule overrides it."""
    ctrl = controller(
        room("obyvak"),
        room("loznice", **{c.CONF_SCHEDULE_ENTITY: "schedule.loznice"}),
        **{c.CONF_HAS_BYPASS: True, c.CONF_HOUSE_SCHEDULE_ENTITY: "schedule.dum"},
    )
    house = House(ctrl, temperatures={"obyvak": 20.0, "loznice": 20.0})
    house.set("schedule.dum", "off")
    house.set("schedule.loznice", "on")
    house.step()
    obyvak, loznice = ctrl.rooms["id_obyvak"], ctrl.rooms["id_loznice"]
    assert obyvak.schedule_entity == "schedule.dum"
    assert obyvak.target == 19.0
    assert loznice.schedule_entity == "schedule.loznice"
    assert loznice.target == 21.0

    house.set("schedule.dum", "on")
    house.run(30)
    assert obyvak.target == 21.0


def test_preheat_before_the_house_schedule() -> None:
    ctrl = controller(
        room("obyvak"),
        **{
            c.CONF_HAS_BYPASS: True,
            c.CONF_HOUSE_SCHEDULE_ENTITY: "schedule.dum",
            c.CONF_PREHEAT_MAX: 1,
        },
    )
    house = House(ctrl, temperatures={"obyvak": 19.0})
    comfort_from = T0 + timedelta(hours=2)
    house.set("schedule.dum", "off", next_event=comfort_from)
    house.step()
    obyvak = ctrl.rooms["id_obyvak"]
    assert obyvak.preheat_planned == comfort_from - timedelta(hours=1)
    house.run(3600)
    assert obyvak.preheating
    assert obyvak.preheat_source == "schedule"


def test_target_reason_and_presence_source() -> None:
    """Why a room has its target, and which presence entity it follows."""
    ctrl = controller(
        room("obyvak"),
        room("loznice", **{c.CONF_PRESENCE_ENTITY: "person.ronny"}),
        **{
            **PRESENCE,
            c.CONF_HOUSE_SCHEDULE_ENTITY: "schedule.dum",
            c.CONF_PREHEAT_ENABLED: False,
        },
    )
    house = House(ctrl, temperatures={"obyvak": 20.0, "loznice": 20.0})
    house.set(FAMILY, "home")
    house.set(LONG_AWAY, "off")
    house.set(RETURN, "unknown")
    house.set("person.ronny", "home")
    night_ends = T0 + timedelta(hours=8)
    house.set("schedule.dum", "off", next_event=night_ends)
    house.step()
    obyvak, loznice = ctrl.rooms["id_obyvak"], ctrl.rooms["id_loznice"]
    assert (obyvak.presence_entity, obyvak.presence_source) == (FAMILY, "house")
    assert (loznice.presence_entity, loznice.presence_source) == ("person.ronny", "room")
    assert obyvak.target_reason is TargetReason.SCHEDULE_ECO
    assert obyvak.target_until == night_ends

    # Ronny leaves: only the bedroom follows her, it is logged with the reason.
    house.set("person.ronny", "not_home")
    house.set("schedule.dum", "on", next_event=night_ends)
    house.now += timedelta(seconds=30)
    house.step()
    assert loznice.target_reason is TargetReason.ABSENT
    assert obyvak.target_reason is TargetReason.SCHEDULE_COMFORT
    logged = {d.params["room"]: d.params for d in ctrl.decisions if d.kind == "room_target"}
    assert logged["Loznice"]["reason"] == "absent"
    assert logged["Loznice"]["presence_entity"] == "person.ronny"
    assert logged["Obyvak"]["reason"] == "schedule_comfort"

    ctrl.rooms["id_obyvak"].set_target(22.0, house.now)
    house.run(30)
    assert obyvak.target_reason is TargetReason.OVERRIDE
    assert not [d for d in ctrl.decisions if d.kind == "room_target"]


def test_target_reason_preheat_and_no_presence() -> None:
    ctrl = controller(
        room("obyvak", **{c.CONF_SCHEDULE_ENTITY: "schedule.obyvak"}),
        **{c.CONF_HAS_BYPASS: True, c.CONF_PREHEAT_MAX: 1},
    )
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set("schedule.obyvak", "off", next_event=T0 + timedelta(minutes=30))
    house.step()
    obyvak = ctrl.rooms["id_obyvak"]
    assert obyvak.presence_source == "none"
    assert obyvak.target_reason is TargetReason.PREHEAT
    assert obyvak.target_until == T0 + timedelta(minutes=30)


def test_room_with_own_presence_uses_its_own_return() -> None:
    """Item 7 of the to-do: the household return is not used for a room of one person."""
    options = {
        c.CONF_PRESENCE_ENTITY: "person.ronny",
        c.CONF_EXPECTED_RETURN_ENTITY: "sensor.navrat_ronny",
    }
    ctrl = controller(
        room("loznice", **options),
        room("pracovna", **{c.CONF_PRESENCE_ENTITY: "person.zdenek"}),
        **{**PRESENCE, c.CONF_PREHEAT_MAX: 1},
    )
    house = House(ctrl, temperatures={"loznice": 19.0, "pracovna": 19.0})
    house.set(FAMILY, "not_home")
    house.set(LONG_AWAY, "off")
    house.set("person.ronny", "not_home")
    house.set("person.zdenek", "not_home")
    household_back = T0 + timedelta(minutes=20)
    ronny_back = T0 + timedelta(hours=3)
    house.set(RETURN, household_back.isoformat())
    house.set("sensor.navrat_ronny", ronny_back.isoformat())
    house.step()
    loznice, pracovna = ctrl.rooms["id_loznice"], ctrl.rooms["id_pracovna"]
    assert loznice.target_until == ronny_back
    assert not loznice.preheating
    assert loznice.preheat_planned == ronny_back - timedelta(hours=1)
    # Own presence without an own return: no preheating by the household return.
    assert pracovna.target_until is None
    assert not pracovna.preheating
    assert pracovna.preheat_planned is None


def test_changed_settings_do_not_log_the_schedule_again() -> None:
    """17. 10. 8:13: saving the rooms logged "comfort by schedule" six times (NFR-13)."""
    ctrl = controller(
        room("obyvak"), room("pracovna"), **{c.CONF_HOUSE_SCHEDULE_ENTITY: "schedule.dum"}
    )
    house = House(ctrl, temperatures={"obyvak": 21.0, "pracovna": 21.0})
    house.set("schedule.dum", "on", next_event=(T0 + timedelta(hours=8)).isoformat())
    house.run(60)
    assert ctrl.rooms["id_pracovna"].target_reason is TargetReason.SCHEDULE_COMFORT
    for _ in range(6):
        ctrl.reconfigure(ctrl.cfg, [r.cfg for r in ctrl.rooms.values()])
        house.step()
        assert not [d for d in ctrl.decisions if d.kind == "room_target"]
    assert ctrl.rooms["id_pracovna"].target_reason is TargetReason.SCHEDULE_COMFORT
