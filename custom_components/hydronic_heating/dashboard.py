"""Dashboard for watching the controller and the demo, built from the configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, ENTITY_PREFIX

if TYPE_CHECKING:
    from .runtime import HydronicHeatingRuntime

TEXTS = {
    "cs": {
        "title": "Topení",
        "overview": "Přehled",
        "history": "Grafy",
        "system": "Systém",
        "manual": "Manuál",
        "demo_outputs": "Demo: virtuální výstupy",
        "demo_house": "Demo: virtuální dům",
        "real": "skutečný",
        "virtual": "virtuální",
        "boiler": "Kotel",
        "valve": "Ventil",
        "system_mode": "Režim",
        "state": "Stav",
        "boiler_command": "Povel kotli",
        "heat_demand": "Požadavek na teplo",
        "demand_total": "Celkový požadavek",
        "problem": "Porucha",
        "outdoor_temperature_damped": "Venku (tlumená)",
        "summer": "Léto",
        "window_block": "Blokace okny",
        "boiler_duty": "Střída 24 h",
        "boiler_starts_today": "Starty dnes",
        "shadow_mode": "Shadow režim",
        "manual_ends_at": "Konec manuálu",
        "flow_setpoint": "Teplota vody (křivka)",
        "duty_limit": "Omezení střídy",
        "temperature": "Teplota",
        "demand": "Požadavek",
        "valve_state": "Ventily",
        "window": "Okno",
        "demo_boiler_behavior": "Chování kotle",
        "demo_outdoor_temperature": "Venkovní teplota",
        "demo_window": "Okno (simulace)",
        "demo_sensor_fault": "Výpadek čidla (simulace)",
        "stop": "Zastavit",
        "minutes": "{minutes} min",
    },
    "en": {
        "title": "Heating",
        "overview": "Overview",
        "history": "History",
        "system": "System",
        "manual": "Manual",
        "demo_outputs": "Demo: virtual outputs",
        "demo_house": "Demo: virtual house",
        "real": "real",
        "virtual": "virtual",
        "boiler": "Boiler",
        "valve": "Valve",
        "system_mode": "Mode",
        "state": "State",
        "boiler_command": "Boiler command",
        "heat_demand": "Heat demand",
        "demand_total": "Total demand",
        "problem": "Problem",
        "outdoor_temperature_damped": "Outdoor (damped)",
        "summer": "Summer",
        "window_block": "Window block",
        "boiler_duty": "Duty 24 h",
        "boiler_starts_today": "Starts today",
        "shadow_mode": "Shadow mode",
        "manual_ends_at": "Manual ends",
        "flow_setpoint": "Flow temperature (curve)",
        "duty_limit": "Duty limit",
        "temperature": "Temperature",
        "demand": "Demand",
        "valve_state": "Valves",
        "window": "Window",
        "demo_boiler_behavior": "Boiler behavior",
        "demo_outdoor_temperature": "Outdoor temperature",
        "demo_window": "Window (simulated)",
        "demo_sensor_fault": "Sensor fault (simulated)",
        "stop": "Stop",
        "minutes": "{minutes} min",
    },
}


def _tile(entity_id: str, name: str | None = None, **extra: Any) -> dict[str, Any]:
    card: dict[str, Any] = {"type": "tile", "entity": entity_id}
    if name:
        card["name"] = name
    card.update(extra)
    return card


def build_dashboard(runtime: HydronicHeatingRuntime) -> dict[str, Any]:
    """Return a Lovelace dashboard (sections view) for this installation."""
    hass = runtime.hass
    entry = runtime.entry
    lang = "cs" if (hass.config.language or "").startswith("cs") else "en"
    text = TEXTS[lang]
    registry = er.async_get(hass)

    def system_id(domain: str, key: str) -> str:
        unique_id = f"{entry.entry_id}_{key}"
        return registry.async_get_entity_id(domain, DOMAIN, unique_id) or (
            f"{domain}.{ENTITY_PREFIX}_{key}"
        )

    def room_id(domain: str, room: Any, key: str) -> str:
        unique_id = f"{entry.entry_id}_{room.room_id}_{key or 'climate'}"
        object_id = "_".join(p for p in (ENTITY_PREFIX, room.slug, key) if p)
        return registry.async_get_entity_id(domain, DOMAIN, unique_id) or f"{domain}.{object_id}"

    cfg = runtime.controller.cfg
    durations = cfg.manual_durations
    system_cards: list[dict[str, Any]] = [
        {"type": "heading", "heading": text["system"]},
        _tile(
            system_id("climate", "system"),
            features=[{"type": "climate-hvac-modes", "hvac_modes": ["off", "auto", "heat"]}],
        ),
        _tile(
            system_id("select", "system_mode"),
            text["system_mode"],
            features=[{"type": "select-options"}],
        ),
        _tile(system_id("sensor", "state"), text["state"]),
        _tile(system_id("binary_sensor", "boiler_command"), text["boiler_command"]),
        _tile(system_id("binary_sensor", "heat_demand"), text["heat_demand"]),
        _tile(system_id("sensor", "demand_total"), text["demand_total"]),
        _tile(system_id("binary_sensor", "problem"), text["problem"]),
        _tile(
            system_id("sensor", "outdoor_temperature_damped"), text["outdoor_temperature_damped"]
        ),
        _tile(system_id("sensor", "flow_setpoint"), text["flow_setpoint"]),
        _tile(system_id("sensor", "duty_limit"), text["duty_limit"]),
        _tile(system_id("binary_sensor", "summer"), text["summer"]),
        _tile(system_id("binary_sensor", "window_block"), text["window_block"]),
        _tile(system_id("sensor", "boiler_duty"), text["boiler_duty"]),
        _tile(system_id("sensor", "boiler_starts_today"), text["boiler_starts_today"]),
        _tile(system_id("switch", "shadow_mode"), text["shadow_mode"]),
        {"type": "heading", "heading": text["manual"], "heading_style": "subtitle"},
        _tile(system_id("sensor", "manual_ends_at"), text["manual_ends_at"]),
        {
            "type": "entities",
            "entities": [
                {
                    "entity": system_id("button", f"manual_{m}"),
                    "name": text["minutes"].format(minutes=m),
                }
                for m in durations
            ]
            + [{"entity": system_id("button", "stop"), "name": text["stop"]}],
        },
    ]
    sections: list[dict[str, Any]] = [{"type": "grid", "cards": system_cards}]

    layout = runtime.layout
    real_boiler = runtime.real_system_config().heat_source.state_entity
    if layout is not None:
        demo_cards: list[dict[str, Any]] = [
            {
                "type": "heading",
                "heading": text["demo_house"] if layout.house else text["demo_outputs"],
            },
            _tile(layout.boiler.entity_id, f"{text['boiler']} ({text['virtual']})"),
        ]
        if real_boiler:
            demo_cards.append(_tile(real_boiler, f"{text['boiler']} ({text['real']})"))
        demo_cards.append(
            _tile(
                layout.boiler_behavior.entity_id,
                text["demo_boiler_behavior"],
                features=[{"type": "select-options"}],
            )
        )
        if layout.house:
            demo_cards.append(_tile(layout.outdoor.entity_id, text["demo_outdoor_temperature"]))
        sections.append({"type": "grid", "cards": demo_cards})

    demo_rooms = {room.room.room_id: room for room in layout.rooms} if layout else {}
    history_cards: list[dict[str, Any]] = [
        {
            "type": "history-graph",
            "title": text["system"],
            "hours_to_show": 24,
            "entities": [
                system_id("binary_sensor", "boiler_command"),
                system_id("sensor", "demand_total"),
                system_id("sensor", "flow_setpoint"),
                system_id("sensor", "state"),
            ]
            + ([layout.boiler.entity_id] if layout else [])
            + ([real_boiler] if real_boiler else []),
        }
    ]
    for room in runtime.rooms:
        climate = room_id("climate", room, "")
        cards: list[dict[str, Any]] = [
            {"type": "heading", "heading": room.name},
            _tile(
                climate,
                features=[
                    {"type": "target-temperature"},
                    {
                        "type": "climate-preset-modes",
                        "style": "dropdown",
                        "preset_modes": ["comfort", "eco", "away", "none"],
                    },
                ],
            ),
            _tile(room_id("sensor", room, "temperature"), text["temperature"]),
            _tile(room_id("sensor", room, "demand"), text["demand"]),
            _tile(room_id("sensor", room, "valve_state"), text["valve_state"]),
            _tile(room_id("binary_sensor", room, "window"), text["window"]),
            _tile(room_id("binary_sensor", room, "problem"), text["problem"]),
        ]
        demo = demo_rooms.get(room.room_id)
        for index, valve in enumerate(room.valves, start=1):
            if demo is not None:
                cards.append(
                    _tile(
                        demo.valves[index - 1].ids.entity_id,
                        f"{text['valve']} {index} ({text['virtual']})",
                    )
                )
            cards.append(_tile(valve.entity_id, f"{text['valve']} {index} ({text['real']})"))
        if demo is not None and layout is not None and layout.house:
            cards.append(_tile(demo.window.entity_id, text["demo_window"]))
            cards.append(_tile(demo.sensor_fault.entity_id, text["demo_sensor_fault"]))
        sections.append({"type": "grid", "cards": cards})
        history_cards.append(
            {
                "type": "history-graph",
                "title": room.name,
                "hours_to_show": 24,
                "entities": [
                    climate,
                    room_id("sensor", room, "demand"),
                    *(
                        [v.ids.entity_id for v in demo.valves]
                        if demo is not None
                        else [v.entity_id for v in room.valves]
                    ),
                ],
            }
        )

    return {
        "title": text["title"],
        "views": [
            {
                "title": text["overview"],
                "path": "prehled",
                "type": "sections",
                "sections": sections,
            },
            {
                "title": text["history"],
                "path": "grafy",
                "type": "sections",
                "sections": [{"type": "grid", "cards": history_cards}],
            },
        ],
    }
