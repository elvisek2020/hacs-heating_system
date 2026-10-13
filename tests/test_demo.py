"""Demo mode: virtual outputs, virtual house, safety net and dashboard."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.hydronic_heating.const import (
    CONF_DEMO_MODE,
    DEMO_VIRTUAL_HOUSE,
    DEMO_VIRTUAL_OUTPUTS,
    DOMAIN,
)
from custom_components.hydronic_heating.core.model import Command
from custom_components.hydronic_heating.demo_model import RoomThermal

from .test_runtime import _setup

REAL_OUTPUTS = (
    "input_boolean.kotel",
    "input_boolean.hlavice_obyvak",
    "input_boolean.hlavice_loznice",
)


async def _run(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int) -> None:
    for _ in range(seconds // 10):
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


def _real_states(hass: HomeAssistant) -> dict[str, str]:
    return {entity_id: hass.states.get(entity_id).state for entity_id in REAL_OUTPUTS}


# --- Thermal model ------------------------------------------------------------


def test_thermal_model_heats_and_cools() -> None:
    heated = RoomThermal(temperature=19.0, radiator=19.0, opening=0.0)
    for _ in range(360):  # one hour in 10 s steps
        heated.step(10, valves_open=1.0, travel_s=120, water_temp=40, outdoor=5, window_open=False)
    assert heated.opening == 1.0
    assert 19.5 < heated.temperature < 21.0

    idle = RoomThermal(temperature=21.0, radiator=21.0)
    window = RoomThermal(temperature=21.0, radiator=21.0)
    for _ in range(360):
        idle.step(10, valves_open=1.0, travel_s=120, water_temp=None, outdoor=5, window_open=False)
        window.step(10, valves_open=0.0, travel_s=120, water_temp=40, outdoor=5, window_open=True)
    assert 20.0 < idle.temperature < 21.0  # about 0.8 K per hour
    assert window.temperature < 15.0  # an open window cools much faster
    assert window.opening == 0.0


# --- Virtual outputs ------------------------------------------------------------


async def test_virtual_outputs_never_touch_real_entities(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Commands go to the demo switches; the real boiler and valves stay as they are."""
    entry = await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_OUTPUTS})
    before = _real_states(hass)
    assert hass.states.get("switch.hh_shadow_mode").state == "on"  # configured, overridden

    await _run(hass, freezer, 6 * 60)
    assert hass.states.get("switch.hh_demo_boiler").state == "on"
    assert hass.states.get("switch.hh_obyvak_demo_valve_1").state == "off"  # NO, open
    assert hass.states.get("switch.hh_loznice_demo_valve_1").state == "on"  # warm, closed
    assert hass.states.get("switch.hh_obyvak_demo_valve_1").attributes["real_entity"] == (
        "input_boolean.hlavice_obyvak"
    )
    assert _real_states(hass) == before
    # The controller verified the demo commands, no fault.
    assert hass.states.get("sensor.hh_state").state == "auto"
    assert entry.runtime_data.store.key.endswith(".demo")

    # Real sensors drive the decision.
    hass.states.async_set("sensor.obyvak", "24.0", {"unit_of_measurement": "°C"})
    await _run(hass, freezer, 6 * 60)
    assert hass.states.get("switch.hh_obyvak_demo_valve_1").state == "on"
    assert _real_states(hass) == before


async def test_safety_net_refuses_real_entities(hass: HomeAssistant) -> None:
    """Even a wrong command cannot reach a real entity during the demo."""
    entry = await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_OUTPUTS})
    runtime = entry.runtime_data
    calls: list[str] = []

    @callback
    def _record(event: Event) -> None:
        calls.append(str(event.data["service_data"].get("entity_id")))

    hass.bus.async_listen(EVENT_CALL_SERVICE, _record)
    await runtime._async_execute(Command("input_boolean.kotel", "turn_on"))
    await runtime._async_execute(Command("switch.hh_demo_boiler", "turn_on"))
    await hass.async_block_till_done()
    assert "input_boolean.kotel" not in calls
    assert "switch.hh_demo_boiler" in calls
    assert hass.states.get("input_boolean.kotel").state == "off"


async def test_virtual_boiler_ignoring_commands_goes_fault_safe(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The command path with retries and fault_safe can be tried without hardware."""
    await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_OUTPUTS})
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.hh_demo_boiler_behavior", "option": "ignore_commands"},
        blocking=True,
    )
    await _run(hass, freezer, 7 * 60)
    assert hass.states.get("switch.hh_demo_boiler").state == "off"
    assert hass.states.get("sensor.hh_state").state == "fault_safe"
    assert ir.async_get(hass).async_get_issue(DOMAIN, "fault_safe") is not None
    notifications = hass.data.get("persistent_notification", {})
    assert any(n["title"].startswith("[Demo]") for n in notifications.values())


# --- Virtual house --------------------------------------------------------------


async def test_virtual_house_heats_and_reacts_to_events(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Simulated rooms warm up, windows block, sensor faults are detected."""
    # A fixed start makes the PWM phase deterministic. At this moment the boiler
    # stops when the window blocks, so the test also covers the overrun.
    freezer.move_to("2026-10-10 20:00:00+00:00")
    await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_HOUSE})
    before = _real_states(hass)
    temperature = hass.states.get("sensor.hh_obyvak_demo_temperature")
    assert temperature is not None
    start = float(temperature.state)
    assert hass.states.get("number.hh_demo_outdoor_temperature").state == "5.0"
    # The controller now reads the simulated sensor.
    assert hass.states.get("climate.hh_obyvak").attributes["current_temperature"] == start

    await _run(hass, freezer, 60 * 60)
    assert hass.states.get("switch.hh_demo_boiler").state == "on"
    assert float(hass.states.get("sensor.hh_obyvak_demo_temperature").state) > start

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.hh_obyvak_demo_window"}, blocking=True
    )
    await _run(hass, freezer, 90)
    assert hass.states.get("binary_sensor.hh_obyvak_window").state == "on"
    # Valves that were open stay open during the boiler overrun (180 s); then the
    # boiler stands and no head draws current (NO = open).
    await _run(hass, freezer, 180)
    assert hass.states.get("switch.hh_obyvak_demo_valve_1").state == "off"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.hh_loznice_demo_sensor_fault"}, blocking=True
    )
    await _run(hass, freezer, 60)
    assert hass.states.get("sensor.hh_loznice_demo_temperature").state == "unavailable"
    assert hass.states.get("binary_sensor.hh_loznice_problem").state == "on"
    assert _real_states(hass) == before


# --- Dashboard and configuration -------------------------------------------------


async def test_generate_dashboard(hass: HomeAssistant) -> None:
    """The dashboard lists the real and the virtual entities of this installation."""
    await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_HOUSE})
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    text = str(dashboard)
    for entity_id in (
        "climate.hh_system",
        "climate.hh_obyvak",
        "switch.hh_demo_boiler",
        "switch.hh_obyvak_demo_window",
        "input_boolean.kotel",
        "number.hh_demo_outdoor_temperature",
        "button.hh_manual_60",
    ):
        assert entity_id in text, entity_id
    assert [view["path"] for view in dashboard["views"]] == ["prehled", "grafy"]


async def test_dashboard_without_demo(hass: HomeAssistant) -> None:
    """Without the demo the dashboard shows only real entities."""
    await _setup(hass)
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    assert "hh_demo" not in str(dashboard)


async def test_switching_demo_mode_reloads(hass: HomeAssistant) -> None:
    """Turning the demo on creates the demo entities, turning it off removes them."""
    entry = await _setup(hass)
    assert hass.states.get("switch.hh_demo_boiler") is None
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_DEMO_MODE: DEMO_VIRTUAL_OUTPUTS}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("switch.hh_demo_boiler") is not None
    assert hass.states.get("sensor.hh_obyvak_demo_temperature") is None
    hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_DEMO_MODE: "off"})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.demo is None
    assert not entry.runtime_data.store.key.endswith(".demo")


async def test_options_offer_demo_mode(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """The demo mode is chosen in Configure -> General."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "general"}
    )
    assert CONF_DEMO_MODE in {str(key) for key in result["data_schema"].schema}


# --- Reload (to-do: false fault_safe on reload) -----------------------------------


async def test_reload_in_demo_raises_no_false_fault(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, caplog: pytest.LogCaptureFixture
) -> None:
    """Removing the demo entities during unload must not look like a boiler fault."""
    entry = await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_OUTPUTS})
    await _run(hass, freezer, 6 * 60)
    assert entry.runtime_data.controller.ready
    assert hass.states.get("switch.hh_demo_boiler").state == "on"  # boiler running
    boiler_before = entry.runtime_data.controller.sequencer.to_dict()
    modes_before = entry.runtime_data.controller.modes.to_dict()
    caplog.clear()

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The stored state is unchanged: no forced stop touched the anti-cycling times.
    assert entry.runtime_data.controller.sequencer.to_dict() == boiler_before
    assert entry.runtime_data.controller.modes.to_dict() == modes_before

    assert ir.async_get(hass).async_get_issue(DOMAIN, "fault_safe") is None
    assert "v poruše" not in caplog.text
    assert "fault" not in caplog.text.lower()
    notifications = hass.data.get("persistent_notification", {})
    assert not any("fault_safe" in key for key in notifications)
    # The saved state is not a fault either.
    await _run(hass, freezer, 30)
    assert hass.states.get("sensor.hh_state").state != "fault_safe"


async def test_dashboard_structure(hass: HomeAssistant) -> None:
    """Overview with badges and one section per room; charts never mix units."""
    await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_HOUSE})
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    overview, history = dashboard["views"]
    assert overview["type"] == "sections"
    assert {b["entity"] for b in overview["badges"]} >= {
        "sensor.hh_state",
        "binary_sensor.hh_boiler_command",
        "sensor.hh_flow_setpoint",
    }
    # Control row (heating, boiler, boiler operation), demo across the width, rooms.
    headings = [
        next((c["heading"] for c in s["cards"] if c["type"] == "heading"), None)
        for s in overview["sections"]
    ]
    assert headings == [
        "Heating",
        "Boiler",
        "Boiler operation",
        "Demo · virtual house",
        "Rooms – individual settings",
        "Obývák",
        "Ložnice",
        "Legend",
    ]
    legend = overview["sections"][-1]
    assert legend["column_span"] == 3
    assert '<ha-icon icon="mdi:pipe-valve"></ha-icon> | **Valve**' in legend["cards"][2]["content"]
    assert overview["sections"][3]["column_span"] == 3
    divider = overview["sections"][4]
    assert divider["column_span"] == 3
    assert divider["cards"][0]["content"] == "<hr>"
    assert divider["cards"][1]["heading_style"] == "title"
    living = overview["sections"][-3]["cards"]
    assert living[0]["icon"] == "mdi:sofa-outline"
    assert living[1]["entity"] == "climate.hh_obyvak"
    # Room mode switch first (back to auto in one tap), then target and presets.
    assert [f["type"] for f in living[1]["features"]] == [
        "climate-hvac-modes",
        "target-temperature",
        "climate-preset-modes",
    ]
    assert living[1]["features"][0]["hvac_modes"] == ["auto", "heat", "off"]
    # Manual buttons press the button entity directly.
    system = overview["sections"][0]["cards"]
    manual = [c for c in system if c.get("entity", "").startswith("button.hh_manual_")]
    assert len(manual) == 4
    assert manual[0]["tap_action"]["perform_action"] == "button.press"
    # Each room temperature chart shows only its climate entity.
    room_charts = [c for c in history["sections"][0]["cards"] if c["type"] == "history-graph"]
    assert [len(c["entities"]) for c in room_charts] == [1, 1]
    demand_chart = history["sections"][1]["cards"][1]
    assert all(e["entity"].endswith("_demand") for e in demand_chart["entities"])


async def test_dashboard_explains_the_boiler(hass: HomeAssistant) -> None:
    """Reason, countdown and explanation of the boiler state (FR-SAFE-07)."""
    await _setup(hass, **{CONF_DEMO_MODE: DEMO_VIRTUAL_OUTPUTS})
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    overview, history = dashboard["views"]
    badges = {b["entity"]: b for b in overview["badges"]}
    assert "sensor.hh_boiler_reason" in badges
    hold_badge = badges["sensor.hh_boiler_hold_ends_at"]
    assert hold_badge["visibility"][0]["state_not"] == ["unknown", "unavailable"]
    boiler = overview["sections"][1]["cards"]
    assert boiler[1]["entity"] == "sensor.hh_boiler_reason"
    assert boiler[2]["entity"] == "sensor.hh_boiler_hold_ends_at"
    assert "visibility" in boiler[2]
    assert "state_attr('sensor.hh_boiler_reason', 'detail')" in boiler[3]["content"]
    assert [c.get("entity") for c in boiler[4:]] == [
        "sensor.hh_demand_total",
        "sensor.hh_flow_setpoint",
        "sensor.hh_outdoor_temperature_damped",
    ]
    operation = overview["sections"][2]["cards"]
    assert operation[1]["entity"] == "binary_sensor.hh_boiler_command"
    assert operation[-1]["entity"] == "binary_sensor.hh_problem"
    # In the demo the demo section explains what is switched, not the shadow banner.
    assert "shadow_mode" not in str(overview["sections"][3])
    timeline = history["sections"][1]["cards"][2]["entities"]
    assert timeline[0]["entity"] == "sensor.hh_boiler_reason"
    assert timeline[2]["entity"] == "switch.hh_demo_boiler"


async def test_dashboard_shadow_banner(hass: HomeAssistant) -> None:
    """Without the demo a banner shows in shadow mode."""
    await _setup(hass)
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    # Right after the boiler operation block, shown only in shadow mode.
    section = dashboard["views"][0]["sections"][3]
    assert section["column_span"] == 3
    assert section["visibility"] == [
        {"condition": "state", "entity": "switch.hh_shadow_mode", "state": "on"}
    ]
    banner = section["cards"][0]
    assert banner["type"] == "markdown"
    assert banner["content"].startswith('<ha-alert alert-type="warning">**Shadow mode:**')


async def test_dashboard_room_shows_the_valve_not_the_heads(hass: HomeAssistant) -> None:
    """The radiator valve is shown; the head outputs (switches) are not."""
    for mode in (None, DEMO_VIRTUAL_OUTPUTS):
        options = {CONF_DEMO_MODE: mode} if mode else {}
        entry = await _setup(hass, **options)
        dashboard = await hass.services.async_call(
            DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
        )
        text = str(dashboard)
        assert "input_boolean.hlavice_obyvak" not in text
        assert "demo_valve" not in text
        rooms = {
            s["cards"][0].get("heading"): s["cards"] for s in dashboard["views"][0]["sections"]
        }
        valve = next(c for c in rooms["Obývák"] if c.get("entity", "").endswith("valve_state"))
        assert valve["entity"] == "sensor.hh_obyvak_valve_state"
        assert valve["name"] == "Valve"  # test instance runs in English
        timeline = dashboard["views"][1]["sections"][2]["cards"][-1]["entities"]
        assert timeline == [
            {"entity": "sensor.hh_obyvak_valve_state", "name": "Obývák"},
            {"entity": "sensor.hh_loznice_valve_state", "name": "Ložnice"},
        ]
        assert await hass.config_entries.async_remove(entry.entry_id)
