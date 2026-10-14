"""Thresholds of the demand and the season limit on the dashboard."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.core import HomeAssistant

from custom_components.hydronic_heating.const import CONF_SHADOW_MODE, DOMAIN
from custom_components.hydronic_heating.explain import demand_rule, room_call

from .test_runtime import _setup


def _ctrl(*, request: bool, combine: str = "any", rooms: int = 2, calling: int = 1):
    cfg = SimpleNamespace(
        demand_threshold=30.0,
        demand_hysteresis=10.0,
        min_rooms_calling=rooms,
        combine=combine,
        room_call_threshold=50.0,
    )
    return SimpleNamespace(cfg=cfg, arbitration=SimpleNamespace(request=request, calling=calling))


async def test_demand_rule_sentences(hass: HomeAssistant) -> None:
    hass.config.language = "cs"
    assert demand_rule(hass, _ctrl(request=False)) == (
        "start od 30 % nebo od 2 volajících místností · volá 1"
    )
    assert demand_rule(hass, _ctrl(request=True)) == (
        "vypne pod 20 % a pod 2 volajícími místnostmi · volá 1"
    )
    # Both rules together swap the joining words.
    assert demand_rule(hass, _ctrl(request=False, combine="all", rooms=1)) == (
        "start od 30 % a od 1 volající místnosti · volá 1"
    )
    assert demand_rule(hass, _ctrl(request=True, combine="all", rooms=1)) == (
        "vypne pod 20 % nebo pod 1 volající místností · volá 1"
    )
    room = SimpleNamespace(demand=49.6)
    assert room_call(hass, room, _ctrl(request=False)) == "nevolá (volá od 50 %)"
    room.demand = 75.0
    assert room_call(hass, room, _ctrl(request=False)) == "volá (od 50 %)"


async def test_threshold_attributes_and_season_limit(hass: HomeAssistant) -> None:
    await _setup(hass)
    # The living room wants heat: the boiler is requested, the lower threshold applies.
    total = hass.states.get("sensor.hh_demand_total").attributes
    assert (total["threshold"], total["min_rooms_calling"], total["combine"]) == (20, 1, "any")
    assert total["rule"] == "stops below 20 % and below 1 calling room · 1 calling"
    assert hass.states.get("sensor.hh_obyvak_demand").attributes["call"].startswith("calling")
    assert hass.states.get("sensor.hh_loznice_demand").attributes["call"].startswith("not")
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
