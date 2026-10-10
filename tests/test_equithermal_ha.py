"""F3 in Home Assistant: curve and duty sensors, forecast, options."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hydronic_heating.const import (
    CONF_BOILER_FIXED_FLOW_TEMP,
    CONF_DESIGN_FLOW_TEMP,
    CONF_FLOW_TEMP_MIN,
    CONF_OUTDOOR_SENSORS,
    CONF_USE_FORECAST,
    CONF_WEATHER_ENTITY,
)

from .conftest import form_input
from .test_runtime import _setup

HOUSE = {
    CONF_DESIGN_FLOW_TEMP: 40,
    CONF_FLOW_TEMP_MIN: 25,
    CONF_BOILER_FIXED_FLOW_TEMP: 40,
    CONF_OUTDOOR_SENSORS: ["sensor.venku"],
}


def _mock_forecast(hass: HomeAssistant, temperatures: list[float]) -> list[str]:
    """Register weather.get_forecasts returning hourly temperatures."""
    calls: list[str] = []

    async def handler(call: ServiceCall) -> dict[str, Any]:
        calls.append(call.data["type"])
        if call.data["type"] != "hourly":
            return {}
        now = dt_util.utcnow()
        return {
            "weather.domov": {
                "forecast": [
                    {"datetime": (now + timedelta(hours=i)).isoformat(), "temperature": t}
                    for i, t in enumerate(temperatures)
                ]
            }
        }

    hass.services.async_register(
        "weather", "get_forecasts", handler, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set("weather.domov", "cloudy", {"temperature": 8.0})
    return calls


async def test_curve_and_duty_sensors(hass: HomeAssistant) -> None:
    """The virtual flow temperature and the duty limit are visible (FR-EQ-04, 05)."""
    hass.states.async_set("sensor.venku", "5.0", {"unit_of_measurement": "°C"})
    await _setup(hass, **HOUSE)
    flow = hass.states.get("sensor.hh_flow_setpoint")
    assert flow.state == "31.2"
    assert flow.attributes["virtual"] is True
    duty = hass.states.get("sensor.hh_duty_limit")
    assert duty.state == "56"
    assert duty.attributes["enabled"] is False
    assert duty.attributes["run_per_cycle_min"] == 11.2


async def test_curve_unknown_without_outdoor(hass: HomeAssistant) -> None:
    await _setup(hass)
    assert hass.states.get("sensor.hh_flow_setpoint").state == "unknown"
    assert hass.states.get("sensor.hh_duty_limit").state == "unknown"


async def test_forecast_is_fetched_and_used(hass: HomeAssistant) -> None:
    """FR-EQ-06: mean of the next 24 h forecast complements the damped value."""
    hass.states.async_set("sensor.venku", "5.0", {"unit_of_measurement": "°C"})
    calls = _mock_forecast(hass, [11.0] * 24 + [30.0] * 24)
    await _setup(hass, **{**HOUSE, CONF_USE_FORECAST: True, CONF_WEATHER_ENTITY: "weather.domov"})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert calls[0] == "hourly"
    outdoor = hass.states.get("sensor.hh_outdoor_temperature_damped")
    assert outdoor.attributes["forecast_24h"] == 11.0
    assert outdoor.attributes["effective"] == 8.0  # (5 + 11) / 2
    assert hass.states.get("sensor.hh_flow_setpoint").state == "29.4"  # curve at 8 °C


async def test_forecast_disabled_is_not_fetched(hass: HomeAssistant) -> None:
    calls = _mock_forecast(hass, [11.0] * 24)
    await _setup(hass, **{CONF_WEATHER_ENTITY: "weather.domov"})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert calls == []


async def test_forecast_option_needs_weather(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "equithermal"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], form_input(result, use_forecast=True)
    )
    assert result["errors"] == {CONF_USE_FORECAST: "forecast_needs_weather"}
