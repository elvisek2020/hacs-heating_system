"""Why the boiler is in its state: sensors, logbook and reverted outputs (FR-SAFE-07)."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Event, HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.hydronic_heating import logbook
from custom_components.hydronic_heating.const import (
    CONF_BOILER_MIN_ON,
    CONF_SHADOW_MODE,
    DOMAIN,
    EVENT_DECISION,
)
from custom_components.hydronic_heating.core.model import BoilerReason, BoilerStatus, Decision
from custom_components.hydronic_heating.explain import decision_text

from .test_runtime import CELSIUS, _settle, _setup, _wait

LIVE = {CONF_SHADOW_MODE: False, CONF_BOILER_MIN_ON: 10}


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    await _settle(hass)


def _reason(hass: HomeAssistant) -> Any:
    return hass.states.get("sensor.hh_boiler_reason")


async def test_manual_then_stop_shows_min_on_hold(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The case from the to-do list: manual 30 min, stop after 16 s, warm rooms.

    The heat of the minimum run and of the overrun after manual heating goes to
    all rooms, although no room wants heat (FR-MAN-06, FR-BOI-09).
    """
    freezer.move_to("2026-01-15 11:00:00+00:00")
    entry = await _setup(hass, **LIVE)
    hass.states.async_set("sensor.obyvak", "25.0", CELSIUS)
    hass.states.async_set("sensor.loznice", "25.0", CELSIUS)
    # Without stored history the boiler is assumed to have just stopped.
    await _wait(hass, freezer, 300)
    assert _reason(hass).state == "idle"
    assert hass.states.get("sensor.hh_boiler_hold_ends_at").state == "unknown"

    events = async_capture_events(hass, EVENT_DECISION)
    await _press(hass, "button.hh_manual_30")
    started = dt_util.utcnow()
    assert hass.states.get("input_boolean.kotel").state == "on"
    assert _reason(hass).state == "firing_manual"
    assert [e.data["kind"] for e in events] == ["boiler_on"]
    assert events[0].data["message"].startswith("Boiler on: manual heating to all rooms until ")
    assert events[0].data["entity_id"] == "sensor.hh_boiler_reason"

    freezer.tick(timedelta(seconds=16))
    await _press(hass, "button.hh_stop")
    assert hass.states.get("select.hh_system_mode").state == "auto"
    assert hass.states.get("input_boolean.kotel").state == "on"
    reason = _reason(hass)
    assert reason.state == "min_on_hold"
    ends = started + timedelta(minutes=10)
    assert reason.attributes["until"] == ends.isoformat()
    assert reason.attributes["remaining_s"] == 584
    assert reason.attributes["rule"] == "boiler_min_on = 10 min"
    local = dt_util.as_local(ends)
    clock = f"{local.hour}:{local:%M:%S}"  # no leading zero
    assert clock in reason.attributes["detail"]
    hold = hass.states.get("sensor.hh_boiler_hold_ends_at")
    assert dt_util.parse_datetime(hold.state) == ends
    # One extra step is scheduled for the end, the boiler does not wait for the tick.
    assert entry.runtime_data._hold_at == ends
    assert hass.states.get("climate.hh_system").attributes["min_on_until"] == ends.isoformat()
    hold_event = events[-1].data
    assert hold_event["kind"] == "hold"
    assert hold_event["reason"] == "min_on_hold"
    assert hold_event["until"] == ends.isoformat()
    assert hold_event["message"] == (
        f"Stop: the boiler runs until {clock} because of its minimum run time of 10 min, "
        "the heat goes to all rooms."
    )
    for room in ("obyvak", "loznice"):
        valve = hass.states.get(f"sensor.hh_{room}_valve_state")
        assert valve.attributes["reason"] == "min_run"
        assert valve.attributes["until"] == ends.isoformat()
    assert reason.attributes["detail"].endswith("the heat goes to all rooms.")

    await _wait(hass, freezer, 600)
    assert hass.states.get("input_boolean.kotel").state == "off"
    assert _reason(hass).state == "overrun"
    off = [e.data for e in events if e.data["kind"] == "boiler_off"]
    assert len(off) == 1
    assert off[0]["cause"] == "min_on_done"
    assert off[0]["message"].startswith(
        "Boiler off: the minimum run time is over and nobody needs heat. The pump runs on until "
    )
    assert off[0]["message"].endswith(" to all rooms.")
    assert _reason(hass).attributes["detail"].endswith(" to all rooms.")
    for room in ("obyvak", "loznice"):
        valve = hass.states.get(f"sensor.hh_{room}_valve_state")
        assert valve.attributes["reason"] == "overrun"

    await _wait(hass, freezer, 180)
    assert _reason(hass).state == "idle"
    assert hass.states.get("sensor.hh_boiler_hold_ends_at").state == "unknown"


async def test_demand_during_min_pause_waits_and_then_starts(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Without stored history the boiler is assumed to have just stopped (FR-BOI-08)."""
    freezer.move_to("2026-01-15 11:00:00+00:00")
    events = async_capture_events(hass, EVENT_DECISION)
    await _setup(hass, **LIVE)
    reason = _reason(hass)
    assert reason.state == "min_off_hold"
    next_start = hass.states.get("climate.hh_system").attributes["next_allowed_start"]
    assert reason.attributes["until"] == next_start
    hold = hass.states.get("sensor.hh_boiler_hold_ends_at")
    assert dt_util.parse_datetime(hold.state) == dt_util.parse_datetime(next_start)

    await _wait(hass, freezer, 300)
    assert hass.states.get("input_boolean.kotel").state == "on"
    on = [e.data for e in events if e.data["kind"] == "boiler_on"]
    assert len(on) == 1
    assert on[0]["message"].startswith("Boiler on: room demand (")


async def test_boiler_switched_by_hand_is_reverted_and_logged(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="custom_components.hydronic_heating")
    freezer.move_to("2026-01-15 11:00:00+00:00")
    await _setup(hass, **LIVE)
    await _wait(hass, freezer, 300)
    assert hass.states.get("input_boolean.kotel").state == "on"
    assert _reason(hass).state == "firing_demand"

    events = async_capture_events(hass, EVENT_DECISION)
    await hass.services.async_call(
        "input_boolean", "turn_off", {"entity_id": "input_boolean.kotel"}, blocking=True
    )
    await _settle(hass)
    assert hass.states.get("input_boolean.kotel").state == "on"
    reverted = [e.data for e in events if e.data["kind"] == "reverted"]
    assert len(reverted) == 1
    assert reverted[0]["entity_id"] == "input_boolean.kotel"
    assert reverted[0]["message"].startswith(
        "Switched outside the controller to off, the integration set it back to on. "
        "The boiler heats on room demand"
    )
    assert (
        "Output kotel (input_boolean.kotel) was switched outside the controller to off, "
        "the integration set it back to on." in caplog.text
    )
    override = hass.states.get("climate.hh_system").attributes["last_reverted_override"]
    assert override["entity_id"] == "input_boolean.kotel"
    assert (override["found"], override["set_to"]) == (False, True)


async def test_mode_change_prefixes_only_the_time_rule(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The cause of an on/off decision already says it; a time rule names the action."""
    freezer.move_to("2026-01-15 11:00:00+00:00")
    await _setup(hass, **LIVE)
    await _wait(hass, freezer, 300)
    assert hass.states.get("input_boolean.kotel").state == "on"
    events = async_capture_events(hass, EVENT_DECISION)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.hh_system_mode", "option": "off"},
        blocking=True,
    )
    await _settle(hass)
    assert [e.data["kind"] for e in events] == ["hold"]
    assert events[0].data["message"].startswith("Mode off: the boiler runs until ")
    await _wait(hass, freezer, 600)
    off = [e.data for e in events if e.data["kind"] == "boiler_off"]
    assert off[0]["message"].startswith("Boiler off: the minimum run time is over")


async def test_shadow_mode_decisions_are_marked(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-01-15 11:00:00+00:00")
    await _setup(hass)
    events = async_capture_events(hass, EVENT_DECISION)
    await _wait(hass, freezer, 300)
    on = [e.data for e in events if e.data["kind"] == "boiler_on"]
    assert on
    assert on[0]["message"].startswith("[Shadow] Boiler on: room demand")
    assert hass.states.get("input_boolean.kotel").state == "off"


async def test_czech_texts(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to("2026-01-15 11:00:00+00:00")
    hass.config.language = "cs"
    await _setup(hass, **LIVE)
    events = async_capture_events(hass, EVENT_DECISION)
    await _wait(hass, freezer, 300)
    on = [e.data for e in events if e.data["kind"] == "boiler_on"]
    assert on[0]["message"].startswith("Kotel zapnut: požadavek místností (celkem ")
    assert _reason(hass).attributes["detail"].startswith("Kotel topí na požadavek místností")


async def test_airing_is_logged_at_the_room(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A fast drop pauses the room and says so in the logbook (FR-WIN-06)."""
    freezer.move_to("2026-01-15 11:00:00+00:00")
    hass.config.language = "cs"
    await _setup(hass)
    await _wait(hass, freezer, 120)
    events = async_capture_events(hass, EVENT_DECISION)
    for step in range(8):  # 19.0 -> 17.0 °C in 4 min
        hass.states.async_set("sensor.obyvak", str(18.75 - step * 0.25), CELSIUS)
        await _wait(hass, freezer, 30)
    airing = [e.data for e in events if e.data["kind"] == "ventilation"]
    assert airing[0]["entity_id"] == "climate.hh_obyvak"
    assert airing[0]["message"].startswith(
        "[Shadow] Obývák: rychlý pokles teploty o 1 °C, asi se větrá – topení pozastaveno do "
    )
    living = hass.states.get("climate.hh_obyvak").attributes
    assert living["window_state"] == "open_detected"
    assert living["target_reason"] == "ventilation"
    assert living["target_detail"].startswith("Větrá se (rychlý pokles teploty)")
    assert hass.states.get("binary_sensor.hh_obyvak_window").state == "on"


async def test_valve_check_sentences(hass: HomeAssistant) -> None:
    """Logbook sentences of the pipe check (FR-SAFE-09)."""
    hass.config.language = "cs"
    status = BoilerStatus(BoilerReason.FIRING_DEMAND)
    params = {"room": "Ložnice", "rise": 0.8, "minutes": 10.0}
    texts = [
        decision_text(hass, Decision("valve_check", status, {**params, "result": result}))
        for result in ("not_opening", "not_closing", "ok")
    ]
    assert texts == [
        "Ložnice: ventil asi neotvírá – trubka se za 10 min ohřála jen o 0,8 °C.",
        "Ložnice: ventil asi nezavírá – trubka se ohřála o 0,8 °C.",
        "Ložnice: ventil zase funguje, kontrola podle trubky prošla.",
    ]


async def test_cancelled_start_sentence(hass: HomeAssistant) -> None:
    hass.config.language = "cs"
    status = BoilerStatus(BoilerReason.IDLE)
    decision = Decision("start_cancelled", status, {"waited": "pre_close"})
    assert decision_text(hass, decision) == (
        "Start zrušen: požadavek během zavírání ventilů zmizel."
    )


async def test_valve_state_explains_the_position(hass: HomeAssistant) -> None:
    await _setup(hass)
    attrs = hass.states.get("sensor.hh_obyvak_valve_state").attributes
    assert attrs["reason"] in ("pwm", "heat_call", "min_state_hold", "startup")
    assert "until" in attrs


async def test_logbook_describes_the_event(hass: HomeAssistant) -> None:
    described: dict[str, Any] = {}

    def register(domain: str, event_type: str, describe: Any) -> None:
        described[event_type] = (domain, describe)

    logbook.async_describe_events(hass, register)
    domain, describe = described[EVENT_DECISION]
    assert domain == DOMAIN
    entry = describe(
        Event(
            EVENT_DECISION,
            {
                "name": "Topení",
                "message": "Kotel zapnut: manuální topení do 01:15:12.",
                "entity_id": "sensor.hh_boiler_reason",
            },
        )
    )
    assert entry == {
        "name": "Topení",
        "message": "Kotel zapnut: manuální topení do 01:15:12.",
        "entity_id": "sensor.hh_boiler_reason",
    }
