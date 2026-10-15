"""Thresholds of the demand and the season limit on the dashboard."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.core import HomeAssistant

from custom_components.hydronic_heating.const import CONF_SHADOW_MODE, DOMAIN
from custom_components.hydronic_heating.explain import demand_rule, room_call

from .test_runtime import _setup


def _ctrl(*, request: bool, combine: str = "any", rooms: int = 2, calling: int = 1, value=0.6):
    cfg = SimpleNamespace(
        demand_threshold=30.0,
        demand_hysteresis=10.0,
        min_rooms_calling=rooms,
        combine=combine,
        room_call_threshold=50.0,
    )
    arbitration = SimpleNamespace(request=request, calling=calling, weighted=value)
    # The hysteresis applies while the boiler really runs.
    return SimpleNamespace(
        cfg=cfg, arbitration=arbitration, sequencer=SimpleNamespace(boiler_on=request)
    )


async def test_demand_rule_sentences(hass: HomeAssistant) -> None:
    hass.config.language = "cs"
    assert demand_rule(hass, _ctrl(request=False, calling=0)) == "0,6 % z 30 % nebo 0 z 2 místností"
    # Running: the lower threshold of the hysteresis is the one to stop at.
    assert demand_rule(hass, _ctrl(request=True, value=25.0, calling=2)) == (
        "25 % z 20 % (vypnutí) nebo 2 z 2 místností"
    )
    # Both rules together.
    assert demand_rule(hass, _ctrl(request=False, combine="all", rooms=1)) == (
        "0,6 % z 30 % a 1 z 1 místnosti"
    )
    room = SimpleNamespace(demand=49.6)
    assert room_call(hass, room, _ctrl(request=False)) == "49,6 % z 50 %"
    room.demand = 0.0
    assert room_call(hass, room, _ctrl(request=False)) == "0 % z 50 %"


async def test_threshold_attributes_and_season_limit(hass: HomeAssistant) -> None:
    await _setup(hass)
    # The living room wants heat, but the boiler waits for the valves: the full
    # threshold applies until it really runs.
    total = hass.states.get("sensor.hh_demand_total").attributes
    assert (total["threshold"], total["min_rooms_calling"], total["combine"]) == (30, 1, "any")
    # Living room 100 %, bedroom 0 %: the mean is 50 %, one room calls.
    assert total["rule"] == "50 % of 30 % or 1 of 1 room"
    assert hass.states.get("sensor.hh_loznice_demand").attributes["call"] == "0 % of 50 %"
    assert hass.states.get("sensor.hh_heating_limit").state == "13.0"


async def test_legend_keeps_names_together_and_shows_the_rules(hass: HomeAssistant) -> None:
    hass.config.language = "cs"
    await _setup(hass)
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    rows = dashboard["views"][3]["sections"][0]["cards"][1]["content"]
    assert "**Celkový požadavek**" in rows
    assert "dosáhne 30 % nebo když volají aspoň 1 místnost" in rows
    assert "pod 20 % (hystereze)" in rows
    assert "Od 50 % se počítá jako volající" in rows
    assert "**Činnost (místnost)**" in rows
    assert "**Předtápění**" in rows
    assert "**Shadow**" in rows  # the test instance runs in shadow mode


async def test_legend_without_shadow_mode(hass: HomeAssistant) -> None:
    await _setup(hass, **{CONF_SHADOW_MODE: False})
    dashboard = await hass.services.async_call(
        DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True
    )
    assert "**Shadow**" not in dashboard["views"][3]["sections"][0]["cards"][1]["content"]
