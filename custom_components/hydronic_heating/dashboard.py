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
        "boiler_operation": "Provoz kotle",
        "rooms_settings": "Místnosti – individuální nastavení",
        "season": "Topná sezóna",
        "outdoor_mean_4h": "Venku (průměr 4 h)",
        "who_home": "Kdo je doma",
        "home": "Doma",
        "home_house": "Doma v domě",
        "nobody": "nikdo",
        "schedule_house_line": "Rozvrh domu",
        "on": "zapnuto",
        "off": "vypnuto",
        "next_change": "další změna",
        "legend": "Vysvětlivky",
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
            "**Shadow režim:** řízení všechno počítá, ale kotel ani ventily nespíná. "
            "Co by udělalo, ukazuje logbook a atributy `would_command_*`."
        ),
        "open_windows": "Okna",
        "presence": "Doma",
        "house_schedule": "Rozvrh domu",
        "schedule_room": "Rozvrh",
        "long_away": "Dlouhodobě pryč",
        "heat_demand": "Požadavek na teplo",
        "demand_total": "Celkový požadavek",
        "flow_setpoint": "Teplota vody",
        "duty_limit": "Omezení střídy",
        "boiler_duty": "Střída 24 h",
        "boiler_starts_today": "Starty dnes",
        "outdoor_damped": "Venku (tlumená)",
        "window_block": "Blokace okny",
        "problem": "Porucha",
        "shadow": "Shadow",
        "temperature": "Teplota",
        "demand": "Požadavek",
        "valve": "Ventil",
        "valves": "Ventily",
        "window": "Okno",
        "simulation": "Simulace",
        "demo_outputs": "Demo · virtuální výstupy",
        "demo_house": "Demo · virtuální dům",
        "demo_info_outputs": (
            "Povely jdou jen do **virtuálního kotle a ventilů**. Skutečný kotel a ventily "
            "dál řídí stávající systém, skutečný kotel vidíte vedle virtuálního."
        ),
        "demo_info_house": (
            "Teploty, okna a venkovní teplota jsou **simulované**. Povely jdou jen do "
            "virtuálních výstupů, skutečný kotel ani ventily se nesepnou."
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
        "boiler_operation": "Boiler operation",
        "rooms_settings": "Rooms – individual settings",
        "season": "Heating season",
        "outdoor_mean_4h": "Outdoor (4 h mean)",
        "who_home": "Who is home",
        "home": "Home",
        "home_house": "Home in the house",
        "nobody": "nobody",
        "schedule_house_line": "House schedule",
        "on": "on",
        "off": "off",
        "next_change": "next change",
        "legend": "Legend",
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
        "presence": "Home",
        "house_schedule": "House schedule",
        "schedule_room": "Schedule",
        "long_away": "Long absence",
        "heat_demand": "Heat demand",
        "demand_total": "Total demand",
        "flow_setpoint": "Flow temperature",
        "duty_limit": "Duty limit",
        "boiler_duty": "Duty 24 h",
        "boiler_starts_today": "Starts today",
        "outdoor_damped": "Outdoor (damped)",
        "window_block": "Window block",
        "problem": "Problem",
        "shadow": "Shadow",
        "temperature": "Temperature",
        "demand": "Demand",
        "valve": "Valve",
        "valves": "Valves",
        "window": "Window",
        "simulation": "Simulation",
        "demo_outputs": "Demo · virtual outputs",
        "demo_house": "Demo · virtual house",
        "demo_info_outputs": (
            "Commands go only to the **virtual boiler and valves**. The real boiler and valves "
            "are still controlled by the current system; the real boiler is shown next to the "
            "virtual one."
        ),
        "demo_info_house": (
            "Temperatures, windows and the outdoor temperature are **simulated**. Commands "
            "go only to virtual outputs, the real boiler and valves are never switched."
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

# Legend at the end of the overview: icon as on the dashboard, name, meaning.
LEGEND: dict[str, list[tuple[str, str, str]]] = {
    "cs": [
        (
            "mdi:state-machine",
            "Stav",
            "Stav řízení: automaticky, pryč, vypnuto, mimo sezónu, manuál nebo porucha.",
        ),
        (
            "mdi:thermostat",
            "Systém",
            "Režim celé soustavy: vypnuto, automaticky, nebo topit (manuál).",
        ),
        (
            "mdi:radiator",
            "Režim",
            "Automaticky, manuál, vypnuto nebo pryč (teploty Pryč ve všech místnostech).",
        ),
        (
            "mdi:calendar-range",
            "Topná sezóna",
            (
                "Automaticky podle 4h průměru venkovní teploty, nebo ručně. Mimo sezónu se "
                "netopí, protimrazová ochrana platí."
            ),
        ),
        (
            "mdi:calendar-clock",
            "Rozvrh domu",
            "Zapnuto = komfort, vypnuto = útlum. Platí pro místnosti bez vlastního rozvrhu.",
        ),
        (
            "mdi:fire",
            "Manuální topení",
            "Topí na zvolenou dobu. Konec manuálu a Stop se ukážou jen během manuálu.",
        ),
        (
            "mdi:information-outline",
            "Proč",
            "Proč kotel topí nebo stojí. Pod ním věta s vysvětlením.",
        ),
        (
            "mdi:timer-sand",
            "Další změna",
            "Kdy skončí časové pravidlo (minimální běh, pauza, doběh). Jen když nějaké platí.",
        ),
        ("mdi:gauge", "Celkový požadavek", "Vážený požadavek všech místností na teplo v %."),
        (
            "mdi:thermometer-water",
            "Teplota vody",
            "Teplota vody podle topné křivky. U kotle spínaného kontaktem jen orientační.",
        ),
        (
            "mdi:thermometer",
            "Venku (tlumená)",
            "Venkovní teplota s tlumením, podle ní se počítá topná křivka.",
        ),
        ("mdi:play", "Povel kotli", "Zda integrace kotli povoluje topit."),
        ("mdi:fire-alert", "Požadavek na teplo", "Zda místnosti teplo chtějí."),
        ("mdi:percent-outline", "Střída 24 h", "Kolik procent posledních 24 hodin kotel běžel."),
        ("mdi:counter", "Starty dnes", "Počet startů kotle od půlnoci."),
        (
            "mdi:sine-wave",
            "Omezení střídy",
            "Kolik procent cyklu smí kotel běžet podle topné křivky.",
        ),
        (
            "mdi:radiator",
            "Topná sezóna (stav)",
            "Zda je topná sezóna. Začne hned pod hranicí, skončí po 3 celých dnech nad ní.",
        ),
        (
            "mdi:thermometer-lines",
            "Venku (průměr 4 h)",
            "Průměr venkovní teploty za 4 hodiny, podle něj se řídí topná sezóna.",
        ),
        (
            "mdi:window-open-variant",
            "Blokace okny",
            "Otevřená okna ve více místnostech zastavila kotel.",
        ),
        (
            "mdi:alert-circle",
            "Porucha",
            "Něco nefunguje (kotel, čidlo, ventil). Podrobnosti v oznámeních a v Opravách.",
        ),
        (
            "mdi:account-multiple",
            "Kdo je doma",
            (
                "Osoby z přítomnosti, kterou topení používá. „Před 5 minutami“ ukazuje, kdo právě"
                " odešel."
            ),
        ),
        (
            "mdi:thermostat",
            "Teplota (místnost)",
            (
                "Aktuální teplota, režim místnosti (automaticky, ručně, vypnuto), cíl a "
                "předvolba. Ruční změna platí trvale, zpět na automatiku jedním dotykem."
            ),
        ),
        ("mdi:text", "Věta u místnosti", "Proč má místnost tento cíl, kdo je doma a rozvrh domu."),
        (
            "mdi:pipe-valve",
            "Ventil",
            "Poloha ventilu radiátoru: otevřeno, otevírá se, zavírá se, zavřeno.",
        ),
        ("mdi:gauge", "Požadavek (místnost)", "Kolik procent tepla místnost chce."),
        (
            "mdi:calendar-clock",
            "Rozvrh (místnost)",
            "Vlastní plán místnosti, jen když ho místnost má. Úprava mění jen tuto místnost.",
        ),
        ("mdi:ghost-outline", "Shadow", "Řízení všechno počítá, ale kotel ani ventily nespíná."),
    ],
    "en": [
        (
            "mdi:state-machine",
            "State",
            "Control state: auto, away, off, off season, manual or fault.",
        ),
        ("mdi:thermostat", "System", "Mode of the whole system: off, auto, or heat (manual)."),
        ("mdi:radiator", "Mode", "Auto, manual, off or away (away temperatures in all rooms)."),
        (
            "mdi:calendar-range",
            "Heating season",
            (
                "Automatic by the 4 h mean outdoor temperature, or by hand. No heating off "
                "season, frost protection applies."
            ),
        ),
        (
            "mdi:calendar-clock",
            "House schedule",
            "On = comfort, off = setback. For rooms without their own schedule.",
        ),
        (
            "mdi:fire",
            "Manual heating",
            "Heats for the chosen time. Manual end and Stop show only during manual heating.",
        ),
        (
            "mdi:information-outline",
            "Why",
            "Why the boiler heats or stands. A sentence below explains it.",
        ),
        (
            "mdi:timer-sand",
            "Next change",
            "When a time rule ends (minimum run, pause, overrun). Only while one applies.",
        ),
        ("mdi:gauge", "Total demand", "Weighted heat demand of all rooms in %."),
        (
            "mdi:thermometer-water",
            "Flow temperature",
            (
                "Water temperature by the heating curve. Only indicative for a boiler switched by"
                " a contact."
            ),
        ),
        (
            "mdi:thermometer",
            "Outdoor (damped)",
            "Damped outdoor temperature, used for the heating curve.",
        ),
        ("mdi:play", "Boiler command", "Whether the integration lets the boiler heat."),
        ("mdi:fire-alert", "Heat demand", "Whether the rooms want heat."),
        (
            "mdi:percent-outline",
            "Duty 24 h",
            "How many percent of the last 24 hours the boiler ran.",
        ),
        ("mdi:counter", "Starts today", "Boiler starts since midnight."),
        (
            "mdi:sine-wave",
            "Duty limit",
            "How many percent of a cycle the boiler may run by the curve.",
        ),
        (
            "mdi:radiator",
            "Heating season (state)",
            (
                "Whether it is the heating season. Starts at once below the limit, ends after 3 "
                "whole days above it."
            ),
        ),
        (
            "mdi:thermometer-lines",
            "Outdoor (4 h mean)",
            "Mean outdoor temperature of 4 hours; the heating season follows it.",
        ),
        (
            "mdi:window-open-variant",
            "Window block",
            "Open windows in several rooms stopped the boiler.",
        ),
        (
            "mdi:alert-circle",
            "Problem",
            (
                "Something does not work (boiler, sensor, valve). Details in notifications and "
                "Repairs."
            ),
        ),
        (
            "mdi:account-multiple",
            "Who is home",
            'People of the presence the heating uses. "5 minutes ago" shows who just left.',
        ),
        (
            "mdi:thermostat",
            "Temperature (room)",
            (
                "Current temperature, room mode (auto, manual, off), target and preset. A manual "
                "change stays; back to auto in one tap."
            ),
        ),
        (
            "mdi:text",
            "Room sentence",
            "Why the room has its target, who is home and the house schedule.",
        ),
        (
            "mdi:pipe-valve",
            "Valve",
            "Position of the radiator valve: open, opening, closing, closed.",
        ),
        ("mdi:gauge", "Demand (room)", "How many percent of heat the room wants."),
        (
            "mdi:calendar-clock",
            "Schedule (room)",
            ("The room's own schedule, only when it has one. Editing it changes only this room."),
        ),
        (
            "mdi:ghost-outline",
            "Shadow",
            (
                "The controller calculates everything but switches neither the boiler nor the "
                "valves."
            ),
        ),
    ],
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
ROOM_HVAC_MODES = ["auto", "heat", "off"]
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
    # Presence of the household, when configured (FR-SCH-02).
    cfg = runtime.controller.cfg
    if cfg.house_presence_entity:
        badges.insert(2, _badge(cfg.house_presence_entity, text["presence"]))
    if cfg.long_away_entity:
        badges.append(
            _badge(
                cfg.long_away_entity,
                text["long_away"],
                color="blue",
                visibility=_when_on(cfg.long_away_entity),
            )
        )
    # Fixed order: one row of control blocks, the shadow or demo note across the
    # whole width (it ends the row, so rooms never mix with the control blocks),
    # a divider and the rooms.
    sections = [
        _system_section(runtime, ids, text),
        _boiler_section(ids, text),
        _boiler_operation_section(runtime, ids, text),
    ]
    if runtime.layout is not None:
        sections.append({**_demo_section(runtime, text), "column_span": 3})
    else:
        sections.append(_shadow_section(shadow, text))
    sections.append(_divider(text["rooms_settings"], "mdi:home-thermometer-outline"))
    sections.extend(_room_section(runtime, ids, text, room) for room in runtime.rooms)
    sections.append(_legend_section(runtime, text))
    return {
        "title": text["overview"],
        "path": "prehled",
        "icon": "mdi:radiator",
        "type": "sections",
        "max_columns": 3,
        "badges": badges,
        "sections": sections,
    }


def _divider(text: str, icon: str) -> dict:
    """Full-width section with a horizontal line and a title."""
    return {
        "type": "grid",
        "column_span": 3,
        "cards": [
            {"type": "markdown", "content": "<hr>", "text_only": True, "grid_options": FULL},
            _heading(text, icon, heading_style="title", grid_options=FULL),
        ],
    }


def _legend_section(runtime: HydronicHeatingRuntime, text: dict[str, str]) -> dict:
    """Explain each tile, with the same icon as on the dashboard."""
    lang = "cs" if (runtime.hass.config.language or "").startswith("cs") else "en"
    rows = "\n".join(
        f'| <ha-icon icon="{icon}"></ha-icon> | **{name}** | {meaning} |'
        for icon, name, meaning in LEGEND[lang]
    )
    return {
        "type": "grid",
        "column_span": 3,
        "cards": [
            {"type": "markdown", "content": "<hr>", "text_only": True, "grid_options": FULL},
            _heading(text["legend"], "mdi:help-circle-outline", grid_options=FULL),
            {
                "type": "markdown",
                "content": "| | | |\n|---|---|---|\n" + rows,
                "text_only": True,
                "grid_options": FULL,
            },
        ],
    }


def _shadow_section(shadow: str, text: dict[str, str]) -> dict:
    """Warning that nothing is switched; shown only in shadow mode (not in the demo)."""
    return {
        "type": "grid",
        "column_span": 3,
        "visibility": _when_on(shadow),
        "cards": [
            {
                "type": "markdown",
                "content": f'<ha-alert alert-type="warning">{text["shadow_banner"]}</ha-alert>',
                "text_only": True,
                "grid_options": FULL,
            }
        ],
    }


def _system_section(runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str]) -> dict:
    sid = ids.system
    durations = runtime.controller.cfg.manual_durations
    cards: list[dict[str, Any]] = [_heading(text["heating"], "mdi:radiator")]
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
        _full(
            sid("select", "heating_season"),
            text["season"],
            features=[{"type": "select-options"}],
        ),
    ]
    if schedule := runtime.controller.cfg.house_schedule_entity:
        # On = comfort, off = setback; the next change shows in the tile.
        cards.append(_full(schedule, text["house_schedule"], state_content=["state", "next_event"]))
    cards += [
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
        ],
    }


def _boiler_operation_section(
    runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str]
) -> dict:
    """Command, demand, statistics and blocks of the boiler; who is home below."""
    sid = ids.system
    cards = [
        _heading(text["boiler_operation"], "mdi:chart-box-outline"),
        _half(sid("binary_sensor", "boiler_command"), text["boiler_command"], color="deep-orange"),
        _half(sid("binary_sensor", "heat_demand"), text["heat_demand"], color="orange"),
        _half(sid("sensor", "boiler_duty"), text["boiler_duty"]),
        _half(sid("sensor", "boiler_starts_today"), text["boiler_starts_today"]),
        _half(sid("sensor", "duty_limit"), text["duty_limit"]),
        _half(sid("binary_sensor", "heating_season"), text["season"]),
        _half(sid("sensor", "outdoor_mean_4h"), text["outdoor_mean_4h"]),
        _half(sid("binary_sensor", "window_block"), text["window_block"]),
        _half(sid("binary_sensor", "problem"), text["problem"], color="red"),
    ]
    if people := _people(runtime):
        # Person -> home or away; "Away · 5 minutes ago" shows who just left.
        cards.append(_heading(text["who_home"], "mdi:account-multiple", subtitle=True))
        cards.extend(
            _half(person, state_content=["state", "last_changed"], color="green")
            for person in people
        )
    return {"type": "grid", "cards": cards}


def _people(runtime: HydronicHeatingRuntime) -> list[str]:
    """Entities of the people behind the presence entities the heating uses.

    A group lists its members in `entity_id`; a single person or sensor is itself.
    No link to a particular presence module.
    """
    cfg = runtime.controller.cfg
    sources = [cfg.house_presence_entity, *(r.presence_entity for r in runtime.rooms)]
    found: list[str] = []
    for source in sources:
        if not source:
            continue
        state = runtime.hass.states.get(source)
        members = state.attributes.get("entity_id") if state else None
        candidates = list(members) if isinstance(members, list | tuple) else [source]
        for entity_id in candidates:
            if entity_id not in found and not entity_id.startswith("zone."):
                found.append(entity_id)
    return found


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
    climate = ids.room("climate", room, "")
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
        # 1. Controls: back to auto in one tap, target temperature, presets.
        _full(
            climate,
            text["temperature"],
            state_content=["current_temperature", "hvac_action"],
            features=[
                {"type": "climate-hvac-modes", "style": "icons", "hvac_modes": ROOM_HVAC_MODES},
                {"type": "target-temperature"},
                {"type": "climate-preset-modes", "style": "dropdown", "preset_modes": PRESETS},
            ],
        ),
        # 2. Display only: why, who is home, valve, demand.
        {
            "type": "markdown",
            "content": _room_explanation(runtime, text, room, climate),
            "text_only": True,
        },
    ]
    # The valve on the radiator: its position modelled from the head command and the
    # travel time, so "open" means open regardless of NO/NC heads.
    valve_name = text["valve"] if len(room.valves) == 1 else text["valves"]
    cards.append(_full(ids.room("sensor", room, "valve_state"), valve_name))
    cards.append(
        _full(
            ids.room("sensor", room, "demand"),
            text["demand"],
            features=[{"type": "bar-gauge", "min": 0, "max": 100}],
            features_position="inline",
        )
    )
    if demo is not None and layout is not None and layout.house:
        cards.append(_heading(text["simulation"], "mdi:test-tube", subtitle=True))
        cards.append(_half(demo.window.entity_id, text["window"], color="blue"))
        cards.append(_half(demo.sensor_fault.entity_id, text["demo_sensor_fault"], color="red"))
    # 3. The room's own schedule, editable; the house schedule is only a line above.
    if room.schedule_entity:
        cards.append(
            _full(
                room.schedule_entity, text["schedule_room"], state_content=["state", "next_event"]
            )
        )
    return {"type": "grid", "cards": cards}


def _names_home(entity_id: str, nobody: str) -> str:
    """Jinja: names of who is home behind a presence entity.

    `people` (a presence module) lists names; any entity with members in `entity_id`
    (groups) is expanded; a single person or sensor is its own name when home.
    """
    return (
        f"{{%- set people = state_attr('{entity_id}', 'people') -%}}"
        "{%- if people is iterable and people is not string -%}"
        f"{{{{ people | join(', ') if people else '{nobody}' }}}}"
        "{%- else -%}"
        f"{{%- set members = state_attr('{entity_id}', 'entity_id') -%}}"
        "{%- set targets = members if members is iterable and members is not string"
        f" else ['{entity_id}'] -%}}"
        "{%- set home = expand(targets) | selectattr('state', 'in', ['on', 'home'])"
        " | map(attribute='name') | list -%}"
        f"{{{{ home | join(', ') if home else '{nobody}' }}}}"
        "{%- endif -%}"
    )


def _room_explanation(
    runtime: HydronicHeatingRuntime, text: dict[str, str], room: RoomConfig, climate: str
) -> str:
    """Markdown: why the target, who is home (by name) and the house schedule."""
    cfg = runtime.controller.cfg
    lines = [f"{{{{ state_attr('{climate}', 'target_detail') }}}}"]
    presence = room.presence_entity or cfg.house_presence_entity
    if presence:
        label = text["home"] if room.presence_entity else text["home_house"]
        lines.append(f"**{label}:** {_names_home(presence, text['nobody'])}")
    if not room.schedule_entity and cfg.house_schedule_entity:
        schedule = cfg.house_schedule_entity
        lines.append(
            f"**{text['schedule_house_line']}:** "
            f"{{{{ '{text['on']}' if is_state('{schedule}', 'on') else '{text['off']}' }}}}"
            f"{{%- set nxt = state_attr('{schedule}', 'next_event') -%}}"
            f"{{%- if nxt %}}, {text['next_change']} "
            "{{ as_timestamp(nxt) | timestamp_custom('%H:%M') }}{% endif %}"
        )
    return "  \n".join(lines)


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
        {"entity": sid("binary_sensor", "heating_season"), "name": text["season"]},
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
                {"entity": sid("sensor", "outdoor_mean_4h"), "name": text["outdoor_mean_4h"]},
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

    valve_entities = [
        {"entity": ids.room("sensor", room, "valve_state"), "name": room.name} for room in rooms
    ]
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
