"""Dashboard built from the configuration (service `generate_dashboard`).

Only built-in cards. Overview: status badges, system and boiler sections and
one compact section per room. History: one clear chart per topic, units are
never mixed in one chart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, ENTITY_PREFIX

if TYPE_CHECKING:
    from .core.model import RoomConfig
    from .runtime import HydronicHeatingRuntime

TEXTS: dict[str, dict[str, str]] = {
    "cs": {
        "title": "Topení",
        "overview": "Přehled",
        "history": "Grafy",
        "heating": "Topení",
        "boiler": "Kotel",
        "outdoor": "Venku",
        "rooms": "Místnosti",
        "system": "Systém",
        "mode": "Režim",
        "state": "Stav",
        "manual": "Manuální topení",
        "manual_ends_at": "Konec manuálu",
        "minutes": "{minutes} min",
        "stop": "Stop",
        "boiler_command": "Povel kotli",
        "boiler_reason": "Proč",
        "boiler_hold": "Další změna",
        "boiler_reason_timeline": "Důvod stavu kotle",
        "shadow_banner": (
            "**Shadow režim:** řízení všechno počítá, ale kotel ani hlavice nespíná. "
            "Co by udělalo, ukazuje logbook a atributy `would_command_*`."
        ),
        "open_windows": "Okna",
        "heat_demand": "Požadavek na teplo",
        "demand_total": "Celkový požadavek",
        "flow_setpoint": "Teplota vody",
        "duty_limit": "Omezení střídy",
        "boiler_duty": "Střída 24 h",
        "boiler_starts_today": "Starty dnes",
        "outdoor_damped": "Venku (tlumená)",
        "summer": "Léto",
        "window_block": "Blokace okny",
        "problem": "Porucha",
        "shadow": "Shadow",
        "temperature": "Teplota",
        "demand": "Požadavek",
        "valves": "Ventily",
        "window": "Okno",
        "valve": "Hlavice {index}",
        "head": "Hlavice",
        "head_n": "Hlavice {index}",
        "heads": "Hlavice",
        "demo": "Demo",
        "real": "Skutečná",
        "simulation": "Simulace",
        "demo_outputs": "Demo · virtuální výstupy",
        "demo_house": "Demo · virtuální dům",
        "demo_info_outputs": (
            "Povely jdou jen do **virtuálního kotle a hlavic**. Skutečné výstupy dál řídí "
            "stávající systém, vidíte je vedle virtuálních. U hlavic NO znamená *Vypnuto* "
            "bez proudu, tedy otevřeno."
        ),
        "demo_info_house": (
            "Teploty, okna a venkovní teplota jsou **simulované**. Povely jdou jen do "
            "virtuálních výstupů, skutečný kotel ani hlavice se nesepnou. U hlavic NO "
            "znamená *Vypnuto* bez proudu, tedy otevřeno."
        ),
        "boiler_virtual": "Kotel · demo",
        "boiler_real": "Kotel · skutečný",
        "boiler_behavior": "Chování kotle",
        "demo_outdoor": "Venkovní teplota",
        "demo_window": "Otevřít okno",
        "demo_sensor_fault": "Výpadek čidla",
        "room_temperatures": "Teploty místností",
        "room_demands": "Požadavky místností",
        "boiler_timeline": "Kotel a blokace",
        "outdoor_curve": "Venkovní teplota a teplota vody",
        "boiler_stats": "Kotel po dnech",
        "duty_per_day": "Střída kotle (průměr za den)",
        "starts_per_day": "Starty kotle za den",
        "valves_timeline": "Ventily",
    },
    "en": {
        "title": "Heating",
        "overview": "Overview",
        "history": "History",
        "heating": "Heating",
        "boiler": "Boiler",
        "outdoor": "Outdoor",
        "rooms": "Rooms",
        "system": "System",
        "mode": "Mode",
        "state": "State",
        "manual": "Manual heating",
        "manual_ends_at": "Manual ends",
        "minutes": "{minutes} min",
        "stop": "Stop",
        "boiler_command": "Boiler command",
        "boiler_reason": "Why",
        "boiler_hold": "Next change",
        "boiler_reason_timeline": "Boiler state reason",
        "shadow_banner": (
            "**Shadow mode:** the controller calculates everything but switches neither the "
            "boiler nor the valves. The logbook and the `would_command_*` attributes show "
            "what it would do."
        ),
        "open_windows": "Windows",
        "heat_demand": "Heat demand",
        "demand_total": "Total demand",
        "flow_setpoint": "Flow temperature",
        "duty_limit": "Duty limit",
        "boiler_duty": "Duty 24 h",
        "boiler_starts_today": "Starts today",
        "outdoor_damped": "Outdoor (damped)",
        "summer": "Summer",
        "window_block": "Window block",
        "problem": "Problem",
        "shadow": "Shadow",
        "temperature": "Temperature",
        "demand": "Demand",
        "valves": "Valves",
        "window": "Window",
        "valve": "Head {index}",
        "head": "Valve head",
        "head_n": "Head {index}",
        "heads": "Valve heads",
        "demo": "Demo",
        "real": "Real",
        "simulation": "Simulation",
        "demo_outputs": "Demo · virtual outputs",
        "demo_house": "Demo · virtual house",
        "demo_info_outputs": (
            "Commands go only to the **virtual boiler and valve heads**. The real outputs are "
            "still controlled by the current system and shown next to the virtual ones. For "
            "NO heads *Off* means de-energized, i.e. open."
        ),
        "demo_info_house": (
            "Temperatures, windows and the outdoor temperature are **simulated**. Commands "
            "go only to virtual outputs, the real boiler and valves are never switched. For "
            "NO heads *Off* means de-energized, i.e. open."
        ),
        "boiler_virtual": "Boiler · demo",
        "boiler_real": "Boiler · real",
        "boiler_behavior": "Boiler behavior",
        "demo_outdoor": "Outdoor temperature",
        "demo_window": "Open window",
        "demo_sensor_fault": "Sensor fault",
        "room_temperatures": "Room temperatures",
        "room_demands": "Room demands",
        "boiler_timeline": "Boiler and blocks",
        "outdoor_curve": "Outdoor and flow temperature",
        "boiler_stats": "Boiler per day",
        "duty_per_day": "Boiler duty (daily mean)",
        "starts_per_day": "Boiler starts per day",
        "valves_timeline": "Valves",
    },
}

# Room icons by a part of the room name (slug), the first match wins.
ROOM_ICONS = (
    ("obyv", "mdi:sofa-outline"),
    ("living", "mdi:sofa-outline"),
    ("lozn", "mdi:bed-outline"),
    ("bed", "mdi:bed-outline"),
    ("kuch", "mdi:stove"),
    ("kitchen", "mdi:stove"),
    ("koupel", "mdi:shower"),
    ("bath", "mdi:shower"),
    ("pracov", "mdi:desk"),
    ("office", "mdi:desk"),
    ("det", "mdi:teddy-bear"),
    ("kids", "mdi:teddy-bear"),
    ("chodb", "mdi:door"),
    ("hall", "mdi:door"),
    ("jidel", "mdi:silverware-fork-knife"),
    ("dining", "mdi:silverware-fork-knife"),
    ("wc", "mdi:toilet"),
    ("toal", "mdi:toilet"),
    ("pokoj", "mdi:bed-outline"),
)
ROOM_ICON_DEFAULT = "mdi:home-thermometer-outline"
PRESETS = ["comfort", "eco", "away", "none"]
HALF = {"columns": 6}
FULL = {"columns": "full"}


def room_icon(slug: str) -> str:
    """Pick an icon from the room name."""
    return next((icon for part, icon in ROOM_ICONS if part in slug), ROOM_ICON_DEFAULT)


def _tile(entity_id: str, name: str | None = None, **extra: Any) -> dict[str, Any]:
    card: dict[str, Any] = {"type": "tile", "entity": entity_id}
    if name:
        card["name"] = name
    card.update(extra)
    return card


def _half(entity_id: str, name: str | None = None, **extra: Any) -> dict[str, Any]:
    return _tile(entity_id, name, grid_options=HALF, **extra)


def _full(entity_id: str, name: str | None = None, **extra: Any) -> dict[str, Any]:
    return _tile(entity_id, name, grid_options=FULL, **extra)


def _heading(
    text: str, icon: str | None = None, *, subtitle: bool = False, **extra: Any
) -> dict[str, Any]:
    card: dict[str, Any] = {"type": "heading", "heading": text}
    if icon:
        card["icon"] = icon
    if subtitle:
        card["heading_style"] = "subtitle"
    card.update(extra)
    return card


def _badge(entity_id: str, name: str, **extra: Any) -> dict[str, Any]:
    return {"type": "entity", "entity": entity_id, "name": name, "show_name": True, **extra}


def _press(entity_id: str) -> dict[str, Any]:
    return {
        "action": "perform-action",
        "perform_action": "button.press",
        "target": {"entity_id": entity_id},
    }


def _when_on(entity_id: str) -> list[dict[str, str]]:
    return [{"condition": "state", "entity": entity_id, "state": "on"}]


def _when_known(entity_id: str) -> list[dict[str, Any]]:
    return [{"condition": "state", "entity": entity_id, "state_not": ["unknown", "unavailable"]}]


class _Ids:
    """Entity IDs of this installation, found by unique ID (renames are kept)."""

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        self.registry = er.async_get(runtime.hass)
        self.entry_id = runtime.entry.entry_id

    def system(self, domain: str, key: str) -> str:
        unique_id = f"{self.entry_id}_{key}"
        found = self.registry.async_get_entity_id(domain, DOMAIN, unique_id)
        return found or f"{domain}.{ENTITY_PREFIX}_{key}"

    def room(self, domain: str, room: RoomConfig, key: str) -> str:
        unique_id = f"{self.entry_id}_{room.room_id}_{key or 'climate'}"
        object_id = "_".join(p for p in (ENTITY_PREFIX, room.slug, key) if p)
        found = self.registry.async_get_entity_id(domain, DOMAIN, unique_id)
        return found or f"{domain}.{object_id}"


def build_dashboard(runtime: HydronicHeatingRuntime) -> dict[str, Any]:
    """Return a Lovelace dashboard (two sections views) for this installation."""
    lang = "cs" if (runtime.hass.config.language or "").startswith("cs") else "en"
    text = TEXTS[lang]
    ids = _Ids(runtime)
    return {
        "title": text["title"],
        "views": [_overview(runtime, ids, text), _history(runtime, ids, text)],
    }


# --- Overview ---------------------------------------------------------------


def _overview(runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str]) -> dict:
    sid = ids.system
    problem = sid("binary_sensor", "problem")
    shadow = sid("switch", "shadow_mode")
    hold = sid("sensor", "boiler_hold_ends_at")
    windows = sid("sensor", "open_windows")
    badges = [
        _badge(sid("sensor", "state"), text["state"]),
        _badge(sid("binary_sensor", "boiler_command"), text["boiler"], color="deep-orange"),
        _badge(sid("sensor", "boiler_reason"), text["boiler_reason"]),
        _badge(hold, text["boiler_hold"], visibility=_when_known(hold)),
        _badge(sid("sensor", "outdoor_temperature_damped"), text["outdoor"]),
        _badge(sid("sensor", "flow_setpoint"), text["flow_setpoint"]),
        _badge(sid("sensor", "demand_total"), text["demand_total"]),
        _badge(
            windows,
            text["open_windows"],
            color="blue",
            visibility=[{"condition": "numeric_state", "entity": windows, "above": 0}],
        ),
        _badge(problem, text["problem"], color="red", visibility=_when_on(problem)),
        _badge(shadow, text["shadow"], visibility=_when_on(shadow)),
    ]
    sections = [_system_section(runtime, ids, text), _boiler_section(ids, text)]
    if runtime.layout is not None:
        sections.append(_demo_section(runtime, text))
    sections.extend(_room_section(runtime, ids, text, room) for room in runtime.rooms)
    return {
        "title": text["overview"],
        "path": "prehled",
        "icon": "mdi:radiator",
        "type": "sections",
        "max_columns": 3,
        "badges": badges,
        "sections": sections,
    }


def _system_section(runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str]) -> dict:
    sid = ids.system
    durations = runtime.controller.cfg.manual_durations
    shadow = sid("switch", "shadow_mode")
    cards: list[dict[str, Any]] = [_heading(text["heating"], "mdi:radiator")]
    if runtime.layout is None:
        # In the demo the demo section explains what is switched.
        cards.append(
            {
                "type": "markdown",
                "content": f'<ha-alert alert-type="warning">{text["shadow_banner"]}</ha-alert>',
                "text_only": True,
                "visibility": _when_on(shadow),
            }
        )
    cards += [
        _tile(
            sid("climate", "system"),
            text["system"],
            state_content=["hvac_action", "hvac_mode"],
            features=[
                {
                    "type": "climate-hvac-modes",
                    "style": "icons",
                    "hvac_modes": ["off", "auto", "heat"],
                }
            ],
        ),
        _tile(sid("select", "system_mode"), text["mode"], features=[{"type": "select-options"}]),
        _heading(text["manual"], "mdi:fire", subtitle=True),
    ]
    # One row of start buttons (3 of 12 columns each, 4 per row).
    cards.extend(
        _tile(
            entity_id,
            text["minutes"].format(minutes=minutes),
            hide_state=True,
            vertical=True,
            tap_action=_press(entity_id),
            icon_tap_action=_press(entity_id),
            grid_options={"columns": 3},
        )
        for minutes in durations
        if (entity_id := sid("button", f"manual_{minutes}"))
    )
    # End time and stop only while manual heating runs.
    running = [{"condition": "state", "entity": sid("select", "system_mode"), "state": "manual"}]
    stop = sid("button", "stop")
    cards.append(_half(sid("sensor", "manual_ends_at"), text["manual_ends_at"], visibility=running))
    cards.append(
        _half(
            stop,
            text["stop"],
            hide_state=True,
            color="red",
            tap_action=_press(stop),
            icon_tap_action=_press(stop),
            visibility=running,
        )
    )
    return {"type": "grid", "cards": cards}


def _boiler_section(ids: _Ids, text: dict[str, str]) -> dict:
    sid = ids.system
    trend = {"type": "trend-graph", "hours_to_show": 24}
    reason = sid("sensor", "boiler_reason")
    hold = sid("sensor", "boiler_hold_ends_at")
    return {
        "type": "grid",
        "cards": [
            _heading(text["boiler"], "mdi:water-boiler"),
            # Why the boiler is on or off, and when that changes (FR-SAFE-07).
            _full(reason, text["boiler_reason"], state_content=["state", "last_changed"]),
            _full(hold, text["boiler_hold"], visibility=_when_known(hold)),
            {
                "type": "markdown",
                "content": f"{{{{ state_attr('{reason}', 'detail') }}}}",
                "text_only": True,
            },
            _half(
                sid("binary_sensor", "boiler_command"), text["boiler_command"], color="deep-orange"
            ),
            _half(sid("binary_sensor", "heat_demand"), text["heat_demand"], color="orange"),
            _full(
                sid("sensor", "demand_total"),
                text["demand_total"],
                features=[{"type": "bar-gauge", "min": 0, "max": 100}],
                features_position="inline",
            ),
            _full(sid("sensor", "flow_setpoint"), text["flow_setpoint"], features=[trend]),
            _full(
                sid("sensor", "outdoor_temperature_damped"),
                text["outdoor_damped"],
                features=[trend],
            ),
            _half(sid("sensor", "boiler_duty"), text["boiler_duty"]),
            _half(sid("sensor", "boiler_starts_today"), text["boiler_starts_today"]),
            _half(sid("sensor", "duty_limit"), text["duty_limit"]),
            _half(sid("binary_sensor", "summer"), text["summer"]),
            _half(sid("binary_sensor", "window_block"), text["window_block"]),
            _half(sid("binary_sensor", "problem"), text["problem"], color="red"),
        ],
    }


def _demo_section(runtime: HydronicHeatingRuntime, text: dict[str, str]) -> dict:
    layout = runtime.layout
    assert layout is not None
    real_boiler = runtime.real_system_config().heat_source.state_entity
    cards: list[dict[str, Any]] = [
        _heading(text["demo_house"] if layout.house else text["demo_outputs"], "mdi:test-tube"),
        {
            "type": "markdown",
            "content": text["demo_info_house"] if layout.house else text["demo_info_outputs"],
        },
        _half(layout.boiler.entity_id, text["boiler_virtual"], color="deep-orange"),
    ]
    if real_boiler:
        cards.append(_half(real_boiler, text["boiler_real"], color="deep-orange"))
    else:
        cards[-1]["grid_options"] = FULL
    cards.append(
        _tile(
            layout.boiler_behavior.entity_id,
            text["boiler_behavior"],
            features=[{"type": "select-options"}],
        )
    )
    if layout.house:
        cards.append(
            _tile(
                layout.outdoor.entity_id,
                text["demo_outdoor"],
                features=[{"type": "numeric-input", "style": "buttons"}],
            )
        )
    return {"type": "grid", "cards": cards}


def _room_section(
    runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str], room: RoomConfig
) -> dict:
    window = ids.room("binary_sensor", room, "window")
    problem = ids.room("binary_sensor", room, "problem")
    layout = runtime.layout
    demo = (
        next((d for d in layout.rooms if d.room.room_id == room.room_id), None)
        if layout is not None
        else None
    )
    cards: list[dict[str, Any]] = [
        _heading(
            room.name,
            room_icon(room.slug),
            badges=[
                {
                    "type": "entity",
                    "entity": window,
                    "show_state": False,
                    "visibility": _when_on(window),
                },
                {
                    "type": "entity",
                    "entity": problem,
                    "show_state": False,
                    "color": "red",
                    "visibility": _when_on(problem),
                },
            ],
        ),
        _full(
            ids.room("climate", room, ""),
            text["temperature"],
            state_content=["current_temperature", "hvac_action"],
            features=[
                {"type": "target-temperature"},
                {"type": "climate-preset-modes", "style": "dropdown", "preset_modes": PRESETS},
            ],
        ),
        _full(
            ids.room("sensor", room, "demand"),
            text["demand"],
            features=[{"type": "bar-gauge", "min": 0, "max": 100}],
            features_position="inline",
        ),
    ]
    single = len(room.valves) == 1
    if demo is None:
        cards.append(_half(ids.room("sensor", room, "valve_state"), text["valves"]))
        cards.extend(
            _half(
                valve.entity_id,
                text["head"] if single else text["head_n"].format(index=index),
                color="amber",
            )
            for index, valve in enumerate(room.valves, start=1)
        )
        return {"type": "grid", "cards": cards}

    cards.append(_full(ids.room("sensor", room, "valve_state"), text["valves"]))
    cards.append(_heading(text["heads"], "mdi:pipe-valve", subtitle=True))
    for index, valve in enumerate(room.valves, start=1):
        suffix = "" if single else f" {index}"
        cards.append(
            _half(demo.valves[index - 1].ids.entity_id, text["demo"] + suffix, color="amber")
        )
        cards.append(_half(valve.entity_id, text["real"] + suffix, color="amber"))
    if layout is not None and layout.house:
        cards.append(_heading(text["simulation"], "mdi:test-tube", subtitle=True))
        cards.append(_half(demo.window.entity_id, text["window"], color="blue"))
        cards.append(_half(demo.sensor_fault.entity_id, text["demo_sensor_fault"], color="red"))
    return {"type": "grid", "cards": cards}


# --- History ------------------------------------------------------------------


def _history(runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str]) -> dict:
    sid = ids.system
    rooms = runtime.rooms
    layout = runtime.layout
    real_boiler = runtime.real_system_config().heat_source.state_entity

    # One chart per room: current temperature, target and heating (climate history).
    room_cards: list[dict[str, Any]] = [_heading(text["room_temperatures"], "mdi:thermometer")]
    room_cards.extend(
        {
            "type": "history-graph",
            "title": room.name,
            "hours_to_show": 24,
            "entities": [{"entity": ids.room("climate", room, ""), "name": room.name}],
            "grid_options": HALF,
        }
        for room in rooms
    )

    boiler_entities: list[dict[str, str]] = [
        {"entity": sid("sensor", "boiler_reason"), "name": text["boiler_reason_timeline"]},
        {"entity": sid("binary_sensor", "boiler_command"), "name": text["boiler_command"]},
        {"entity": sid("binary_sensor", "heat_demand"), "name": text["heat_demand"]},
        {"entity": sid("binary_sensor", "window_block"), "name": text["window_block"]},
        {"entity": sid("binary_sensor", "summer"), "name": text["summer"]},
    ]
    if layout is not None:
        boiler_entities.insert(
            2, {"entity": layout.boiler.entity_id, "name": text["boiler_virtual"]}
        )
        if real_boiler:
            boiler_entities.insert(3, {"entity": real_boiler, "name": text["boiler_real"]})

    boiler_cards = [
        _heading(text["boiler"], "mdi:water-boiler"),
        {
            "type": "history-graph",
            "title": text["room_demands"],
            "hours_to_show": 24,
            "entities": [
                {"entity": ids.room("sensor", room, "demand"), "name": room.name} for room in rooms
            ],
        },
        {
            "type": "history-graph",
            "title": text["boiler_timeline"],
            "hours_to_show": 24,
            "entities": boiler_entities,
        },
        {
            "type": "history-graph",
            "title": text["outdoor_curve"],
            "hours_to_show": 48,
            "entities": [
                {
                    "entity": sid("sensor", "outdoor_temperature_damped"),
                    "name": text["outdoor_damped"],
                },
                {"entity": sid("sensor", "flow_setpoint"), "name": text["flow_setpoint"]},
            ],
        },
    ]

    stats_cards = [
        _heading(text["boiler_stats"], "mdi:chart-bar"),
        {
            "type": "statistics-graph",
            "title": text["duty_per_day"],
            "entities": [sid("sensor", "boiler_duty")],
            "stat_types": ["mean"],
            "period": "day",
            "days_to_show": 14,
            "chart_type": "bar",
        },
        {
            "type": "statistics-graph",
            "title": text["starts_per_day"],
            "entities": [sid("sensor", "boiler_starts_today")],
            "stat_types": ["max"],
            "period": "day",
            "days_to_show": 14,
            "chart_type": "bar",
        },
    ]

    valve_entities: list[dict[str, str]] = []
    demo_rooms = {d.room.room_id: d for d in layout.rooms} if layout is not None else {}
    for room in rooms:
        demo = demo_rooms.get(room.room_id)
        for index, valve in enumerate(room.valves, start=1):
            label = f"{room.name} · {text['valve'].format(index=index)}"
            if demo is not None:
                valve_entities.append(
                    {"entity": demo.valves[index - 1].ids.entity_id, "name": f"{label} · demo"}
                )
            valve_entities.append({"entity": valve.entity_id, "name": label})
    valve_cards = [
        _heading(text["valves_timeline"], "mdi:pipe-valve"),
        {"type": "history-graph", "hours_to_show": 24, "entities": valve_entities},
    ]

    return {
        "title": text["history"],
        "path": "grafy",
        "icon": "mdi:chart-line",
        "type": "sections",
        "max_columns": 2,
        "sections": [
            {"type": "grid", "column_span": 2, "cards": room_cards},
            {"type": "grid", "cards": boiler_cards},
            {"type": "grid", "cards": stats_cards + valve_cards},
        ],
    }
