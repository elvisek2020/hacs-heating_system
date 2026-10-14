"""Dashboard built from the configuration (service `generate_dashboard`).

Only built-in cards. Overview: status badges, system and boiler sections and
one compact section per room. History: one clear chart per topic, units are
never mixed in one chart. Legend: a subview opened from a badge. Tiles of
features that are not configured are left out; colors follow the meaning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)

from .card import CARD_TYPE
from .const import DOMAIN, ENTITY_PREFIX

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

    from .core.model import RoomConfig
    from .runtime import HydronicHeatingRuntime

TEXTS: dict[str, dict[str, str]] = {
    "cs": {
        "title": "Topení",
        "overview": "Přehled",
        "history": "Grafy",
        "scheme": "Schéma",
        "heating": "Topení",
        "boiler": "Kotel",
        "boiler_operation": "Provoz kotle",
        "rooms_settings": "Místnosti – individuální nastavení",
        "season": "Topná sezóna",
        "outdoor_mean_4h": "Venku (průměr 4 h)",
        "outdoor_mean_limit": "Venku – průměr 4 h (hranice {limit} °C)",
        "who_home": "Kdo je doma",
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
        "boiler_actual": "Kotel (skutečný stav)",
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
        "flow_temperature": "Teplota vody",
        "flow_setpoint": "Teplota vody (křivka)",
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
        "pipe": "Trubka",
        "comfort": "Komfort",
        "eco": "ECO",
        "away": "Pryč",
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
        "outdoor_chart": "Venkovní teplota",
        "boiler_stats": "Kotel po dnech",
        "duty_per_day": "Střída kotle (průměr za den)",
        "starts_per_day": "Starty kotle za den",
        "valves_timeline": "Ventily",
    },
    "en": {
        "title": "Heating",
        "overview": "Overview",
        "history": "History",
        "scheme": "Scheme",
        "heating": "Heating",
        "boiler": "Boiler",
        "boiler_operation": "Boiler operation",
        "rooms_settings": "Rooms – individual settings",
        "season": "Heating season",
        "outdoor_mean_4h": "Outdoor (4 h mean)",
        "outdoor_mean_limit": "Outdoor – 4 h mean (limit {limit} °C)",
        "who_home": "Who is home",
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
        "boiler_actual": "Boiler (actual state)",
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
        "flow_temperature": "Flow temperature",
        "flow_setpoint": "Flow temperature (curve)",
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
        "pipe": "Pipe",
        "comfort": "Comfort",
        "eco": "Eco",
        "away": "Away",
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
        "outdoor_chart": "Outdoor temperature",
        "boiler_stats": "Boiler per day",
        "duty_per_day": "Boiler duty (daily mean)",
        "starts_per_day": "Boiler starts per day",
        "valves_timeline": "Valves",
    },
}

# Legend (a subview): feature key, icon as on the dashboard, name, meaning. Rows
# of features that are not configured are left out (see _Shown.has).
LEGEND: dict[str, list[tuple[str, str, str, str]]] = {
    "cs": [
        (
            "",
            "mdi:state-machine",
            "Stav",
            "Stav řízení: automaticky, pryč, vypnuto, mimo sezónu, manuál nebo porucha.",
        ),
        (
            "house_presence",
            "mdi:account-multiple",
            "Doma",
            (
                "Přítomnost domácnosti, kterou topení používá (například víc lidí doma). "
                "Vypnuto = místnosti bez vlastní přítomnosti jedou na teplotu nepřítomnosti."
            ),
        ),
        (
            "long_away",
            "mdi:bag-suitcase",
            "Dlouhodobě pryč",
            (
                "Domácnost je dlouhodobě pryč (víkend, dovolená): všechny místnosti mají "
                "teplotu Pryč. Odznak se ukáže jen tehdy."
            ),
        ),
        (
            "",
            "mdi:thermostat",
            "Systém",
            "Režim celé soustavy: vypnuto, automaticky, nebo topit (manuál).",
        ),
        (
            "",
            "mdi:radiator",
            "Režim",
            "Automaticky, manuál, vypnuto nebo pryč (teploty Pryč ve všech místnostech).",
        ),
        (
            "",
            "mdi:calendar-range",
            "Topná sezóna",
            (
                "Automaticky podle 4h průměru venkovní teploty, nebo ručně. Mimo sezónu se "
                "netopí, protimrazová ochrana platí."
            ),
        ),
        (
            "house_schedule",
            "mdi:calendar-clock",
            "Rozvrh domu",
            "Zapnuto = komfort, vypnuto = útlum. Platí pro místnosti bez vlastního rozvrhu.",
        ),
        (
            "",
            "mdi:fire",
            "Manuální topení",
            "Topí na zvolenou dobu. Konec manuálu a Stop se ukážou jen během manuálu.",
        ),
        (
            "",
            "mdi:information-outline",
            "Proč",
            "Proč kotel topí nebo stojí. Pod ním věta s vysvětlením.",
        ),
        (
            "",
            "mdi:timer-sand",
            "Další změna",
            "Kdy skončí časové pravidlo (minimální běh, pauza, doběh). Jen když nějaké platí.",
        ),
        ("", "mdi:gauge", "Celkový požadavek", "Vážený požadavek všech místností na teplo v %."),
        (
            "flow",
            "mdi:thermometer-water",
            "Teplota vody",
            (
                "Měřená teplota vody od kotle. Když kotel běží a voda se neohřeje, ohlásí se "
                "porucha „kotel běží, ale netopí“."
            ),
        ),
        (
            "duty",
            "mdi:thermometer-water",
            "Teplota vody (křivka)",
            "Teplota vody podle topné křivky, podle ní se omezuje střída kotle.",
        ),
        (
            "",
            "mdi:thermometer",
            "Venku",
            "Aktuální venkovní teplota z čidla, případně z předpovědi počasí.",
        ),
        (
            "",
            "mdi:thermometer-lines",
            "Venku (průměr 4 h)",
            (
                "Průměr venkovní teploty za 4 hodiny, podle něj začíná a končí topná sezóna. "
                "Hranice je v názvu dlaždice."
            ),
        ),
        ("", "mdi:play", "Povel kotli", "Zda integrace kotli povoluje topit."),
        (
            "feedback",
            "mdi:fire",
            "Kotel (skutečný stav)",
            (
                "Zda kotel opravdu běží, podle zpětné vazby. Při povelu může chvíli stát, "
                "když má vodu nahřátou. Odznak Kotel v horní liště ukazuje tento stav."
            ),
        ),
        ("", "mdi:fire-alert", "Požadavek na teplo", "Zda místnosti teplo chtějí."),
        (
            "",
            "mdi:alert-circle",
            "Porucha",
            (
                "Něco nefunguje (kotel, čidlo, ventil, kotel netopí). Podrobnosti "
                "v oznámeních a v Opravách."
            ),
        ),
        (
            "",
            "mdi:radiator",
            "Topná sezóna (stav)",
            "Zda je topná sezóna. Začne hned pod hranicí, skončí po 3 celých dnech nad ní.",
        ),
        ("", "mdi:counter", "Starty dnes", "Počet startů kotle od půlnoci."),
        (
            "",
            "mdi:percent-outline",
            "Střída 24 h",
            "Kolik procent posledních 24 hodin kotel běžel.",
        ),
        (
            "duty",
            "mdi:sine-wave",
            "Omezení střídy",
            "Kolik procent cyklu smí kotel běžet podle topné křivky.",
        ),
        (
            "airing",
            "mdi:window-open-variant",
            "Okna",
            (
                "Počet místností s otevřeným oknem nebo s větráním. Odznak se ukáže, jen když "
                "nějaké je."
            ),
        ),
        (
            "windows",
            "mdi:window-open-variant",
            "Blokace okny",
            "Otevřená okna ve více místnostech zastavila kotel.",
        ),
        (
            "people",
            "mdi:account-multiple",
            "Kdo je doma",
            (
                "Osoby z přítomnosti, kterou topení používá, bez skupin. „Před 5 minutami“ "
                "ukazuje, kdo právě odešel."
            ),
        ),
        (
            "",
            "mdi:thermostat",
            "Teplota (místnost)",
            (
                "Aktuální teplota, režim místnosti, cíl a předvolba. Ručně (ikona ruky) = "
                "pevný cíl bez rozvrhu a přítomnosti; nastaví ho −/+ na termostatu nebo výběr "
                "předvolby, zpět tlačítkem Automaticky. Proč má místnost svůj cíl, ukazují "
                "atributy termostatu a deník."
            ),
        ),
        ("", "mdi:gauge", "Požadavek (místnost)", "Kolik procent tepla místnost chce."),
        (
            "",
            "mdi:pipe-valve",
            "Ventil",
            "Poloha ventilu radiátoru: otevřeno, otevírá se, zavírá se, zavřeno.",
        ),
        (
            "valve_temps",
            "mdi:pipe",
            "Trubka",
            (
                "Teplota trubky u ventilu. Když kotel topí, otevřený ventil trubku ohřeje a "
                "zavřený ne. U Ventilu je pak výsledek kontroly: funguje, neotvírá, nezavírá."
            ),
        ),
        (
            "airing",
            "mdi:window-open",
            "Okno (u místnosti)",
            (
                "Otevřené okno podle kontaktu, nebo větrání poznané podle rychlého poklesu "
                "teploty. Místnost netopí a ventil je zavřený."
            ),
        ),
        (
            "",
            "mdi:sofa",
            "Komfort",
            (
                "Trvalá komfortní teplota místnosti pro automatiku (rozvrh zapnuto, někdo "
                "doma). Změna platí hned a místnost zůstává v automatice."
            ),
        ),
        (
            "",
            "mdi:leaf",
            "ECO",
            (
                "Trvalá útlumová teplota (předvolba ECO) pro automatiku (rozvrh vypnuto, "
                "nikdo doma). Nejde nastavit nad komfort."
            ),
        ),
        (
            "own_schedule",
            "mdi:calendar-clock",
            "Rozvrh (místnost)",
            "Vlastní plán místnosti, jen když ho místnost má. Úprava mění jen tuto místnost.",
        ),
        (
            "",
            "mdi:ghost-outline",
            "Shadow",
            "Řízení všechno počítá, ale kotel ani ventily nespíná.",
        ),
    ],
    "en": [
        (
            "",
            "mdi:state-machine",
            "State",
            "Control state: auto, away, off, off season, manual or fault.",
        ),
        (
            "house_presence",
            "mdi:account-multiple",
            "Home",
            (
                "Presence of the household the heating uses (for example several people home). "
                "Off = rooms without their own presence use the absence temperature."
            ),
        ),
        (
            "long_away",
            "mdi:bag-suitcase",
            "Long absence",
            (
                "The household is away for long (weekend, holiday): all rooms have the away "
                "temperature. The badge shows only then."
            ),
        ),
        ("", "mdi:thermostat", "System", "Mode of the whole system: off, auto, or heat (manual)."),
        (
            "",
            "mdi:radiator",
            "Mode",
            "Auto, manual, off or away (away temperatures in all rooms).",
        ),
        (
            "",
            "mdi:calendar-range",
            "Heating season",
            (
                "Automatic by the 4 h mean outdoor temperature, or by hand. No heating off "
                "season, frost protection applies."
            ),
        ),
        (
            "house_schedule",
            "mdi:calendar-clock",
            "House schedule",
            "On = comfort, off = setback. For rooms without their own schedule.",
        ),
        (
            "",
            "mdi:fire",
            "Manual heating",
            "Heats for the chosen time. Manual end and Stop show only during manual heating.",
        ),
        (
            "",
            "mdi:information-outline",
            "Why",
            "Why the boiler heats or stands. A sentence below explains it.",
        ),
        (
            "",
            "mdi:timer-sand",
            "Next change",
            "When a time rule ends (minimum run, pause, overrun). Only while one applies.",
        ),
        ("", "mdi:gauge", "Total demand", "Weighted heat demand of all rooms in %."),
        (
            "flow",
            "mdi:thermometer-water",
            "Flow temperature",
            (
                "Measured water temperature from the boiler. When the boiler runs and the water "
                'does not warm up, the problem "boiler runs but does not heat" is reported.'
            ),
        ),
        (
            "duty",
            "mdi:thermometer-water",
            "Flow temperature (curve)",
            "Water temperature by the heating curve; the boiler duty is limited by it.",
        ),
        (
            "",
            "mdi:thermometer",
            "Outdoor",
            "Current outdoor temperature from the sensor, or from the weather forecast.",
        ),
        (
            "",
            "mdi:thermometer-lines",
            "Outdoor (4 h mean)",
            (
                "Mean outdoor temperature of 4 hours; the heating season starts and ends by it. "
                "The limit is in the tile name."
            ),
        ),
        ("", "mdi:play", "Boiler command", "Whether the integration lets the boiler heat."),
        (
            "feedback",
            "mdi:fire",
            "Boiler (actual state)",
            (
                "Whether the boiler really runs, by its feedback. With the command on it may "
                "stand for a while when its water is hot. The Boiler badge on top shows it."
            ),
        ),
        ("", "mdi:fire-alert", "Heat demand", "Whether the rooms want heat."),
        (
            "",
            "mdi:alert-circle",
            "Problem",
            (
                "Something does not work (boiler, sensor, valve, no heat). Details in "
                "notifications and Repairs."
            ),
        ),
        (
            "",
            "mdi:radiator",
            "Heating season (state)",
            (
                "Whether it is the heating season. Starts at once below the limit, ends after 3 "
                "whole days above it."
            ),
        ),
        ("", "mdi:counter", "Starts today", "Boiler starts since midnight."),
        (
            "",
            "mdi:percent-outline",
            "Duty 24 h",
            "How many percent of the last 24 hours the boiler ran.",
        ),
        (
            "duty",
            "mdi:sine-wave",
            "Duty limit",
            "How many percent of a cycle the boiler may run by the curve.",
        ),
        (
            "airing",
            "mdi:window-open-variant",
            "Windows",
            "Rooms with an open window or airing. The badge shows only when there is one.",
        ),
        (
            "windows",
            "mdi:window-open-variant",
            "Window block",
            "Open windows in several rooms stopped the boiler.",
        ),
        (
            "people",
            "mdi:account-multiple",
            "Who is home",
            (
                'People of the presence the heating uses, without groups. "5 minutes ago" '
                "shows who just left."
            ),
        ),
        (
            "",
            "mdi:thermostat",
            "Temperature (room)",
            (
                "Current temperature, room mode, target and preset. Manual (hand icon) = a fixed "
                "target without schedule and presence; set by -/+ on the thermostat or by a "
                "preset, back with the Auto button. The thermostat attributes and the logbook "
                "tell why the room has its target."
            ),
        ),
        ("", "mdi:gauge", "Demand (room)", "How many percent of heat the room wants."),
        (
            "",
            "mdi:pipe-valve",
            "Valve",
            "Position of the radiator valve: open, opening, closing, closed.",
        ),
        (
            "valve_temps",
            "mdi:pipe",
            "Pipe",
            (
                "Temperature of the pipe at the valve. While the boiler heats, an open valve "
                "warms its pipe and a closed one does not. The Valve tile then shows the check: "
                "works, does not open, does not close."
            ),
        ),
        (
            "airing",
            "mdi:window-open",
            "Window (room)",
            (
                "An open window by its contact, or airing noticed by a fast temperature drop. "
                "The room does not heat and its valve is closed."
            ),
        ),
        (
            "",
            "mdi:sofa",
            "Comfort",
            (
                "Lasting comfort temperature of the room for auto (schedule on, someone home). "
                "Applies at once; the room stays in auto."
            ),
        ),
        (
            "",
            "mdi:leaf",
            "Eco",
            (
                "Lasting setback temperature for auto (schedule off, nobody home). Cannot be set "
                "above comfort."
            ),
        ),
        (
            "own_schedule",
            "mdi:calendar-clock",
            "Schedule (room)",
            "The room's own schedule, only when it has one. Editing it changes only this room.",
        ),
        (
            "",
            "mdi:ghost-outline",
            "Shadow",
            (
                "The controller calculates everything but switches neither the boiler nor the "
                "valves."
            ),
        ),
    ],
}

# Colors by meaning (palette approved by the user). Two-state entities light up
# only when active; room thermostats keep the colors of Home Assistant.
HEAT = "deep-orange"  # boiler: command, why
TIME = "orange"  # heat demand, next change, end of manual
DEMAND = "amber"  # demands, heating season
WATER = "red"  # flow temperature
PROBLEM = "red"
OUTDOOR = "light-blue"
OUTDOOR_MEAN = "blue"
VALVE = "cyan"  # valves, open windows
PEOPLE = "green"
CONTROL = "indigo"  # state and mode of the system
LIMIT = "purple"  # schedules, duty limit
STATS = "teal"  # duty 24 h
AUX = "blue-grey"  # starts today, long absence
MISC = "grey"  # shadow, legend
COMFORT = "orange"  # room temperature settings
ECO = "teal"

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
# The frontend draws a flame for `heat`, which reads as "heating now". The room's
# manual mode ("Manual", hand icon) shows in the state; one tap goes back to auto.
ROOM_HVAC_MODES = ["auto", "off"]
HALF = {"columns": 6}
FULL = {"columns": "full"}
LEGEND_PATH = "vysvetlivky"
FLOW_ICON = "mdi:thermometer-water"
BOILER_ICON = "mdi:fire"
PIPE_ICON = "mdi:pipe"
# Attributes of entities that stand for several people (groups, counts).
AGGREGATE_ATTRS = ("entity_id", "people", "count")
PRESENCE_CLASSES = ("presence", "occupancy")


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


def _language(runtime: HydronicHeatingRuntime) -> str:
    return "cs" if (runtime.hass.config.language or "").startswith("cs") else "en"


def _number(value: float, lang: str) -> str:
    text = f"{value:g}"
    return text.replace(".", ",") if lang == "cs" else text


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


@dataclass
class _Shown:
    """Configured features; tiles and legend rows of the others are left out."""

    flow: str | None
    feedback: str | None
    duty: bool
    windows: bool
    airing: bool
    house_schedule: str | None
    own_schedule: bool
    valve_temps: bool = False
    house_presence: bool = False
    long_away: bool = False
    people: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def of(cls, runtime: HydronicHeatingRuntime) -> _Shown:
        cfg = runtime.controller.cfg
        return cls(
            # The real sensor also in the demo: the real boiler keeps running.
            flow=runtime.real_system_config().heat_source.flow_temp_entity,
            # Not in the demo: there the boiler is virtual and has no feedback.
            feedback=cfg.heat_source.feedback_entity,
            duty=cfg.duty_enabled,
            windows=any(room.cfg.windows for room in runtime.controller.rooms.values()),
            valve_temps=any(v.temp_entity for room in runtime.rooms for v in room.valves),
            # Window contacts or airing detection (FR-WIN-06) in any room.
            airing=any(
                room.cfg.windows or room.cfg.vent_detect
                for room in runtime.controller.rooms.values()
            ),
            house_schedule=cfg.house_schedule_entity,
            own_schedule=any(room.schedule_entity for room in runtime.rooms),
            house_presence=cfg.house_presence_entity is not None,
            long_away=cfg.long_away_entity is not None,
            people=_people(runtime),
        )

    def has(self, feature: str) -> bool:
        """Whether a legend row of this feature belongs to the dashboard."""
        return {
            "": True,
            "flow": self.flow is not None,
            "feedback": self.feedback is not None,
            "duty": self.duty,
            "windows": self.windows,
            "airing": self.airing,
            "valve_temps": self.valve_temps,
            "house_schedule": self.house_schedule is not None,
            "own_schedule": self.own_schedule,
            "house_presence": self.house_presence,
            "long_away": self.long_away,
            "people": bool(self.people),
        }[feature]


def build_dashboard(runtime: HydronicHeatingRuntime) -> dict[str, Any]:
    """Return a Lovelace dashboard (sections views) for this installation."""
    text = TEXTS[_language(runtime)]
    ids = _Ids(runtime)
    shown = _Shown.of(runtime)
    return {
        "title": text["title"],
        "views": [
            _overview(runtime, ids, text, shown),
            _scheme_view(runtime, ids, text, shown),
            _history(runtime, ids, text, shown),
            _legend_view(runtime, text, shown),
        ],
    }


# --- Overview ---------------------------------------------------------------


def _overview(
    runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str], shown: _Shown
) -> dict:
    sid = ids.system
    cfg = runtime.controller.cfg
    problem = sid("binary_sensor", "problem")
    shadow = sid("switch", "shadow_mode")
    hold = sid("sensor", "boiler_hold_ends_at")
    state = sid("sensor", "state")
    badges = [
        _badge(state, text["state"], color=CONTROL),
        # The boiler: its actual state by the feedback, else the command.
        _badge(shown.feedback, text["boiler"], color=HEAT, icon=BOILER_ICON)
        if shown.feedback
        else _badge(sid("binary_sensor", "boiler_command"), text["boiler"], color=HEAT),
    ]
    # Presence of the household, when configured (FR-SCH-02).
    if cfg.house_presence_entity:
        badges.append(
            _badge(
                cfg.house_presence_entity,
                text["presence"],
                color=PEOPLE,
                icon="mdi:account-multiple",
            )
        )
    badges += [
        _badge(sid("sensor", "boiler_reason"), text["boiler_reason"], color=HEAT),
        _badge(hold, text["boiler_hold"], color=TIME, visibility=_when_known(hold)),
        _badge(sid("sensor", "outdoor_temperature"), text["outdoor"], color=OUTDOOR),
    ]
    # The measured water temperature; the curve only when the boiler duty follows it.
    if shown.flow:
        badges.append(_badge(shown.flow, text["flow_temperature"], color=WATER, icon=FLOW_ICON))
    elif shown.duty:
        badges.append(_badge(sid("sensor", "flow_setpoint"), text["flow_setpoint"], color=WATER))
    badges.append(_badge(sid("sensor", "demand_total"), text["demand_total"], color=DEMAND))
    if shown.airing:
        windows = sid("sensor", "open_windows")
        badges.append(
            _badge(
                windows,
                text["open_windows"],
                color=VALVE,
                visibility=[{"condition": "numeric_state", "entity": windows, "above": 0}],
            )
        )
    badges += [
        _badge(problem, text["problem"], color=PROBLEM, visibility=_when_on(problem)),
        _badge(shadow, text["shadow"], color=MISC, visibility=_when_on(shadow)),
    ]
    if cfg.long_away_entity:
        badges.append(
            _badge(
                cfg.long_away_entity,
                text["long_away"],
                color=AUX,
                icon="mdi:bag-suitcase",
                visibility=_when_on(cfg.long_away_entity),
            )
        )
    # The legend opens as a subview; the path is relative to this dashboard.
    badges.append(
        {
            "type": "entity",
            "entity": state,
            "name": text["legend"],
            "icon": "mdi:information-outline",
            "color": MISC,
            "show_name": False,
            "show_state": True,
            "state_content": "name",
            "tap_action": {"action": "navigate", "navigation_path": LEGEND_PATH},
        }
    )
    # Fixed order: one row of control blocks, the shadow or demo note across the
    # whole width (it ends the row, so rooms never mix with the control blocks),
    # a divider and the rooms.
    sections = [
        _system_section(runtime, ids, text),
        _boiler_section(runtime, ids, text, shown),
        _boiler_operation_section(ids, text, shown),
    ]
    if runtime.layout is not None:
        sections.append({**_demo_section(runtime, text), "column_span": 3})
    else:
        sections.append(_shadow_section(shadow, text))
    sections.append(_divider(text["rooms_settings"], "mdi:home-thermometer-outline"))
    sections.extend(_room_section(runtime, ids, text, room, shown) for room in runtime.rooms)
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
        _tile(
            sid("select", "system_mode"),
            text["mode"],
            color=CONTROL,
            features=[{"type": "select-options"}],
        ),
        _full(
            sid("select", "heating_season"),
            text["season"],
            color=DEMAND,
            features=[{"type": "select-options"}],
        ),
    ]
    if schedule := runtime.controller.cfg.house_schedule_entity:
        # On = comfort, off = setback; the next change shows in the tile.
        cards.append(
            _full(
                schedule,
                text["house_schedule"],
                color=LIMIT,
                state_content=["state", "next_event"],
            )
        )
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
    cards.append(
        _half(
            sid("sensor", "manual_ends_at"),
            text["manual_ends_at"],
            color=TIME,
            visibility=running,
        )
    )
    cards.append(
        _half(
            stop,
            text["stop"],
            hide_state=True,
            color=PROBLEM,
            tap_action=_press(stop),
            icon_tap_action=_press(stop),
            visibility=running,
        )
    )
    return {"type": "grid", "cards": cards}


def _boiler_section(
    runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str], shown: _Shown
) -> dict:
    sid = ids.system
    trend = {"type": "trend-graph", "hours_to_show": 24}
    reason = sid("sensor", "boiler_reason")
    hold = sid("sensor", "boiler_hold_ends_at")
    limit = _number(runtime.controller.cfg.heating_limit, _language(runtime))
    cards: list[dict[str, Any]] = [
        _heading(text["boiler"], "mdi:water-boiler"),
        # Why the boiler is on or off, and when that changes (FR-SAFE-07).
        _full(reason, text["boiler_reason"], color=HEAT, state_content=["state", "last_changed"]),
        _full(hold, text["boiler_hold"], color=TIME, visibility=_when_known(hold)),
        {
            "type": "markdown",
            "content": f"{{{{ state_attr('{reason}', 'detail') }}}}",
            "text_only": True,
        },
        _full(
            sid("sensor", "demand_total"),
            text["demand_total"],
            color=DEMAND,
            features=[{"type": "bar-gauge", "min": 0, "max": 100}],
            features_position="inline",
        ),
    ]
    if shown.flow:
        cards.append(
            _full(
                shown.flow,
                text["flow_temperature"],
                color=WATER,
                icon=FLOW_ICON,
                features=[trend],
            )
        )
    if shown.duty:
        cards.append(
            _full(
                sid("sensor", "flow_setpoint"), text["flow_setpoint"], color=WATER, features=[trend]
            )
        )
    cards += [
        _full(
            sid("sensor", "outdoor_temperature"), text["outdoor"], color=OUTDOOR, features=[trend]
        ),
        _full(
            sid("sensor", "outdoor_mean_4h"),
            text["outdoor_mean_limit"].format(limit=limit),
            color=OUTDOOR_MEAN,
            features=[trend],
        ),
    ]
    return {"type": "grid", "cards": cards}


def _boiler_operation_section(ids: _Ids, text: dict[str, str], shown: _Shown) -> dict:
    """Boiler tiles by priority, only of configured features; who is home below."""
    sid = ids.system
    cards = [
        _heading(text["boiler_operation"], "mdi:chart-box-outline"),
        _half(sid("binary_sensor", "boiler_command"), text["boiler_command"], color=HEAT),
    ]
    if shown.feedback:
        cards.append(_half(shown.feedback, text["boiler_actual"], color=HEAT, icon=BOILER_ICON))
    cards += [
        _half(sid("binary_sensor", "heat_demand"), text["heat_demand"], color=TIME),
        _half(sid("sensor", "outdoor_mean_4h"), text["outdoor_mean_4h"], color=OUTDOOR_MEAN),
        _half(sid("binary_sensor", "problem"), text["problem"], color=PROBLEM),
    ]
    if shown.windows:
        cards.append(_half(sid("binary_sensor", "window_block"), text["window_block"], color=VALVE))
    cards += [
        _half(sid("binary_sensor", "heating_season"), text["season"], color=DEMAND),
        _half(sid("sensor", "boiler_starts_today"), text["boiler_starts_today"], color=AUX),
        _half(sid("sensor", "boiler_duty"), text["boiler_duty"], color=STATS),
    ]
    if shown.duty:
        cards.append(_half(sid("sensor", "duty_limit"), text["duty_limit"], color=LIMIT))
    if shown.people:
        # Person -> home or away; "Away · 5 minutes ago" shows who just left.
        cards.append(_heading(text["who_home"], "mdi:account-multiple", subtitle=True))
        cards.extend(
            _half(person, name, state_content=["state", "last_changed"], color=PEOPLE)
            for person, name in shown.people
        )
    return {"type": "grid", "cards": cards}


def _is_aggregate(state: State) -> bool:
    return any(key in state.attributes for key in AGGREGATE_ATTRS)


def _people(runtime: HydronicHeatingRuntime) -> list[tuple[str, str]]:
    """People behind the presence entities the heating uses, with their names.

    The house first, then the rooms. Groups and counts are left out: an HA group
    stands for its members (`entity_id`); a group or count of a presence module
    (`people`, `count`) stands for the people of the same integration. No link to a
    particular presence module.
    """
    hass = runtime.hass
    registry = er.async_get(hass)
    cfg = runtime.controller.cfg
    sources = [cfg.house_presence_entity, *(r.presence_entity for r in runtime.rooms)]
    found: list[str] = []

    def add(entity_id: str) -> None:
        state = hass.states.get(entity_id)
        if (
            entity_id not in found
            and not entity_id.startswith("zone.")
            and (state is None or not _is_aggregate(state))
        ):
            found.append(entity_id)

    for source in sources:
        if not source:
            continue
        state = hass.states.get(source)
        if state is None or not _is_aggregate(state):
            add(source)
            continue
        members = state.attributes.get("entity_id")
        if isinstance(members, list | tuple):
            for member in members:
                add(member)
        else:
            for person in _integration_people(hass, registry, source):
                add(person)
    return [(entity_id, _person_name(hass, registry, entity_id)) for entity_id in found]


def _integration_people(hass: HomeAssistant, registry: er.EntityRegistry, source: str) -> list[str]:
    """Presence sensors of single people from the integration of `source`."""
    entry = registry.async_get(source)
    if entry is None or entry.config_entry_id is None:
        return []
    found = []
    for candidate in er.async_entries_for_config_entry(registry, entry.config_entry_id):
        if (
            candidate.domain != "binary_sensor"
            or candidate.disabled_by is not None
            or (candidate.device_class or candidate.original_device_class) not in PRESENCE_CLASSES
        ):
            continue
        state = hass.states.get(candidate.entity_id)
        if state is not None and not _is_aggregate(state):
            found.append(candidate.entity_id)
    return found


def _person_name(hass: HomeAssistant, registry: er.EntityRegistry, entity_id: str) -> str:
    """Name of the person: the device of an entity named by its device, else the entity."""
    entry = registry.async_get(entity_id)
    if entry is not None and entry.device_id and entry.has_entity_name:
        device = dr.async_get(hass).async_get(entry.device_id)
        if device is not None and (name := device.name_by_user or device.name):
            return name
    state = hass.states.get(entity_id)
    return state.name if state is not None else entity_id


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
        _half(layout.boiler.entity_id, text["boiler_virtual"], color=HEAT),
    ]
    if real_boiler:
        cards.append(_half(real_boiler, text["boiler_real"], color=HEAT))
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
                color=OUTDOOR,
                features=[{"type": "numeric-input", "style": "buttons"}],
            )
        )
    return {"type": "grid", "cards": cards}


def _room_section(
    runtime: HydronicHeatingRuntime,
    ids: _Ids,
    text: dict[str, str],
    room: RoomConfig,
    shown: _Shown,
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
    controlled = runtime.controller.rooms.get(room.room_id)
    badges: list[dict[str, Any]] = []
    if controlled is not None and (controlled.cfg.windows or controlled.cfg.vent_detect):
        badges.append(
            {
                "type": "entity",
                "entity": window,
                "show_state": False,
                "color": VALVE,
                "visibility": _when_on(window),
            }
        )
    badges.append(
        {
            "type": "entity",
            "entity": problem,
            "show_state": False,
            "color": PROBLEM,
            "visibility": _when_on(problem),
        }
    )
    cards: list[dict[str, Any]] = [
        _heading(room.name, room_icon(room.slug), badges=badges),
        # 1. Controls: back to auto in one tap, target temperature, presets. Why the
        # room has its target is in the thermostat attributes and the logbook.
        _full(
            climate,
            text["temperature"],
            state_content=["current_temperature", "state", "hvac_action"],
            features=[
                {"type": "climate-hvac-modes", "style": "icons", "hvac_modes": ROOM_HVAC_MODES},
                {"type": "target-temperature"},
                {"type": "climate-preset-modes", "style": "dropdown", "preset_modes": PRESETS},
            ],
        ),
    ]
    cards += [
        # 2. Display only: the demand (the cause), then the valve (the result).
        _full(
            ids.room("sensor", room, "demand"),
            text["demand"],
            color=DEMAND,
            features=[{"type": "bar-gauge", "min": 0, "max": 100}],
            features_position="inline",
        ),
    ]
    # The valve on the radiator: its position modelled from the head command and the
    # travel time, so "open" means open regardless of NO/NC heads.
    valve_name = text["valve"] if len(room.valves) == 1 else text["valves"]
    pipes = [valve.temp_entity for valve in room.valves if valve.temp_entity]
    if pipes:
        # FR-SAFE-09: the valve with the result of its pipe check, the pipe next to it.
        cards.append(
            _half(
                ids.room("sensor", room, "valve_state"),
                valve_name,
                color=VALVE,
                state_content=["state", "check"],
            )
        )
        cards.extend(_half(pipe, text["pipe"], color=WATER, icon=PIPE_ICON) for pipe in pipes)
    else:
        cards.append(_full(ids.room("sensor", room, "valve_state"), valve_name, color=VALVE))
    # 3. Lasting temperatures of the room for auto (ECO as the preset); -/+ on the
    # thermostat is only a manual target.
    # The away temperature stays in the room settings (FR-SCH-02).
    settings = [("comfort", COMFORT), ("eco", ECO)]
    cards.extend(
        _half(
            ids.room("number", room, key),
            text[key],
            color=color,
            features=[{"type": "numeric-input", "style": "buttons"}],
        )
        for key, color in settings
    )
    if demo is not None and layout is not None and layout.house:
        cards.append(_heading(text["simulation"], "mdi:test-tube", subtitle=True))
        cards.append(_half(demo.window.entity_id, text["window"], color=VALVE))
        cards.append(_half(demo.sensor_fault.entity_id, text["demo_sensor_fault"], color=PROBLEM))
    # 4. The room's own schedule, editable; the house schedule is in the Heating block.
    if room.schedule_entity:
        cards.append(
            _full(
                room.schedule_entity,
                text["schedule_room"],
                color=LIMIT,
                state_content=["state", "next_event"],
            )
        )
    return {"type": "grid", "cards": cards}


# --- Scheme (FR-UI-25) ----------------------------------------------------------


def _scheme_view(
    runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str], shown: _Shown
) -> dict:
    """Animated scheme of the boiler, pipes, valves and radiators, by floor."""
    sid = ids.system
    card: dict[str, Any] = {
        "type": CARD_TYPE,
        "boiler": sid("binary_sensor", "boiler_command"),
        "reason": sid("sensor", "boiler_reason"),
        "outdoor": sid("sensor", "outdoor_temperature"),
    }
    if shown.flow:
        card["flow"] = shown.flow
    if shown.feedback:
        card["actual"] = shown.feedback
    card["floors"] = _floors(runtime, ids)
    return {
        "title": text["scheme"],
        "path": "schema",
        "icon": "mdi:pipe-valve",
        "type": "sections",
        "max_columns": 2,
        "sections": [{"type": "grid", "column_span": 2, "cards": [{**card, "grid_options": FULL}]}],
    }


def _floors(runtime: HydronicHeatingRuntime, ids: _Ids) -> list[dict[str, Any]]:
    """Rooms by the floor of their area, the highest floor first.

    The area is the one of the room's device (or entity), else an area with the
    room's name. Rooms without a floor come last, without a heading.
    """
    hass = runtime.hass
    devices, areas, floors = dr.async_get(hass), ar.async_get(hass), fr.async_get(hass)
    grouped: dict[str | None, list[dict[str, Any]]] = {}
    for room in runtime.rooms:
        climate = ids.room("climate", room, "")
        entry = ids.registry.async_get(climate)
        area_id = entry.area_id if entry else None
        if area_id is None and entry is not None and entry.device_id:
            device = devices.async_get(entry.device_id)
            area_id = device.area_id if device else None
        area = areas.async_get_area(area_id) if area_id else areas.async_get_area_by_name(room.name)
        item: dict[str, Any] = {
            "name": room.name,
            "climate": climate,
            "demand": ids.room("sensor", room, "demand"),
            "valve": ids.room("sensor", room, "valve_state"),
        }
        if pipe := next((v.temp_entity for v in room.valves if v.temp_entity), None):
            item["pipe"] = pipe
        grouped.setdefault(area.floor_id if area else None, []).append(item)

    def level(floor_id: str | None) -> tuple[int, int]:
        floor = floors.async_get_floor(floor_id) if floor_id else None
        if floor is None:
            return (1, 0)
        return (0, -(floor.level if floor.level is not None else 0))

    result = []
    for floor_id in sorted(grouped, key=level):
        floor = floors.async_get_floor(floor_id) if floor_id else None
        result.append({"name": floor.name if floor else "", "rooms": grouped[floor_id]})
    return result


# --- Legend -------------------------------------------------------------------


def _legend_view(runtime: HydronicHeatingRuntime, text: dict[str, str], shown: _Shown) -> dict:
    """Explain each tile, with the same icon as on the dashboard (a subview)."""
    rows = "\n".join(
        f'| <ha-icon icon="{icon}"></ha-icon> | **{name}** | {meaning} |'
        for feature, icon, name, meaning in LEGEND[_language(runtime)]
        if shown.has(feature)
    )
    return {
        "title": text["legend"],
        "path": LEGEND_PATH,
        "icon": "mdi:information-outline",
        "subview": True,
        "type": "sections",
        "max_columns": 2,
        "sections": [
            {
                "type": "grid",
                "column_span": 2,
                "cards": [
                    _heading(text["legend"], "mdi:information-outline", grid_options=FULL),
                    {
                        "type": "markdown",
                        "content": "| | | |\n|---|---|---|\n" + rows,
                        "text_only": True,
                        "grid_options": FULL,
                    },
                ],
            }
        ],
    }


# --- History ------------------------------------------------------------------


def _history(
    runtime: HydronicHeatingRuntime, ids: _Ids, text: dict[str, str], shown: _Shown
) -> dict:
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
        *([{"entity": shown.feedback, "name": text["boiler_actual"]}] if shown.feedback else []),
        {"entity": sid("binary_sensor", "heat_demand"), "name": text["heat_demand"]},
    ]
    if shown.windows:
        boiler_entities.append(
            {"entity": sid("binary_sensor", "window_block"), "name": text["window_block"]}
        )
    boiler_entities.append(
        {"entity": sid("binary_sensor", "heating_season"), "name": text["season"]}
    )
    if layout is not None:
        boiler_entities.insert(
            2, {"entity": layout.boiler.entity_id, "name": text["boiler_virtual"]}
        )
        if real_boiler:
            boiler_entities.insert(3, {"entity": real_boiler, "name": text["boiler_real"]})

    # Measured values; the damped temperature and the curve only where they are used.
    temperatures = [
        {"entity": sid("sensor", "outdoor_temperature"), "name": text["outdoor"]},
        {"entity": sid("sensor", "outdoor_mean_4h"), "name": text["outdoor_mean_4h"]},
    ]
    if shown.flow:
        temperatures.append({"entity": shown.flow, "name": text["flow_temperature"]})
    if shown.duty:
        temperatures += [
            {
                "entity": sid("sensor", "outdoor_temperature_damped"),
                "name": text["outdoor_damped"],
            },
            {"entity": sid("sensor", "flow_setpoint"), "name": text["flow_setpoint"]},
        ]
    water = shown.flow is not None or shown.duty

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
            "title": text["outdoor_curve"] if water else text["outdoor_chart"],
            "hours_to_show": 48,
            "entities": temperatures,
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
    # The pipe at each valve against the valve position (FR-SAFE-09).
    valve_entities += [
        {"entity": valve.temp_entity, "name": room.name}
        for room in rooms
        for valve in room.valves
        if valve.temp_entity
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
