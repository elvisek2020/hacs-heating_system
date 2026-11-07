"""External hold of the boiler in Home Assistant (FR-BOI-10)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.hydronic_heating.const import (
    CONF_EXTERNAL_HOLD_ENTITY,
    CONF_EXTERNAL_HOLD_MAX,
    CONF_SHADOW_MODE,
    DOMAIN,
    EVENT_DECISION,
)

from .test_runtime import CELSIUS, _settle, _setup, _wait

HOLD = "input_boolean.nabijeni"
CALENDAR = "calendar.nabijeni"


def _local(when) -> str:
    return dt_util.as_local(when).strftime("%Y-%m-%d %H:%M:%S")


async def test_hold_keeps_the_boiler_off_and_says_why(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    hass.config.language = "cs"
    freezer.move_to("2026-01-15 11:00:00+00:00")
    hass.states.async_set(HOLD, "on", {"friendly_name": "Nabíjení"})
    events = async_capture_events(hass, EVENT_DECISION)
    await _setup(hass, **{CONF_SHADOW_MODE: False, CONF_EXTERNAL_HOLD_ENTITY: HOLD})
    hass.states.async_set("sensor.obyvak", "25.0", CELSIUS)
    await _wait(hass, freezer, 5 * 60)
    assert hass.states.get("sensor.hh_boiler_reason").state == "idle"
    hass.states.async_set("sensor.obyvak", "19.0", CELSIUS)  # the living room wants heat
    await _wait(hass, freezer, 5 * 60)
    assert hass.states.get("input_boolean.kotel").state == "off"
    reason = hass.states.get("sensor.hh_boiler_reason")
    assert reason.state == "external_hold"
    assert reason.attributes["rule"] == f"external_hold_entity = {HOLD}"
    assert reason.attributes["detail"].startswith(
        "Teplo je potřeba, ale kotel blokuje Nabíjení, proto kotel nestartuje. Start nejdříve v "
    )
    system = hass.states.get("climate.hh_system").attributes
    assert system["external_hold"] == "active"
    assert system["blocked_by"] == ["external_hold"]
    hold = next(e.data for e in events if e.data["kind"] == "hold")
    assert hold["message"].startswith("Start odložen do ")
    assert hold["message"].endswith(": kotel blokuje Nabíjení.")

    hass.states.async_set(HOLD, "off", {"friendly_name": "Nabíjení"})
    await _settle(hass)
    await _wait(hass, freezer, 5 * 60)
    assert hass.states.get("input_boolean.kotel").state == "on"
    assert hass.states.get("climate.hh_system").attributes["external_hold"] == "off"


async def test_calendar_window_stops_the_running_boiler(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    hass.config.language = "cs"
    freezer.move_to("2026-01-15 11:00:00+00:00")
    hass.states.async_set(CALENDAR, "off", {"friendly_name": "Nabíjení baterie"})
    events = async_capture_events(hass, EVENT_DECISION)
    await _setup(hass, **{CONF_SHADOW_MODE: False, CONF_EXTERNAL_HOLD_ENTITY: CALENDAR})
    await _wait(hass, freezer, 15 * 60)
    assert hass.states.get("input_boolean.kotel").state == "on"

    start = dt_util.utcnow() + timedelta(minutes=8)
    hass.states.async_set(
        CALENDAR,
        "off",
        {
            "friendly_name": "Nabíjení baterie",
            "start_time": _local(start),
            "end_time": _local(start + timedelta(minutes=45)),
        },
    )
    await _settle(hass)
    assert hass.states.get("input_boolean.kotel").state == "off"
    off = next(e.data for e in events if e.data["kind"] == "boiler_off")
    assert off["cause"] == "external_hold"
    local = dt_util.as_local(start)
    assert off["message"].startswith(
        f"Kotel vypnut: v {local.hour}:{local:%M} začíná blokace kotle (Nabíjení baterie)."
    )
    await _wait(hass, freezer, 5 * 60)
    reason = hass.states.get("sensor.hh_boiler_reason")
    assert reason.state == "external_hold"
    assert dt_util.parse_datetime(reason.attributes["until"]) == start + timedelta(minutes=45)
    assert hass.states.get("climate.hh_system").attributes["external_hold"] == "upcoming"


async def test_long_hold_is_reported_and_the_boiler_may_run(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-01-15 11:00:00+00:00")
    hass.states.async_set(HOLD, "on", {"friendly_name": "Nabíjení"})
    await _setup(
        hass,
        **{CONF_SHADOW_MODE: False, CONF_EXTERNAL_HOLD_ENTITY: HOLD, CONF_EXTERNAL_HOLD_MAX: 30},
    )
    await _wait(hass, freezer, 35 * 60)
    assert hass.states.get("input_boolean.kotel").state == "on"
    assert hass.states.get("binary_sensor.hh_problem").attributes["problems"] == [
        "external_hold_long"
    ]
    notifications = hass.data.get("persistent_notification", {})
    message = notifications[f"{DOMAIN}_external_hold_long"]["message"]
    assert message.startswith("Nabíjení has held the boiler for more than 30 min.")
    hass.states.async_set(HOLD, "off", {"friendly_name": "Nabíjení"})
    await _settle(hass)
    assert hass.states.get("binary_sensor.hh_problem").state == "off"
