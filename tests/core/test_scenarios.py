"""Mandatory scenarios from PRD chapter 13 (and the ones added in PRD 1.1)."""

from __future__ import annotations

from datetime import timedelta
import itertools

from custom_components.hydronic_heating import const as c
from custom_components.hydronic_heating.core.controller import HydronicController
from custom_components.hydronic_heating.core.model import (
    RoomHvacMode,
    SystemMode,
    SystemState,
)

from .helpers import BOILER, T0, House, controller, room, system


def test_heating_starts_after_valve_travel_time() -> None:
    """Valves open first, the boiler follows after the travel time (11.3)."""
    house = House(controller(room("obyvak")), temperatures={"obyvak": 19.0})
    house.step()
    assert not house.boiler_on
    house.run(90)
    assert not house.boiler_on
    house.run(30)
    assert house.boiler_on
    assert house.ctrl.state is SystemState.AUTO


def test_1_closed_valves_never_start_boiler() -> None:
    """Scenario 1: with all valves closed the boiler never starts."""
    house = House(controller(room("obyvak")), temperatures={"obyvak": 19.0})
    house.set("switch.hlavice_obyvak", "on")  # NO head energized = closed
    house.ignore.add("switch.hlavice_obyvak")
    for _ in range(120):
        house.run(30)
        assert not house.boiler_on
    assert house.ctrl.fault_safe
    assert house.ctrl.fault_reason == "no_flow"


def test_2_oscillating_demand_respects_anti_cycling() -> None:
    """Scenario 2: min run time, min pause and starts per hour are never violated."""
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": 19.0})
    history: list[tuple] = []
    for i in range(180):  # 3 hours, temperature flips every 2 minutes
        house.temp("obyvak", 19.0 if (i // 4) % 2 == 0 else 23.0)
        house.run(30)
        history.append((house.now, house.boiler_on))

    changes = [
        (t, on) for (t, on), (_, prev) in zip(history[1:], history, strict=False) if on != prev
    ]
    assert changes, "the boiler should cycle at least once"
    for (t1, on1), (t2, _) in itertools.pairwise(changes):
        duration = (t2 - t1).total_seconds()
        if on1:
            assert duration >= 5 * 60, f"run of {duration} s"
        else:
            assert duration >= 5 * 60, f"pause of {duration} s"
    starts = [t for t, on in changes if on]
    for t in starts:
        assert sum(1 for s in starts if t <= s < t + timedelta(hours=1)) <= 4


def test_3_window_closes_valve_and_restores() -> None:
    """Scenario 3: open window closes the valve after the delay, closing restores it."""
    window = "binary_sensor.okno_obyvak"
    ctrl = controller(
        room("obyvak", windows=[window]),
        **{c.CONF_HAS_BYPASS: True, c.CONF_BOILER_OVERRUN: 0},
    )
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set(window, "off")
    house.run(300)
    assert house.state("switch.hlavice_obyvak") == "off"  # NO head off = open

    house.event(window, "on")
    house.run(30)
    assert house.state("switch.hlavice_obyvak") == "off"
    house.run(30)  # window_open_delay 60 s
    assert house.state("switch.hlavice_obyvak") == "on"
    assert ctrl.rooms["id_obyvak"].demand == 0

    house.event(window, "off")
    assert house.state("switch.hlavice_obyvak") == "on"
    house.run(30)  # window_close_delay 30 s, no wait for the minimum valve state time
    assert house.state("switch.hlavice_obyvak") == "off"


def test_window_without_bypass_keeps_flow_while_boiler_runs() -> None:
    """Without a bypass the last open valve stays open until the boiler and overrun end."""
    window = "binary_sensor.okno_obyvak"
    ctrl = controller(room("obyvak", windows=[window]))
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.set(window, "off")
    house.run(150)
    assert house.boiler_on  # since T0 + 120 s

    house.event(window, "on")
    house.run(60)
    assert ctrl.rooms["id_obyvak"].window.effective_open
    assert house.state("switch.hlavice_obyvak") == "off"  # kept open for flow
    on_since = ctrl.sequencer.on_since
    while house.boiler_on:
        assert house.state("switch.hlavice_obyvak") == "off"  # kept open for flow
        house.run(30)
    assert (house.now - on_since).total_seconds() >= 5 * 60  # min_on respected
    house.run(150)
    assert house.state("switch.hlavice_obyvak") == "off"  # overrun 180 s
    house.run(30)
    assert house.state("switch.hlavice_obyvak") == "on"


def test_4_two_windows_stop_the_boiler() -> None:
    """Scenario 4: two rooms with an open window stop the boiler (global threshold)."""
    rooms = [room(s, windows=[f"binary_sensor.okno_{s}"]) for s in ("a", "b", "c")]
    house = House(controller(*rooms), temperatures={"a": 19.0, "b": 19.0, "c": 19.0})
    for s in ("a", "b", "c"):
        house.set(f"binary_sensor.okno_{s}", "off")
    house.run(10 * 60)
    assert house.boiler_on

    house.set("binary_sensor.okno_a", "on")
    house.event("binary_sensor.okno_b", "on")
    house.run(90)
    assert house.boiler_on  # global_window_delay 120 s
    house.run(60)
    assert house.ctrl.window_block
    assert not house.boiler_on
    assert "window_block" in house.ctrl.blocked_by

    house.set("binary_sensor.okno_a", "off")
    house.run(30)
    assert not house.ctrl.window_block


def test_5_manual_survives_restart() -> None:
    """Scenario 5: manual 60 min, restart at 30 min, ends at 60 min."""
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": 22.0})
    ctrl.start_manual(60, house.now)
    house.run(30 * 60)
    assert ctrl.modes.mode is SystemMode.MANUAL
    assert house.boiler_on

    restarted = HydronicController(system(), [room("obyvak")])
    restarted.restore(ctrl.to_dict(), house.now)
    house.ctrl = restarted
    house.run(29 * 60)
    assert restarted.modes.mode is SystemMode.MANUAL
    assert restarted.modes.remaining_s(house.now) == 60
    house.run(60)
    assert restarted.modes.mode is SystemMode.AUTO
    assert restarted.modes.last_transition["reason"] == "expired"


def test_6_sensor_failure_falls_back() -> None:
    """Scenario 6: sensor outage uses the last value, then the fallback, and reports."""
    ctrl = controller(room("obyvak", sensor_fallback="fixed_demand", fallback_hold=60))
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.run(60)
    obyvak = ctrl.rooms["id_obyvak"]
    assert obyvak.demand == 100

    house.temp("obyvak", None)
    house.run(30 * 60)
    assert obyvak.sensor_failure
    assert obyvak.temperature == 19.0  # last known within fallback_hold
    assert "sensor_failure_obyvak" in ctrl.problems
    assert ctrl.problems["sensor_failure_obyvak"].repair

    house.run(31 * 60)
    assert obyvak.temperature is None
    assert obyvak.demand == 30  # fallback_demand

    house.temp("obyvak", 20.5)
    house.run(30)
    assert not obyvak.sensor_failure
    assert "sensor_failure_obyvak" not in ctrl.problems


def test_7_boiler_ignoring_commands_goes_fault_safe() -> None:
    """Scenario 7: retries, then fault_safe with a repeated "off"."""
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.ignore.add(BOILER)
    house.run(120, every=5)
    house.run(60, every=5)
    turn_on = [cmd for cmd in house.commands if cmd.entity_id == BOILER and cmd.action == "turn_on"]
    assert len(turn_on) == 3  # first command + command_retries (2)
    assert ctrl.fault_safe
    assert ctrl.fault_reason == "boiler_command"
    assert ctrl.state is SystemState.FAULT_SAFE
    assert ctrl.problems["fault_safe"].repair
    house.commands.clear()
    house.run(60, every=30)
    assert [cmd.action for cmd in house.commands if cmd.entity_id == BOILER] == [
        "turn_off",
        "turn_off",
    ]
    # Valves go to the idle position: NO heads de-energized.
    assert house.state("switch.hlavice_obyvak") == "off"


def test_8_summer_exercise_and_zero_power() -> None:
    """Scenario 8: 30 days of summer, weekly exercise, otherwise de-energized."""
    ctrl = controller(room("obyvak"))
    ctrl.set_mode(SystemMode.SUMMER, T0)
    house = House(ctrl, temperatures={"obyvak": 23.0})
    energized_s = 0
    episodes = 0
    previous = "off"
    step = 120
    for _ in range(30 * 24 * 3600 // step):
        house.run(step, every=step)
        state = house.state("switch.hlavice_obyvak")
        if state == "on":
            energized_s += step
            if previous == "off":
                episodes += 1
        previous = state
        assert not house.boiler_on
    assert episodes == 4
    assert 4 * 600 <= energized_s <= 4 * (600 + step)


def test_9_heating_limit_with_hysteresis() -> None:
    """Scenario 9: summer after the delay above the limit, winter below limit - hysteresis."""
    ctrl = controller(room("obyvak"), outdoor_sensors=["sensor.venku"])
    house = House(ctrl, temperatures={"obyvak": 22.0})
    house.set("sensor.venku", "20", 20.0)
    house.run(11 * 3600 + 50 * 60, every=600)
    assert not ctrl.outdoor.summer
    house.run(20 * 60, every=600)
    assert ctrl.outdoor.summer
    assert ctrl.state is SystemState.SUMMER

    house.run(3600, every=600)
    house.set("sensor.venku", "5", 5.0)
    house.run(15 * 3600, every=600)
    assert ctrl.outdoor.summer  # damped still above 13 °C
    house.run(3600, every=600)
    assert not ctrl.outdoor.summer
    assert ctrl.state is SystemState.AUTO


def test_10_frost_overrides_open_window_even_in_summer() -> None:
    """Scenario 10: frost opens the valve and requests the boiler despite window and summer."""
    window = "binary_sensor.okno_obyvak"
    ctrl = controller(room("obyvak", windows=[window]))
    ctrl.set_mode(SystemMode.SUMMER, T0)
    house = House(ctrl, temperatures={"obyvak": 4.0})
    house.set(window, "on")
    house.run(300)
    obyvak = ctrl.rooms["id_obyvak"]
    assert obyvak.frost_active
    assert obyvak.window.effective_open
    assert house.state("switch.hlavice_obyvak") == "off"  # open
    assert house.boiler_on

    house.temp("obyvak", 7.5)  # above frost_temp + 2 K
    house.run(10 * 60)
    assert not obyvak.frost_active
    assert not house.boiler_on


def test_11_waiting_for_min_off_is_not_no_flow() -> None:
    """Scenario 11: PRE_OPEN waiting for anti-cycling does not raise no_flow."""
    ctrl = HydronicController(system(), [room("obyvak")])
    ctrl.restore({"boiler": {"off_since": T0.isoformat(), "boiler_on": False}}, T0)
    house = House(ctrl, temperatures={"obyvak": 19.0})
    seen_anti_cycling = False
    for _ in range(9):
        house.run(30)
        seen_anti_cycling |= "anti_cycling" in ctrl.blocked_by
        assert not ctrl.fault_safe
        assert not house.boiler_on
    assert seen_anti_cycling
    house.run(30)  # 300 s after the last stop
    assert house.boiler_on


def test_12_restart_keeps_min_off() -> None:
    """Scenario 12: a restart one minute after stop does not start the boiler early."""
    options = {c.CONF_HAS_BYPASS: True}
    ctrl = controller(room("obyvak"), **options)
    house = House(ctrl, temperatures={"obyvak": 19.0})
    house.run(10 * 60)
    assert house.boiler_on
    house.temp("obyvak", 23.0)
    house.run(60)
    assert not house.boiler_on
    stopped_at = ctrl.sequencer.off_since
    house.run(60)

    restarted = HydronicController(system(**options), [room("obyvak")])
    restarted.restore(ctrl.to_dict(), house.now)
    house.ctrl = restarted
    house.temp("obyvak", 19.0)
    while house.now + timedelta(seconds=30) < stopped_at + timedelta(minutes=5):
        house.run(30)
        assert not house.boiler_on
    house.run(30)
    assert house.boiler_on


def test_13_manual_ignores_global_window_block() -> None:
    """Scenario 13: in manual mode the boiler keeps running, window rooms stay closed."""
    rooms = [room(s, windows=[f"binary_sensor.okno_{s}"]) for s in ("a", "b", "c")]
    ctrl = controller(*rooms)
    house = House(ctrl, temperatures={"a": 22.0, "b": 22.0, "c": 22.0})
    for s in ("a", "b", "c"):
        house.set(f"binary_sensor.okno_{s}", "off")
    ctrl.start_manual(60, house.now)
    house.run(5 * 60)
    assert house.boiler_on

    house.set("binary_sensor.okno_a", "on")
    house.set("binary_sensor.okno_b", "on")
    house.run(5 * 60)
    assert ctrl.window_block
    assert house.boiler_on
    assert house.state("switch.hlavice_a") == "on"  # closed
    assert house.state("switch.hlavice_b") == "on"
    assert house.state("switch.hlavice_c") == "off"  # open


def test_14_setpoint_change_is_permanent_override() -> None:
    """Scenario 14: a setpoint change in auto switches to heat and ignores the schedule."""
    ctrl = controller(room("obyvak", schedule_entity="schedule.obyvak"))
    house = House(ctrl, temperatures={"obyvak": 20.0})
    house.set("schedule.obyvak", "on")
    house.run(30)
    obyvak = ctrl.rooms["id_obyvak"]
    assert obyvak.target == 21.0
    house.set("schedule.obyvak", "off")
    house.run(30)
    assert obyvak.target == 19.0

    obyvak.set_target(23.0, house.now)
    house.run(30)
    assert obyvak.hvac_mode is RoomHvacMode.HEAT
    assert obyvak.override_active
    assert obyvak.target == 23.0
    house.set("schedule.obyvak", "on")
    house.run(30)
    assert obyvak.target == 23.0

    obyvak.set_hvac_mode(RoomHvacMode.AUTO, house.now)
    house.run(30)
    assert not obyvak.override_active
    assert obyvak.target == 21.0


def test_15_valve_resync_after_unavailable() -> None:
    """Scenario 15: a valve that comes back in another state is corrected (FR-VAL-09)."""
    ctrl = controller(room("obyvak"))
    house = House(ctrl, temperatures={"obyvak": 23.0})
    house.run(10 * 60)
    assert house.state("switch.hlavice_obyvak") == "on"  # warm room, valve closed

    house.set("switch.hlavice_obyvak", "unavailable")
    house.run(30)
    house.set("switch.hlavice_obyvak", "off")  # Miniserver restarted
    house.commands.clear()
    house.step()
    assert house.state("switch.hlavice_obyvak") == "on"
    assert house.commands[0].entity_id == "switch.hlavice_obyvak"


def test_bypass_starts_without_open_valves() -> None:
    """With a bypass the boiler may start before the valves are open (FR-BOI-03)."""
    house = House(
        controller(room("obyvak"), **{c.CONF_HAS_BYPASS: True}), temperatures={"obyvak": 19.0}
    )
    house.step()
    assert house.boiler_on
