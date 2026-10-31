"""Unit tests of individual core parts."""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.aggregation import aggregate, combine
from custom_components.hydronic_heating.core.controller import HydronicController
from custom_components.hydronic_heating.core.heat_source import RoomDemand, arbitrate
from custom_components.hydronic_heating.core.model import (
    BoilerReason,
    EntityReading,
    Preset,
    RoomHvacMode,
    SystemMode,
    SystemState,
    ValveConfig,
    ValvePhysical,
    ValveReason,
)
from custom_components.hydronic_heating.core.safety import OutputTracker
from custom_components.hydronic_heating.core.valve import (
    ValveState,
    observed_open,
    pwm_on_time,
    pwm_open,
)

from .helpers import BOILER, T0, TZ, House, controller, room, system, valve

# --- Aggregation and validation (FR-ROOM-03, FR-ROOM-04) ----------------------


@pytest.mark.parametrize(
    ("method", "expected"),
    [("mean", 20.0), ("min", 19.0), ("max", 21.0), ("median", 20.0), ("priority", 21.0)],
)
def test_combine_methods(method: str, expected: float) -> None:
    assert combine([21.0, 19.0, 20.0], method) == expected


def test_aggregate_drops_invalid_sensors() -> None:
    readings = {
        "sensor.ok": EntityReading("20.5", 20.5, T0),
        "sensor.stale": EntityReading("19", 19.0, T0 - timedelta(hours=3)),
        "sensor.range": EntityReading("85", 85.0, T0),
        "sensor.down": EntityReading("unavailable"),
    }
    agg = aggregate(
        list(readings),
        readings,
        T0,
        method="mean",
        minimum=-20,
        maximum=50,
        stale_timeout_s=7200,
    )
    assert agg.value == 20.5
    assert agg.valid == ("sensor.ok",)
    assert agg.invalid == ("sensor.stale", "sensor.range", "sensor.down")


def test_stale_check_can_be_disabled() -> None:
    readings = {"sensor.a": EntityReading("20", 20.0, T0 - timedelta(days=2))}
    agg = aggregate(
        ["sensor.a"], readings, T0, method="mean", minimum=-20, maximum=50, stale_timeout_s=0
    )
    assert agg.value == 20.0


# --- Valves (FR-VAL-02, FR-VAL-03, FR-VAL-05) --------------------------------


@pytest.mark.parametrize(
    ("entity_id", "normally_open", "state", "expected"),
    [
        ("switch.no", True, "off", True),
        ("switch.no", True, "on", False),
        ("switch.nc", False, "off", False),
        ("switch.nc", False, "on", True),
        ("valve.v", True, "open", True),
        ("valve.v", True, "closed", False),
        ("switch.no", True, "unavailable", None),
    ],
)
def test_observed_open_no_nc(
    entity_id: str, normally_open: bool, state: str, expected: bool | None
) -> None:
    cfg = ValveConfig(entity_id, normally_open, 120, 120)
    assert observed_open(cfg, EntityReading(state)) is expected


def test_valve_physical_model() -> None:
    cfg = ValveConfig("switch.no", True, 120, 180)
    state = ValveState()
    assert state.physical(cfg, T0) is ValvePhysical.UNKNOWN
    state.observe(True, T0)
    assert state.physical(cfg, T0 + timedelta(seconds=119)) is ValvePhysical.OPENING
    assert state.physical(cfg, T0 + timedelta(seconds=120)) is ValvePhysical.OPEN
    state.observe(False, T0 + timedelta(seconds=200))
    assert state.physical(cfg, T0 + timedelta(seconds=300)) is ValvePhysical.CLOSING
    assert state.transition_ends_at(cfg) == T0 + timedelta(seconds=380)
    assert state.physical(cfg, T0 + timedelta(seconds=380)) is ValvePhysical.CLOSED


@pytest.mark.parametrize(
    ("demand", "expected"),
    [(0, 0), (10, 0), (50, 900), (90, 1800), (100, 1800)],
)
def test_pwm_on_time_rounding(demand: float, expected: float) -> None:
    """Shorter than the minimum state time rounds to fully closed or open."""
    assert pwm_on_time(demand, 1800, 300) == expected


def test_pwm_periods_are_aligned() -> None:
    start = T0.replace(minute=0)  # 11:00 UTC is a period boundary for 30 min
    assert pwm_open(start + timedelta(minutes=10), 50, 1800, 300)
    assert not pwm_open(start + timedelta(minutes=20), 50, 1800, 300)


def test_valve_commands_for_no_nc_and_valve_domain() -> None:
    rooms = [
        room("a", valves=[valve("switch.no")]),
        room("b", valves=[valve("switch.nc", normally_open=False)]),
        room("v", valves=[valve("valve.v")]),
        room("z"),  # cold, keeps the boiler running
    ]
    ctrl = controller(*rooms, **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"a": 25.0, "b": 25.0, "v": 25.0, "z": 15.0})
    house.set("switch.nc", "on")  # NC energized = open
    house.run(240)  # the warm rooms close their valves first (120 s), then the boiler
    # The boiler runs for z; the warm rooms close their valves.
    assert house.boiler_on
    assert house.state("switch.no") == "on"
    assert house.state("switch.nc") == "off"
    assert house.state("valve.v") == "closed"


def test_valves_without_current_while_the_boiler_is_idle() -> None:
    """No heat wanted and the boiler stands: no head draws current (FR-VAL-07)."""
    ctrl = controller(room("a"), room("b"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"a": 25.0, "b": 25.0})
    house.set("switch.hlavice_a", "on")
    house.set("switch.hlavice_b", "on")
    house.run(60)
    assert not house.boiler_on
    assert house.state("switch.hlavice_a") == "off"
    assert house.state("switch.hlavice_b") == "off"
    assert ctrl.valve_status["switch.hlavice_a"].reason is ValveReason.IDLE_POLICY


def test_unneeded_valves_close_before_the_boiler_starts() -> None:
    """Heat wanted in one room: the other room's valve closes first, then the boiler."""
    ctrl = controller(room("a"), room("b"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"a": 25.0, "b": 25.0})
    house.run(60)
    assert house.state("switch.hlavice_b") == "off"  # idle, open
    house.temp("a", 15.0)
    house.run(30)
    assert house.state("switch.hlavice_b") == "on"  # closing
    assert not house.boiler_on
    assert ctrl.boiler_status.reason is BoilerReason.PRE_CLOSE
    house.run(120)
    assert not house.boiler_on  # valve close time 120 s from the observed change
    house.run(30)
    assert house.boiler_on


# --- Arbitration (FR-ARB-01, FR-ARB-02) ---------------------------------------


def test_arbitration_threshold_and_hysteresis() -> None:
    cfg = system(**{c.CONF_MIN_ROOMS_CALLING: 2})
    rooms = [RoomDemand(35, 1, 0, False), RoomDemand(25, 1, 0, False)]
    assert arbitrate(rooms, cfg, prev_request=False).request  # 30 % >= 30
    rooms = [RoomDemand(25, 1, 0, False), RoomDemand(20, 1, 0, False)]
    assert not arbitrate(rooms, cfg, prev_request=False).request
    assert arbitrate(rooms, cfg, prev_request=True).request  # above 30 - 10
    rooms = [RoomDemand(15, 1, 0, False), RoomDemand(10, 1, 0, False)]
    assert not arbitrate(rooms, cfg, prev_request=True).request


def test_arbitration_area_weighting_and_calling_rooms() -> None:
    small_cold = [RoomDemand(100, 1, 2, False), RoomDemand(0, 1, 40, False)]
    weighted = system(**{c.CONF_AREA_WEIGHTING: True, c.CONF_MIN_ROOMS_CALLING: 2})
    result = arbitrate(small_cold, weighted, prev_request=False)
    assert result.weighted == pytest.approx(4.8, abs=0.1)
    assert not result.request
    # Default: one calling room is enough (combine any).
    assert arbitrate(small_cold, system(), prev_request=False).request
    both = system(**{c.CONF_COMBINE: "all"})
    assert arbitrate([RoomDemand(60, 1, 0, False), RoomDemand(0, 1, 0, False)], both, False).request
    assert not arbitrate(
        [
            RoomDemand(100, 1, 0, False),
            RoomDemand(0, 1, 0, False),
            RoomDemand(0, 1, 0, False),
            RoomDemand(0, 1, 0, False),
        ],
        both,
        False,
    ).request


def test_frost_always_requests() -> None:
    assert arbitrate([RoomDemand(0, 1, 0, True)], system(), False).request


# --- Modes, shadow, startup ---------------------------------------------------


def test_shadow_mode_sends_nothing_but_simulates() -> None:
    ctrl = controller(room("obyvak"), **{c.CONF_SHADOW_MODE: True})
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.run(5 * 60)
    assert house.commands == []
    assert not house.boiler_on
    assert ctrl.would_command()["boiler"] == "on"
    assert ctrl.would_command()["valves"] == {"switch.hlavice_obyvak": "open"}


def test_startup_waits_for_entities_then_grace() -> None:
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set(BOILER, "unavailable")
    house.run(90)
    assert ctrl.state is SystemState.STARTUP
    assert house.commands == []
    house.set(BOILER, "off")
    house.step()
    assert ctrl.ready
    assert ctrl.state is SystemState.AUTO


def test_startup_grace_then_fault_when_boiler_missing() -> None:
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set(BOILER, "unavailable")
    house.run(150)
    assert ctrl.ready
    assert ctrl.state is SystemState.FAULT_SAFE
    assert ctrl.fault_reason == "boiler_unavailable"


def test_fault_recovery_after_recovery_time() -> None:
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": 22.0})
    house.run(60)
    house.set(BOILER, "unavailable")
    house.run(30)
    assert ctrl.fault_safe
    house.set(BOILER, "off")
    house.run(270)
    assert ctrl.fault_safe
    house.run(60)
    assert not ctrl.fault_safe
    assert "fault_safe" not in ctrl.problems


def test_select_mode_manual_uses_first_duration() -> None:
    ctrl = controller(room("obyvak"), **{c.CONF_MANUAL_DURATIONS: [45, 90]})
    ctrl.set_mode(SystemMode.MANUAL, T0)
    assert ctrl.modes.manual_ends_at == T0 + timedelta(minutes=45)
    ctrl.set_mode(SystemMode.OFF, T0)
    assert ctrl.modes.mode is SystemMode.OFF
    assert ctrl.modes.manual_ends_at is None


def test_manual_extend_and_stop_policies() -> None:
    ctrl = controller(room("obyvak"), **{c.CONF_MANUAL_RESTART_POLICY: "extend"})
    ctrl.set_mode(SystemMode.AWAY, T0)
    ctrl.start_manual(30, T0)
    ctrl.start_manual(30, T0)
    assert ctrl.modes.manual_ends_at == T0 + timedelta(minutes=60)
    ctrl.stop(T0)
    assert ctrl.modes.mode is SystemMode.AWAY  # stop_policy resume

    off = controller(room("obyvak"), **{c.CONF_STOP_POLICY: "off"})
    off.start_manual(30, T0)
    off.stop(T0)
    assert off.modes.mode is SystemMode.OFF


def test_stop_without_min_on_switches_off_at_once() -> None:
    ctrl = controller(
        room("obyvak"), **{c.CONF_STOP_RESPECTS_MIN_ON: False, c.CONF_HAS_BYPASS: True}
    )
    house = House(ctrl, temperatures={"obyvak": 23.0})
    ctrl.start_manual(60, T0)
    house.run(60)
    assert house.boiler_on
    ctrl.stop(house.now)
    house.step()
    assert not house.boiler_on


def test_stop_respects_min_on_by_default() -> None:
    ctrl = controller(room("obyvak"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"obyvak": 23.0})
    ctrl.start_manual(60, T0)
    house.run(60)
    ctrl.stop(house.now)
    house.step()
    assert house.boiler_on
    house.run(5 * 60)
    assert not house.boiler_on


def test_off_mode_keeps_frost_only() -> None:
    ctrl = controller(room("a"), room("b"), **{c.CONF_HAS_BYPASS: True})
    ctrl.set_mode(SystemMode.OFF, T0)
    house = House(ctrl, temperatures={"a": 15.0, "b": 4.0})
    house.run(60)
    assert ctrl.state is SystemState.OFF
    assert ctrl.rooms["id_a"].demand == 0
    assert ctrl.rooms["id_b"].frost_active
    assert house.boiler_on


def test_away_mode_targets_away_temperature() -> None:
    ctrl = controller(room("obyvak"))
    ctrl.set_mode(SystemMode.AWAY, T0)
    house = House(ctrl, temperatures={"obyvak": 17.0})
    house.run(30)
    assert ctrl.rooms["id_obyvak"].target == 15.0
    assert ctrl.state is SystemState.AWAY


# --- Rooms ----------------------------------------------------------------------


def test_room_presence_absent_uses_absence_preset() -> None:
    """FR-SCH-02: absence means eco by default, away when configured."""
    ctrl = controller(room("obyvak", presence_entity="person.zdenek"))
    house = House(ctrl, temperatures={"obyvak": 20.0})
    house.set("person.zdenek", "not_home")
    house.run(30)
    obyvak = ctrl.rooms["id_obyvak"]
    assert obyvak.effective_preset is Preset.ECO
    assert obyvak.target == 19.0
    house.set("person.zdenek", "home")
    house.run(30)
    assert obyvak.target == 21.0

    ctrl = controller(
        room("obyvak", presence_entity="person.zdenek"), **{c.CONF_ABSENCE_PRESET: "away"}
    )
    house = House(ctrl, temperatures={"obyvak": 20.0})
    house.set("person.zdenek", "not_home")
    house.run(30)
    assert ctrl.rooms["id_obyvak"].effective_preset is Preset.AWAY
    assert ctrl.rooms["id_obyvak"].target == 15.0


def test_preset_change_is_override() -> None:
    ctrl = controller(room("obyvak"))
    obyvak = ctrl.rooms["id_obyvak"]
    obyvak.set_preset(Preset.ECO, T0)
    assert obyvak.hvac_mode is RoomHvacMode.HEAT
    house = House(ctrl, temperatures={"obyvak": 20.0})
    house.run(30)
    assert obyvak.target == 19.0
    obyvak.set_preset(Preset.NONE, house.now)
    assert obyvak.manual_target == 19.0


def test_room_off_closes_valve_but_keeps_frost() -> None:
    ctrl = controller(room("obyvak"), room("b"), **{c.CONF_HAS_BYPASS: True})
    ctrl.rooms["id_obyvak"].set_hvac_mode(RoomHvacMode.OFF, T0)
    house = House(ctrl, temperatures={"obyvak": 15.0, "b": 15.0})
    house.run(60)
    assert house.state("switch.hlavice_obyvak") == "on"  # closed while b heats
    house.temp("obyvak", 4.0)
    house.run(30)
    # A single sample is no frost yet (FR-FROST-03); the next one confirms it.
    assert not ctrl.rooms["id_obyvak"].frost_active
    house.run(30)
    assert house.state("switch.hlavice_obyvak") == "off"  # open for frost


def test_hysteresis_algorithm() -> None:
    ctrl = controller(room("obyvak", control_algorithm="hysteresis"))
    house = House(ctrl, temperatures={"obyvak": 20.8})
    house.run(30)
    obyvak = ctrl.rooms["id_obyvak"]
    assert obyvak.demand == 0
    house.temp("obyvak", 20.6)
    house.run(30)
    assert obyvak.demand == 100
    house.temp("obyvak", 21.1)
    house.run(30)
    assert obyvak.demand == 100
    house.temp("obyvak", 21.3)
    house.run(30)
    assert obyvak.demand == 0


def test_tpi_uses_damped_outdoor_temperature() -> None:
    ctrl = controller(room("obyvak"), outdoor_sensors=["sensor.venku"])
    house = House(ctrl, temperatures={"obyvak": 21.0})
    house.set("sensor.venku", "-9", -9.0)
    house.run(30)
    assert ctrl.rooms["id_obyvak"].demand == 30.0  # 0.01 * (21 - (-9)) * 100


def test_weather_fallback_for_outdoor() -> None:
    ctrl = controller(
        room("obyvak"), outdoor_sensors=["sensor.venku"], weather_entity="weather.domov"
    )
    house = House(ctrl, temperatures={"obyvak": 21.0})
    house.set("sensor.venku", "unavailable")
    house.set("weather.domov", "cloudy", temperature=3.5)
    house.run(30)
    assert ctrl.outdoor.current == 3.5
    assert ctrl.outdoor.source == "weather.domov"


def test_window_outdoor_condition() -> None:
    """A window does not block heating when it is warmer outside (FR-WIN-03)."""
    window = "binary_sensor.okno"
    ctrl = controller(room("obyvak", windows=[window]), outdoor_sensors=["sensor.venku"])
    house = House(ctrl, temperatures={"obyvak": 20.0})
    house.set("sensor.venku", "24", 24.0)
    house.event(window, "on")
    house.run(120)
    window_state = ctrl.rooms["id_obyvak"].window
    assert not window_state.effective_open
    assert not window_state.counts_for_global


def test_long_window_and_not_reached_problems() -> None:
    window = "binary_sensor.okno"
    ctrl = controller(room("a", windows=[window]), room("b"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"a": 20.0, "b": 15.0})
    house.ignore.add("switch.hlavice_b")  # b never warms up
    house.event(window, "on")
    house.run(61 * 60, every=60)
    assert "window_long_a" in ctrl.problems
    house.run(2 * 3600, every=60)
    assert "not_reached_b" in ctrl.problems


def test_valve_command_failure_is_reported() -> None:
    ctrl = controller(room("obyvak"), room("b"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"obyvak": 25.0, "b": 15.0})
    house.ignore.add("switch.hlavice_obyvak")
    house.run(120, every=5)
    assert "valve_command_switch.hlavice_obyvak" in ctrl.problems
    assert not ctrl.fault_safe


def test_min_open_prefers_valves_already_open() -> None:
    """Without a bypass the controller keeps an already open valve open."""
    ctrl = controller(room("a"), room("b"))
    house = House(ctrl, temperatures={"a": 19.0, "b": 25.0})
    house.run(10 * 60)
    assert house.boiler_on
    assert house.state("switch.hlavice_a") == "off"
    house.temp("a", 23.0)  # nobody needs heat, boiler keeps min_on
    house.run(30)
    assert house.state("switch.hlavice_a") == "off"
    assert house.state("switch.hlavice_b") == "on"


# --- Heat source types and heartbeat -------------------------------------------


def test_select_heat_source() -> None:
    ctrl = controller(
        room("obyvak"),
        **{
            c.CONF_HEAT_SOURCE_TYPE: "select",
            c.CONF_HEAT_SOURCE_SELECT_ENTITY: "select.kotel",
            c.CONF_HEAT_SOURCE_SELECT_ON: "Zapnuto",
            c.CONF_HEAT_SOURCE_SELECT_OFF: "Vypnuto",
            c.CONF_HAS_BYPASS: True,
        },
    )
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set("select.kotel", "Vypnuto")
    house.step()
    assert house.state("select.kotel") == "Zapnuto"


def test_actions_heat_source_with_keep_alive() -> None:
    ctrl = controller(
        room("obyvak"),
        **{
            c.CONF_HEAT_SOURCE_TYPE: "actions",
            c.CONF_HEAT_SOURCE_ON_ENTITY: "script.kotel_zap",
            c.CONF_HEAT_SOURCE_OFF_ENTITY: "script.kotel_vyp",
            c.CONF_HAS_BYPASS: True,
        },
    )
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set("script.kotel_zap", "off")
    house.set("script.kotel_vyp", "off")
    house.run(30)
    runs = [cmd.entity_id for cmd in house.commands if cmd.action == "run"]
    assert runs == ["script.kotel_zap"]
    house.run(300)
    runs = [cmd.entity_id for cmd in house.commands if cmd.action == "run"]
    assert runs == ["script.kotel_zap", "script.kotel_zap"]  # keep_alive 300 s


def test_heartbeat_toggles() -> None:
    ctrl = controller(room("obyvak"), heartbeat_entity="input_boolean.hb")
    house = House(ctrl, temperatures={"obyvak": 22.0})
    house.set("input_boolean.hb", "off")
    house.run(150)
    toggles = [cmd for cmd in house.commands if cmd.entity_id == "input_boolean.hb"]
    assert len(toggles) == 3  # at 30 s, 90 s and 150 s


def test_output_tracker_keep_alive_and_backoff() -> None:
    tracker = OutputTracker()
    kwargs = {"verifiable": True, "verify_timeout_s": 10, "retries": 0, "keep_alive_s": 300}
    assert not tracker.evaluate("x", T0, desired=True, observed=True, available=True, **kwargs)
    later = T0 + timedelta(seconds=300)
    assert tracker.evaluate("x", later, desired=True, observed=True, available=True, **kwargs)
    # Failure, then retry only after the back-off.
    t1 = later + timedelta(seconds=1)
    assert tracker.evaluate("x", t1, desired=False, observed=True, available=True, **kwargs)
    t2 = t1 + timedelta(seconds=11)
    assert not tracker.evaluate("x", t2, desired=False, observed=True, available=True, **kwargs)
    assert tracker.failed("x")
    t3 = t2 + timedelta(seconds=100)
    assert not tracker.evaluate("x", t3, desired=False, observed=True, available=True, **kwargs)
    t4 = t1 + timedelta(seconds=300)
    assert tracker.evaluate("x", t4, desired=False, observed=True, available=True, **kwargs)


# --- Statistics and persistence ------------------------------------------------


def test_duty_and_starts_today() -> None:
    ctrl = controller(room("obyvak"), **{c.CONF_HAS_BYPASS: True})
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.run(3600)
    seq = ctrl.sequencer
    assert seq.starts_today(house.now, TZ) == 1
    assert seq.duty_24h(house.now) == pytest.approx(3600 / 86400 * 100, abs=0.2)


def test_reconfigure_keeps_room_state() -> None:
    ctrl = controller(room("obyvak"))
    ctrl.rooms["id_obyvak"].set_target(23.0, T0)
    ctrl.reconfigure(system(), [room("obyvak", comfort_temp=22.0), room("kuchyn")])
    assert ctrl.rooms["id_obyvak"].manual_target == 23.0
    assert ctrl.rooms["id_obyvak"].cfg.comfort_temp == 22.0
    assert "id_kuchyn" in ctrl.rooms


def test_persistence_roundtrip() -> None:
    ctrl = controller(room("obyvak"), outdoor_sensors=["sensor.venku"])
    house = House(ctrl, temperatures={"obyvak": 16.0})
    house.set("sensor.venku", "2", 2.0)
    ctrl.rooms["id_obyvak"].set_preset(Preset.ECO, T0)
    house.run(600)
    data = ctrl.to_dict()
    restored = HydronicController(system(outdoor_sensors=["sensor.venku"]), [room("obyvak")])
    restored.restore(data, house.now)
    assert restored.outdoor.damped == ctrl.outdoor.damped
    assert restored.rooms["id_obyvak"].preset is Preset.ECO
    assert restored.sequencer.boiler_on
    assert restored.sequencer.starts == ctrl.sequencer.starts
    valve_state = restored.rooms["id_obyvak"].valves["switch.hlavice_obyvak"]
    assert (
        valve_state.changed_at == ctrl.rooms["id_obyvak"].valves["switch.hlavice_obyvak"].changed_at
    )


def test_short_sensor_outage_is_not_reported() -> None:
    """Sensors loading slowly after a restart do not raise a notification."""
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": None})
    house.run(4 * 60)
    assert ctrl.rooms["id_obyvak"].sensor_failure
    assert "sensor_failure_obyvak" not in ctrl.problems
    house.run(90)  # 5 minutes after the first step at T0 + 30 s
    assert "sensor_failure_obyvak" in ctrl.problems


def test_startup_decisions_do_not_hold_valves() -> None:
    """Sensors that load after the valves must not keep a valve closed for 5 minutes."""
    # The cold bedroom calls the boiler; a threshold above the fallback demand keeps
    # the living room on its PWM period.
    ctrl = controller(
        room("obyvak"),
        room("loznice"),
        **{c.CONF_HAS_BYPASS: True, c.CONF_BOILER_DEMAND_THRESHOLD: 50},
    )
    house = House(ctrl, temperatures={"obyvak": None, "loznice": 15.0})
    house.set(BOILER, "unavailable")
    # Fallback demand 30 % lands in the closed part of the PWM period.
    house.now = T0.replace(minute=20)
    house.step()
    assert not ctrl.ready
    assert ctrl.valve_desired["switch.hlavice_obyvak"] is False
    house.set(BOILER, "off")
    house.temp("obyvak", 19.0)
    house.step()
    assert ctrl.ready
    assert ctrl.rooms["id_obyvak"].demand == 100
    assert house.state("switch.hlavice_obyvak") == "off"  # open at once


def test_start_is_cancelled_when_the_demand_vanishes_while_valves_close() -> None:
    """15. 10. 17:29: a sensor failed for 16 s, the demand vanished during pre_close."""
    rooms = [room(slug) for slug in ("a", "b", "c", "d")]
    ctrl = controller(*rooms, **{c.CONF_HAS_BYPASS: True, c.CONF_MIN_ROOMS_CALLING: 2})
    house = House(ctrl, temperatures={slug: 25.0 for slug in "abcd"})
    house.run(60)
    house.temp("a", 15.0)
    house.temp("b", 15.0)
    house.run(30)
    assert ctrl.boiler_status.reason is BoilerReason.PRE_CLOSE
    # b is fine again: 25 % of 30 %, one room calls. Before the boiler runs the
    # hysteresis (20 %) does not apply, the start is cancelled.
    house.temp("b", 25.0)
    house.step()
    assert ctrl.boiler_status.reason is BoilerReason.IDLE
    assert [d.kind for d in ctrl.decisions] == ["start_cancelled"]
    assert ctrl.decisions[0].params["waited"] == "pre_close"
    house.run(300)
    assert not house.boiler_on
    assert ctrl.sequencer.starts_last_hour(house.now) == 0


def test_hysteresis_keeps_a_running_boiler_on() -> None:
    rooms = [room(slug) for slug in ("a", "b", "c", "d")]
    ctrl = controller(*rooms, **{c.CONF_HAS_BYPASS: True, c.CONF_MIN_ROOMS_CALLING: 2})
    house = House(ctrl, temperatures={"a": 15.0, "b": 15.0, "c": 25.0, "d": 25.0})
    house.run(5 * 60)
    assert house.boiler_on
    house.temp("b", 25.0)  # 25 %: above the stop threshold of 20 %
    house.run(10 * 60)
    assert house.boiler_on


def test_flickering_sensor_does_not_cancel_the_start_again_and_again() -> None:
    """31. 10. 7:30: the kitchen sensor flickered by 1/16 K, its demand around 50 %.

    Two rooms must call. The kitchen started and stopped calling every minute, each
    start in pre_close was cancelled and the valve heads switched every minute. A
    calling room now stops only below the threshold less the hysteresis (40 %).
    """
    rooms = [room(slug) for slug in ("obyvak", "kuchyn", "loznice", "pracovna")]
    ctrl = controller(*rooms, **{c.CONF_HAS_BYPASS: True, c.CONF_MIN_ROOMS_CALLING: 2})
    house = House(
        ctrl, temperatures={"obyvak": 20.0625, "kuchyn": 20.125, "loznice": 25, "pracovna": 25}
    )
    kinds: list[str] = []
    head_actions: list[str] = []
    for minute in range(15):
        house.temp("kuchyn", 20.125 if minute % 2 == 0 else 20.1875)  # 52.5 % / 48.75 %
        for _ in range(2):
            house.now += timedelta(seconds=30)
            plan = house.step()
            kinds += [d.kind for d in ctrl.decisions]
            head_actions += [
                cmd.action for cmd in plan.commands if cmd.entity_id == "switch.hlavice_loznice"
            ]
    assert ctrl.rooms["id_kuchyn"].calls_boiler
    assert "start_cancelled" not in kinds
    assert house.boiler_on
    assert set(head_actions) == {"turn_on"}  # closed before the start, then keep-alive

    house.temp("kuchyn", 20.4)  # 36 %: below 50 % less 10 %
    house.run(60)
    assert not ctrl.rooms["id_kuchyn"].calls_boiler
    assert ctrl.arbitration.calling == 1


def test_short_sensor_drop_out_keeps_the_last_value() -> None:
    """15. 10. 17:29: the Thread sensor was away for 16 s, the backup reads 0,9 K less."""
    sensors = [c.CONF_SENSORS, ["sensor.alpstuga", "sensor.loxone"]]
    ctrl = controller(
        room("loznice", **{sensors[0]: sensors[1], c.CONF_AGGREGATION: "priority"}),
        **{c.CONF_HAS_BYPASS: True},
    )
    house = House(ctrl)
    house.set("sensor.alpstuga", "21.12", 21.12)
    house.set("sensor.loxone", "20.25", 20.25)
    house.run(60)
    bedroom = ctrl.rooms["id_loznice"]
    assert bedroom.temperature == 21.12
    house.set("sensor.alpstuga", "unavailable")
    house.run(30)
    assert bedroom.temperature == 21.12
    assert bedroom.held_sources == ("sensor.alpstuga",)
    assert bedroom.valid_sources == ("sensor.alpstuga", "sensor.loxone")
    assert bedroom.invalid_sources == ()
    # Back within the grace: nothing happened.
    house.set("sensor.alpstuga", "21.1", 21.1)
    house.run(30)
    assert (bedroom.temperature, bedroom.held_sources) == (21.1, ())
    # A long drop-out: after 5 min the backup sensor takes over.
    house.set("sensor.alpstuga", "unavailable")
    house.run(6 * 60)
    assert bedroom.temperature == 20.25
    assert bedroom.invalid_sources == ("sensor.alpstuga",)


def test_held_value_counts_in_the_mean_and_stops_at_the_grace() -> None:
    ctrl = controller(
        room("obyvak", **{c.CONF_SENSORS: ["sensor.a", "sensor.b"], c.CONF_SENSOR_GRACE: 2}),
    )
    house = House(ctrl)
    house.set("sensor.a", "20.0", 20.0)
    house.set("sensor.b", "22.0", 22.0)
    house.run(60)
    living = ctrl.rooms["id_obyvak"]
    house.set("sensor.b", "unknown")
    house.run(60)
    assert living.temperature == 21.0  # mean with the held 22 °C
    house.run(90)
    assert living.temperature == 20.0
