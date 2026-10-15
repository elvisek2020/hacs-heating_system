"""Readable explanations of the boiler state and of logged decisions (cs/en).

The core says what happened and why (`BoilerStatus`, `Decision`); this module
turns it into sentences for the `detail` attribute, the logbook and the log.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .core.model import BoilerReason, BoilerStatus, Decision
from .notifications import reason_text

DETAIL: dict[str, dict[str, str]] = {
    "cs": {
        "startup": "Integrace startuje a čeká na načtení entit, nejpozději do {until}.",
        "idle": "Žádná místnost nepotřebuje teplo, kotel stojí.",
        "off": "Režim je vypnutý, kotel netopí. Protimrazová ochrana platí dál.",
        "summer": ("Mimo topnou sezónu, kotel netopí. Protimrazová ochrana platí dál."),
        "window_block": "Otevřená okna blokují topení, kotel stojí.",
        "pre_open": "Kotel čeká, až se otevřou ventily. Start nejdříve v {until}.",
        "pre_open_now": "Kotel čeká na start.",
        "pre_close": (
            "Kotel čeká, až se zavřou ventily místností, které teplo nechtějí, aby voda "
            "netekla tam, kde se netopí. Start nejdříve v {until}."
        ),
        "no_flow_hold": (
            "Ventily se neotevřely: otevřeno {open} z potřebných {needed}. Pokud se do "
            "{until} neotevřou, přejde topení do poruchy."
        ),
        "min_off_hold": (
            "Teplo je potřeba, ale kotel drží minimální pauzu {minutes} min. "
            "Start nejdříve v {until}."
        ),
        "max_starts_hold": (
            "Teplo je potřeba, ale kotel vyčerpal limit {count} startů za hodinu. "
            "Start nejdříve v {until}."
        ),
        "duty_hold": (
            "Teplo je potřeba, ale omezení střídy drží kotel vypnutý do konce cyklu "
            "{cycle_min} min, tedy do {until}."
        ),
        "firing_demand": (
            "Kotel topí na požadavek místností (celkem {demand} %, volajících místností: {rooms})."
        ),
        "firing_manual": "Kotel topí v manuálním režimu do {manual_until}.",
        "firing_frost": "Kotel topí kvůli protimrazové ochraně.",
        "duty_stop": " Omezení střídy ho vypne v {until}.",
        "min_on_hold": (
            "Teplo už nikdo nechce, ale kotel musí běžet minimální dobu {minutes} min. "
            "Vypne se v {until}."
        ),
        "overrun": "Kotel je vypnutý, ventily zůstávají otevřené kvůli doběhu do {until}.",
        "fault_safe": "Porucha: {fault}. Kotel je vypnutý, ventily jsou v klidovém stavu.",
        "fault_recovery": (
            "Porucha odeznívá ({fault}). Pokud vše vydrží v pořádku, vrátí se řízení "
            "do provozu v {until}."
        ),
    },
    "en": {
        "startup": "The integration is starting and waits for its entities, at most until {until}.",
        "idle": "No room needs heat, the boiler is idle.",
        "off": "The mode is off, the boiler does not heat. Frost protection still applies.",
        "summer": (
            "Off the heating season, the boiler does not heat. Frost protection still applies."
        ),
        "window_block": "Open windows block heating, the boiler is idle.",
        "pre_open": "The boiler waits for the valves to open. Start at {until} at the earliest.",
        "pre_open_now": "The boiler waits to start.",
        "pre_close": (
            "The boiler waits until the valves of rooms without demand are closed, so the "
            "water does not go where nobody heats. Start at {until} at the earliest."
        ),
        "no_flow_hold": (
            "The valves did not open: {open} of {needed} needed are open. If they do not "
            "open by {until}, heating goes to the fault state."
        ),
        "min_off_hold": (
            "Heat is needed, but the boiler keeps its minimum pause of {minutes} min. "
            "Start at {until} at the earliest."
        ),
        "max_starts_hold": (
            "Heat is needed, but the boiler used up its limit of {count} starts per hour. "
            "Start at {until} at the earliest."
        ),
        "duty_hold": (
            "Heat is needed, but the duty limit keeps the boiler off until the end of the "
            "{cycle_min} min cycle at {until}."
        ),
        "firing_demand": (
            "The boiler heats on room demand ({demand} % in total, rooms calling: {rooms})."
        ),
        "firing_manual": "The boiler heats in manual mode until {manual_until}.",
        "firing_frost": "The boiler heats for frost protection.",
        "duty_stop": " The duty limit stops it at {until}.",
        "min_on_hold": (
            "Nobody needs heat any more, but the boiler must run its minimum time of "
            "{minutes} min. It stops at {until}."
        ),
        "overrun": "The boiler is off, the valves stay open for the overrun until {until}.",
        "fault_safe": "Fault: {fault}. The boiler is off, the valves are in their idle position.",
        "fault_recovery": (
            "The fault is clearing ({fault}). If everything stays fine, control resumes at {until}."
        ),
    },
}

DECISION: dict[str, dict[str, str]] = {
    "cs": {
        "boiler_on": "Kotel zapnut: {cause}.",
        "on_firing_manual": "manuální topení do {manual_until}",
        "on_firing_frost": "protimrazová ochrana",
        "on_firing_demand": (
            "požadavek místností (celkem {demand} %, volajících místností: {rooms})"
        ),
        "boiler_off": "Kotel vypnut: {cause}.",
        "off_min_on_done": "uplynula minimální doba běhu a teplo nikdo nechce",
        "off_no_demand": "teplo nikdo nechce",
        "off_mode_off": "režim vypnuto",
        "off_summer": "skončila topná sezóna",
        "season_start": (
            "Začala topná sezóna: průměr venkovní teploty za 4 h {mean} °C klesl pod "
            "hranici {limit} °C."
        ),
        "season_end": (
            "Skončila topná sezóna: {days} dny po sobě byl průměr venkovní teploty za 4 h "
            "celý den nad hranicí {limit} °C."
        ),
        "season_on": "Topná sezóna zapnuta ručně.",
        "season_off": "Topná sezóna vypnuta ručně, mimo sezónu se netopí.",
        "off_window_block": "otevřená okna",
        "off_duty_limit": "omezení střídy, další start nejdříve v {next_start}",
        "off_no_flow": "chybí průtok, otevřených ventilů je málo",
        "off_fault": "porucha ({fault})",
        "overrun_suffix": " Ventily zůstanou otevřené do {until}.",
        "hold_min_on_hold": "Kotel poběží do {until} kvůli minimální době běhu {minutes} min.",
        "hold_min_off_hold": "Start odložen do {until}: minimální pauza {minutes} min.",
        "hold_max_starts_hold": "Start odložen do {until}: limit {count} startů za hodinu.",
        "hold_duty_hold": "Start odložen do {until}: omezení střídy, cyklus {cycle_min} min.",
        "hold_pre_open": "Start odložen do {until}: čeká se na otevření ventilů.",
        "hold_pre_close": (
            "Start odložen do {until}: zavírají se ventily místností, které teplo nechtějí."
        ),
        "hold_no_flow_hold": (
            "Ventily se neotevřely (otevřeno {open} z {needed}). Pokud se neotevřou, "
            "přejde topení v {until} do poruchy."
        ),
        "hold_fault_recovery": "Porucha odeznívá, návrat do provozu v {until}.",
        "reverted": "Přepnuto mimo řízení na {found}, integrace výstup vrátila na {set_to}. {why}",
        "reverted_subject": "Výstup {name} ({entity_id}) byl přepnut mimo řízení na {found}, "
        "integrace ho vrátila na {set_to}. {why}",
        "valve_why": "Důvod: {reason}.",
        "valve_why_until": "Důvod: {reason}, do {until}.",
        "boiler_on_state": "zapnuto",
        "boiler_off_state": "vypnuto",
        "valve_open_state": "otevřeno",
        "valve_closed_state": "zavřeno",
        "presence_absent": "Nikdo doma: místnosti v režimu automaticky jedou na {preset_word}.",
        "presence_long_away": "Dlouhodobě pryč: celý dům jede na teploty Pryč.",
        "presence_home": "Někdo je doma: místnosti jedou zase podle rozvrhu.",
        "return_suffix": " Očekávaný návrat {expected_return}.",
        "preset_eco": "útlum",
        "preset_away": "teploty Pryč",
        "preheat": "Předtápění: {room} na {comfort} °C do {preheat_until} ({source_word}), "
        "rychlost ohřevu {rate} K/h.",
        "source_schedule": "začátek komfortu podle rozvrhu",
        "source_return": "očekávaný návrat",
        "ventilation_started": (
            "{room}: rychlý pokles teploty o {drop} °C, asi se větrá – topení pozastaveno "
            "do {pause_until}."
        ),
        "ventilation_ended": "{room}: větrání skončilo, místnost zase topí podle cíle.",
        "ventilation_manual_started": "{room}: ruční větrání do {vent_until}.",
        "ventilation_manual_extended": "{room}: větrání prodlouženo do {vent_until}.",
        "ventilation_manual_ended": "{room}: větrání skončilo, místnost zase topí podle cíle.",
        "ventilation_floor_started": (
            "{room}: větrá se celé patro do {vent_until} (rychlý pokles teploty: {trigger})."
        ),
        "ventilation_floor_extended": "{room}: větrání prodlouženo do {vent_until}.",
        "ventilation_floor_ended": "{room}: větrání skončilo, místnost zase topí podle cíle.",
        "valve_not_opening": (
            "{room}: ventil asi neotvírá – trubka se za {minutes} min ohřála jen o {rise} °C."
        ),
        "valve_not_closing": "{room}: ventil asi nezavírá – trubka se ohřála o {rise} °C.",
        "valve_ok": "{room}: ventil zase funguje, kontrola podle trubky prošla.",
        "trigger_stop": "Stop",
        "trigger_mode": "Režim {mode}",
        "shadow": "[Shadow] ",
        "demo": "[Demo] ",
    },
    "en": {
        "boiler_on": "Boiler on: {cause}.",
        "on_firing_manual": "manual heating until {manual_until}",
        "on_firing_frost": "frost protection",
        "on_firing_demand": "room demand ({demand} % in total, rooms calling: {rooms})",
        "boiler_off": "Boiler off: {cause}.",
        "off_min_on_done": "the minimum run time is over and nobody needs heat",
        "off_no_demand": "nobody needs heat",
        "off_mode_off": "mode off",
        "off_summer": "the heating season ended",
        "season_start": (
            "Heating season started: the 4 h mean outdoor temperature {mean} °C dropped "
            "below the limit of {limit} °C."
        ),
        "season_end": (
            "Heating season ended: for {days} days in a row the 4 h mean outdoor "
            "temperature stayed above the limit of {limit} °C all day."
        ),
        "season_on": "Heating season switched on by hand.",
        "season_off": "Heating season switched off by hand, no heating off season.",
        "off_window_block": "open windows",
        "off_duty_limit": "duty limit, next start at {next_start} at the earliest",
        "off_no_flow": "no flow, too few valves are open",
        "off_fault": "fault ({fault})",
        "overrun_suffix": " The valves stay open until {until}.",
        "hold_min_on_hold": "The boiler runs until {until} because of its minimum run time of "
        "{minutes} min.",
        "hold_min_off_hold": "Start delayed until {until}: minimum pause of {minutes} min.",
        "hold_max_starts_hold": "Start delayed until {until}: limit of {count} starts per hour.",
        "hold_duty_hold": "Start delayed until {until}: duty limit, cycle of {cycle_min} min.",
        "hold_pre_open": "Start delayed until {until}: waiting for the valves to open.",
        "hold_pre_close": (
            "Start delayed until {until}: the valves of rooms without demand are closing."
        ),
        "hold_no_flow_hold": (
            "The valves did not open ({open} of {needed} open). If they stay closed, heating "
            "goes to the fault state at {until}."
        ),
        "hold_fault_recovery": "The fault is clearing, control resumes at {until}.",
        "reverted": "Switched outside the controller to {found}, the integration set it back "
        "to {set_to}. {why}",
        "reverted_subject": "Output {name} ({entity_id}) was switched outside the controller to "
        "{found}, the integration set it back to {set_to}. {why}",
        "valve_why": "Reason: {reason}.",
        "valve_why_until": "Reason: {reason}, until {until}.",
        "boiler_on_state": "on",
        "boiler_off_state": "off",
        "valve_open_state": "open",
        "valve_closed_state": "closed",
        "presence_absent": "Nobody home: rooms in auto use {preset_word}.",
        "presence_long_away": "Long absence: the whole house uses the away temperatures.",
        "presence_home": "Somebody is home: rooms follow their schedule again.",
        "return_suffix": " Expected return {expected_return}.",
        "preset_eco": "the setback",
        "preset_away": "the away temperatures",
        "preheat": "Preheating: {room} to {comfort} °C by {preheat_until} ({source_word}), "
        "heat-up rate {rate} K/h.",
        "source_schedule": "comfort starts by schedule",
        "source_return": "expected return",
        "ventilation_started": (
            "{room}: fast temperature drop by {drop} °C, probably airing – heating paused "
            "until {pause_until}."
        ),
        "ventilation_ended": "{room}: airing is over, the room heats to its target again.",
        "ventilation_manual_started": "{room}: airing by hand until {vent_until}.",
        "ventilation_manual_extended": "{room}: airing extended until {vent_until}.",
        "ventilation_manual_ended": "{room}: airing is over, the room heats to its target again.",
        "ventilation_floor_started": (
            "{room}: the whole floor is aired until {vent_until} (fast temperature drop: "
            "{trigger})."
        ),
        "ventilation_floor_extended": "{room}: airing extended until {vent_until}.",
        "ventilation_floor_ended": "{room}: airing is over, the room heats to its target again.",
        "valve_not_opening": (
            "{room}: the valve does not seem to open – the pipe warmed only by {rise} °C "
            "in {minutes} min."
        ),
        "valve_not_closing": (
            "{room}: the valve does not seem to close – the pipe warmed by {rise} °C."
        ),
        "valve_ok": "{room}: the valve works again, the pipe check passed.",
        "trigger_stop": "Stop",
        "trigger_mode": "Mode {mode}",
        "shadow": "[Shadow] ",
        "demo": "[Demo] ",
    },
}

VALVE_REASONS: dict[str, dict[str, str]] = {
    "cs": {
        "startup": "start integrace",
        "fault_safe": "porucha",
        "frost": "protimrazová ochrana",
        "window": "otevřené okno",
        "ventilation": "větrání (rychlý pokles teploty)",
        "manual": "manuální topení",
        "manual_excluded": "manuál se místnosti netýká",
        "idle_policy": "klidová poloha, topení neběží",
        "room_off": "místnost je vypnutá",
        "pwm": "regulace místnosti (PWM)",
        "min_state_hold": "minimální doba stavu ventilu",
        "exercise": "protáčení ventilu",
        "overrun": "doběh kotle",
        "min_flow": "minimální průtok kotlem",
        "preheat": "předtápění",
    },
    "en": {
        "startup": "integration start",
        "fault_safe": "fault",
        "frost": "frost protection",
        "window": "open window",
        "ventilation": "airing (fast temperature drop)",
        "manual": "manual heating",
        "manual_excluded": "manual heating does not cover the room",
        "idle_policy": "idle position, heating is off",
        "room_off": "the room is off",
        "pwm": "room control (PWM)",
        "min_state_hold": "minimum valve state time",
        "exercise": "valve exercise",
        "overrun": "boiler overrun",
        "min_flow": "minimum flow through the boiler",
        "preheat": "preheating",
    },
}

MODES: dict[str, dict[str, str]] = {
    "cs": {
        "auto": "automaticky",
        "manual": "manuál",
        "off": "vypnuto",
        "away": "pryč",
    },
    "en": {"auto": "auto", "manual": "manual", "off": "off", "away": "away"},
}


def language(hass: HomeAssistant) -> str:
    """Return cs or en from the Home Assistant language."""
    return "cs" if (hass.config.language or "").startswith("cs") else "en"


# A time in a sentence carries its date between two marks; `_finish` turns it into
# "v 5:30", "zítra v 5:30" or "ve čtvrtek do 5:30" once the sentence is complete,
# because the day goes before the preposition.
MARK = "\x1f"
DAYS = {
    "cs": ("v pondělí", "v úterý", "ve středu", "ve čtvrtek", "v pátek", "v sobotu", "v neděli"),
    "en": (
        "on Monday",
        "on Tuesday",
        "on Wednesday",
        "on Thursday",
        "on Friday",
        "on Saturday",
        "on Sunday",
    ),
}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PREPOSITIONS = {"cs": ("ve", "v", "od", "do"), "en": ("at", "from", "until", "by")}
_TIME = {
    lang: re.compile(
        rf"(?:\b(?P<prep>{'|'.join(preps)}) )?{MARK}(?P<date>[0-9-]+){MARK}(?P<time>[0-9:]+)",
        re.IGNORECASE,
    )
    for lang, preps in PREPOSITIONS.items()
}


def clock(value: Any) -> str:
    """Local time of day with seconds (5:32:38); the day is added by `_finish`."""
    if not isinstance(value, datetime):
        return "?"
    local = dt_util.as_local(value)
    return f"{MARK}{local.date().isoformat()}{MARK}{local.hour}:{local:%M:%S}"


def moment(value: Any) -> str:
    """Local time of day (5:30); the day is added by `_finish`."""
    if not isinstance(value, datetime):
        return "?"
    local = dt_util.as_local(value)
    return f"{MARK}{local.date().isoformat()}{MARK}{local.hour}:{local:%M}"


def _day(lang: str, day: date) -> str:
    """Today is no word; tomorrow, the days of the next week, else the date."""
    delta = (day - dt_util.now().date()).days
    if delta == 0:
        return ""
    if delta == 1:
        return "zítra" if lang == "cs" else "tomorrow"
    if delta == -1:
        return "včera" if lang == "cs" else "yesterday"
    if 1 < delta < 7:
        return DAYS[lang][day.weekday()]
    return f"{day.day}. {day.month}." if lang == "cs" else f"on {MONTHS[day.month - 1]} {day.day}"


def finish(hass: HomeAssistant, text: str) -> str:
    """Put the day of each time into the sentence: "zítra v 5:30", "at 5:30 tomorrow"."""
    lang = language(hass)

    def place(match: re.Match[str]) -> str:
        prep, clock_time = match["prep"], match["time"]
        day = _day(lang, date.fromisoformat(match["date"]))
        if lang == "en":
            phrase = f"{prep or 'at'} {clock_time}"
            return f"{phrase} {day}" if day else phrase
        if prep is None:
            return f"{day} v {clock_time}" if day else f"v {clock_time}"
        if not day:
            return f"{prep} {clock_time}"
        phrase = f"{day} {prep.lower()} {clock_time}"
        return phrase[:1].upper() + phrase[1:] if prep[:1].isupper() else phrase

    return _TIME[lang].sub(place, text)


def number(hass: HomeAssistant, value: Any) -> str:
    """Short number, with a decimal comma in Czech (0,5)."""
    text = f"{value:g}" if isinstance(value, int | float) else str(value)
    return text.replace(".", ",") if language(hass) == "cs" else text


def _values(hass: HomeAssistant, status: BoilerStatus, extra: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {**status.params, **extra}
    values["until"] = clock(status.until)
    for key in ("manual_until", "next_start", "valve_until"):
        if key in values:
            values[key] = clock(values[key])
    for key in ("expected_return", "preheat_until"):
        if key in values:
            values[key] = moment(values[key])
    for key in ("demand", "comfort", "rate"):
        if key in values:
            values[key] = number(hass, values[key])
    if "fault" in values:
        values["fault"] = reason_text(hass, str(values["fault"]))
    return values


def detail(hass: HomeAssistant, status: BoilerStatus) -> str:
    """Sentence that explains the current boiler state."""
    texts = DETAIL[language(hass)]
    values = _values(hass, status, {})
    key = status.reason.value
    if status.reason is BoilerReason.PRE_OPEN and status.until is None:
        key = "pre_open_now"
    text = texts[key].format_map(_Defaults(values))
    if status.reason.value.startswith("firing_") and status.until is not None:
        text += texts["duty_stop"].format_map(_Defaults(values))
    return finish(hass, text)


def valve_reason(hass: HomeAssistant, reason: str) -> str:
    """Translate a valve reason code."""
    return VALVE_REASONS[language(hass)].get(reason, reason)


def decision_text(
    hass: HomeAssistant,
    decision: Decision,
    *,
    trigger: tuple[str, str | None] | None = None,
    shadow: bool = False,
    demo: bool = False,
    name: str | None = None,
    subject: bool = False,
) -> str:
    """Logbook and log sentence of one decision.

    The logbook shows the entity next to the message, so only the log names the
    reverted output (`subject`). A user action prefixes the time rule it caused.
    """
    lang = language(hass)
    texts = DECISION[lang]
    status = decision.status
    values = _values(hass, status, decision.params)
    fill = _Defaults(values)
    if decision.kind == "boiler_on":
        cause = texts.get(f"on_{status.reason.value}", status.reason.value).format_map(fill)
        message = texts["boiler_on"].format(cause=cause)
    elif decision.kind == "boiler_off":
        code = str(decision.params.get("cause", "no_demand"))
        if code.startswith("fault:"):
            fill["fault"] = reason_text(hass, code.partition(":")[2])
            code = "fault"
        cause = texts.get(f"off_{code}", code).format_map(fill)
        message = texts["boiler_off"].format(cause=cause)
        if status.reason is BoilerReason.OVERRUN:
            message += texts["overrun_suffix"].format_map(fill)
    elif decision.kind == "hold":
        message = texts.get(f"hold_{status.reason.value}", "{until}").format_map(fill)
    elif decision.kind == "presence":
        state = str(decision.params.get("state"))
        fill["preset_word"] = texts.get(f"preset_{decision.params.get('preset')}", "")
        message = texts[f"presence_{state}"].format_map(fill)
        if state != "home" and decision.params.get("expected_return") is not None:
            message += texts["return_suffix"].format_map(fill)
    elif decision.kind == "season":
        params = decision.params
        if params.get("mode") == "on":
            key = "season_on"
        elif params.get("mode") == "off":
            key = "season_off"
        else:
            key = "season_start" if params.get("active") else "season_end"
        fill["mean"] = number(hass, params.get("mean")) if params.get("mean") is not None else "?"
        fill["limit"] = number(hass, params.get("limit"))
        message = texts[key].format_map(fill)
    elif decision.kind == "room_target":
        message = room_target_text(hass, decision.params)
    elif decision.kind == "ventilation":
        params = decision.params
        fill["drop"] = number(hass, params.get("drop")) if params.get("drop") is not None else "?"
        fill["pause_until"] = moment(params.get("pause_until"))
        fill["vent_until"] = moment(params.get("vent_until"))
        fill["trigger"] = params.get("trigger") or "?"
        message = texts[f"ventilation_{params.get('event')}"].format_map(fill)
    elif decision.kind == "valve_check":
        params = decision.params
        fill["rise"] = number(hass, params.get("rise")) if params.get("rise") is not None else "?"
        fill["minutes"] = number(hass, params.get("minutes"))
        message = texts[f"valve_{params.get('result')}"].format_map(fill)
    elif decision.kind == "preheat":
        fill["source_word"] = texts.get(f"source_{decision.params.get('source')}", "")
        message = texts["preheat"].format_map(fill)
    else:
        message = _reverted_text(hass, texts, decision, values, name, subject=subject)
    if trigger is not None and decision.kind == "hold":
        kind, mode = trigger
        prefix = texts[f"trigger_{kind}"].format(mode=MODES[lang].get(mode or "", mode))
        message = f"{prefix}: {message[0].lower()}{message[1:]}"
    if shadow:
        message = texts["shadow"] + message
    if demo:
        message = texts["demo"] + message
    return finish(hass, message)


def _reverted_text(
    hass: HomeAssistant,
    texts: Mapping[str, str],
    decision: Decision,
    values: dict[str, Any],
    name: str | None,
    *,
    subject: bool,
) -> str:
    params = decision.params
    output = params.get("output", "boiler")
    states = ("on_state", "off_state") if output == "boiler" else ("open_state", "closed_state")

    def word(value: Any) -> str:
        return texts[f"{output}_{states[0] if value else states[1]}"]

    if output == "boiler":
        why = detail(hass, decision.status)
    else:
        reason = valve_reason(hass, str(params.get("valve_reason", "")))
        key = "valve_why_until" if params.get("valve_until") else "valve_why"
        why = texts[key].format(reason=reason, until=values.get("valve_until", ""))
    entity_id = str(params.get("entity_id", ""))
    return texts["reverted_subject" if subject else "reverted"].format(
        name=name or entity_id,
        entity_id=entity_id,
        found=word(params.get("observed")),
        set_to=word(params.get("desired")),
        why=why,
    )


class _Defaults(dict):
    """Format values; a missing placeholder stays visible instead of failing."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


# --- Room target (why comfort, setback or away) ------------------------------

ROOM: dict[str, dict[str, str]] = {
    "cs": {
        "frost": "Protimrazová ochrana: místnost je pod {frost} °C, topí naplno.",
        "window": "Otevřené okno: ventil je zavřený.",
        "ventilation": (
            "Větrá se (rychlý pokles teploty): ventil je zavřený nejméně do {until}, pak "
            "dokud teplota zase nezačne stoupat."
        ),
        "ventilation_manual": "Větrá se (ručně) do {until}: ventil je zavřený.",
        "ventilation_floor": "Větrá se celé patro do {until}: ventil je zavřený.",
        "manual": "Manuální topení: ventil je otevřený, dokud manuál běží.",
        "room_off": "Místnost je vypnutá.",
        "summer": "Mimo topnou sezónu: netopí se.",
        "system_off": "Topení je vypnuté.",
        "system_away": "Režim Pryč: {temp} °C.",
        "override": "Ruční změna: {temp} °C, rozvrh ani přítomnost se nepoužívají.",
        "preheat": "Předtápění na {temp} °C do {until} ({source}).",
        "long_away": "Dlouhodobá nepřítomnost: {temp} °C.",
        "absent": "{Word} {temp} °C: nikdo doma ({presence}).",
        "schedule_eco": "Útlum {temp} °C podle rozvrhu ({schedule}).",
        "schedule_eco_until": "Útlum {temp} °C podle rozvrhu ({schedule}) do {until}.",
        "schedule_comfort": "Komfort {temp} °C podle rozvrhu ({schedule}).",
        "schedule_comfort_until": "Komfort {temp} °C podle rozvrhu ({schedule}) do {until}.",
        "comfort": "Komfort {temp} °C.",
        "return": " Návrat {until}.",
        "source_schedule": "začátek komfortu podle rozvrhu",
        "source_return": "očekávaný návrat",
        "word_comfort": "komfort",
        "word_eco": "útlum",
        "word_away": "teplota Pryč",
        "log_absent": "{room}: {word} {temp} °C, nikdo doma ({presence}).",
        "log_long_away": "{room}: teplota Pryč {temp} °C, dlouhodobá nepřítomnost.",
        "log_back": "{room}: {word} {temp} °C, někdo je doma ({presence}).",
        "log_schedule": "{room}: {word} {temp} °C podle rozvrhu ({schedule}).",
        "log_schedule_until": "{room}: {word} {temp} °C podle rozvrhu ({schedule}) do {until}.",
        "log_comfort": "{room}: komfort {temp} °C.",
    },
    "en": {
        "frost": "Frost protection: the room is below {frost} °C and heats at full power.",
        "window": "Open window: the valve is closed.",
        "ventilation": (
            "Airing (fast temperature drop): the valve is closed at least until {until}, then "
            "until the temperature rises again."
        ),
        "ventilation_manual": "Airing (by hand) until {until}: the valve is closed.",
        "ventilation_floor": "The whole floor is aired until {until}: the valve is closed.",
        "manual": "Manual heating: the valve is open while manual heating runs.",
        "room_off": "The room is off.",
        "summer": "Off the heating season: no heating.",
        "system_off": "Heating is off.",
        "system_away": "Away mode: {temp} °C.",
        "override": "Manual change: {temp} °C, schedule and presence are not used.",
        "preheat": "Preheating to {temp} °C by {until} ({source}).",
        "long_away": "Long absence: {temp} °C.",
        "absent": "{Word} {temp} °C: nobody home ({presence}).",
        "schedule_eco": "Setback {temp} °C by schedule ({schedule}).",
        "schedule_eco_until": "Setback {temp} °C by schedule ({schedule}) until {until}.",
        "schedule_comfort": "Comfort {temp} °C by schedule ({schedule}).",
        "schedule_comfort_until": "Comfort {temp} °C by schedule ({schedule}) until {until}.",
        "comfort": "Comfort {temp} °C.",
        "return": " Back {until}.",
        "source_schedule": "comfort starts by schedule",
        "source_return": "expected return",
        "word_comfort": "comfort",
        "word_eco": "setback",
        "word_away": "away temperature",
        "log_absent": "{room}: {word} {temp} °C, nobody home ({presence}).",
        "log_long_away": "{room}: away temperature {temp} °C, long absence.",
        "log_back": "{room}: {word} {temp} °C, somebody is home ({presence}).",
        "log_schedule": "{room}: {word} {temp} °C by schedule ({schedule}).",
        "log_schedule_until": "{room}: {word} {temp} °C by schedule ({schedule}) until {until}.",
        "log_comfort": "{room}: comfort {temp} °C.",
    },
}


def entity_name(hass: HomeAssistant, entity_id: str | None) -> str:
    """Friendly name of an entity, or its ID when it does not exist (yet)."""
    if not entity_id:
        return "?"
    state = hass.states.get(entity_id)
    return state.name if state else entity_id


def _room_values(
    hass: HomeAssistant,
    *,
    temp: Any,
    preset: str,
    until: Any,
    presence: str | None,
    schedule: str | None,
) -> dict[str, Any]:
    texts = ROOM[language(hass)]
    word = texts.get(f"word_{preset}", texts["word_comfort"])
    return {
        "temp": number(hass, temp) if temp is not None else "?",
        "until": moment(until),
        "presence": entity_name(hass, presence),
        "schedule": entity_name(hass, schedule),
        "word": word,
        "Word": word[:1].upper() + word[1:],
    }


def room_detail(hass: HomeAssistant, room: Any) -> str:
    """Sentence that explains the target of a room (attribute `target_detail`)."""
    texts = ROOM[language(hass)]
    reason = room.target_reason.value
    values = _room_values(
        hass,
        temp=room.target,
        preset=room.effective_preset.value,
        until=room.target_until,
        presence=room.presence_entity,
        schedule=room.schedule_entity,
    )
    values["frost"] = number(hass, room.cfg.frost_temp)
    values["source"] = texts.get(f"source_{room.preheat_source}", "")
    key = reason
    if reason.startswith("schedule_") and room.target_until is not None:
        key = f"{reason}_until"
    if reason == "ventilation" and room.manual_vent:
        key = f"ventilation_{room.vent_source or 'manual'}"
    text = texts[key].format_map(_Defaults(values))
    if reason in ("absent", "long_away") and room.target_until is not None:
        text += texts["return"].format_map(_Defaults(values))
    return finish(hass, text)


def room_target_text(hass: HomeAssistant, params: Mapping[str, Any]) -> str:
    """Logbook sentence when presence or the schedule changed a room's target."""
    texts = ROOM[language(hass)]
    values = _room_values(
        hass,
        temp=params.get("target"),
        preset=str(params.get("preset")),
        until=params.get("target_until"),
        presence=params.get("presence_entity"),
        schedule=params.get("schedule_entity"),
    )
    values["room"] = params.get("room", "?")
    reason = params.get("reason")
    if reason == "absent":
        key = "log_absent"
    elif reason == "long_away":
        key = "log_long_away"
    elif params.get("previous") in ("absent", "long_away"):
        key = "log_back"
    elif reason in ("schedule_eco", "schedule_comfort"):
        key = "log_schedule_until" if params.get("target_until") else "log_schedule"
    else:
        key = "log_comfort"
    return finish(hass, texts[key].format_map(_Defaults(values)))


# --- Now and next, for the animated scheme (FR-UI-25) ---------------------------

SCHEME: dict[str, dict[str, str]] = {
    "cs": {
        "demand": "Teplo chtějí: {rooms}.",
        "no_demand": "Teplo teď nechce žádná místnost.",
        "closing": "Zavírají se ventily: {rooms}.",
        "opening": "Otevírají se ventily: {rooms}.",
        "airing": "Větrá se: {rooms}.",
        "frost": "Protimrazová ochrana: {rooms}.",
        "and": " a ",
        "all_rooms": "všechny místnosti",
        "boiler_start": "Kotel zapne v {at}.",
        "boiler_may_start": "Kotel může zapnout nejdřív v {at}.",
        "boiler_off": "Kotel vypne v {at}.",
        "min_on_end": "Minimální běh do {at}, pak kotel vypne, jakmile místnosti dosáhnou cíle.",
        "duty_stop": "Podle omezení střídy kotel vypne v {at}.",
        "valves_idle_deenergize": "Doběh skončí v {at}, pak jsou hlavice bez proudu.",
        "valves_idle_open": "Doběh skončí v {at}, pak jsou ventily otevřené.",
        "valves_idle_closed": "Doběh skončí v {at}, pak jsou ventily zavřené.",
        "fault_recovery": "Návrat z poruchy v {at}, pokud kotel zůstane v pořádku.",
        "manual_end": "Manuál skončí v {at}.",
        "preheat": "Od {at} předtápění: {rooms} (komfort v {target}).",
        "schedule_comfort": "V {at} komfort podle rozvrhu: {rooms}.",
        "schedule_eco": "V {at} útlum podle rozvrhu: {rooms}.",
        "return": "Očekávaný návrat v {at}: {rooms}.",
        "ventilation_end": "Po větrání topí zase nejdřív v {at}: {rooms}.",
        "manual_ventilation_end": "Konec větrání v {at}: {rooms}.",
    },
    "en": {
        "demand": "Heat wanted by: {rooms}.",
        "no_demand": "No room wants heat now.",
        "closing": "Valves closing: {rooms}.",
        "opening": "Valves opening: {rooms}.",
        "airing": "Airing: {rooms}.",
        "frost": "Frost protection: {rooms}.",
        "and": " and ",
        "all_rooms": "all rooms",
        "boiler_start": "The boiler starts at {at}.",
        "boiler_may_start": "The boiler may start at {at} at the earliest.",
        "boiler_off": "The boiler stops at {at}.",
        "min_on_end": "Minimum run until {at}, then the boiler stops once the rooms reach their "
        "target.",
        "duty_stop": "By the duty limit the boiler stops at {at}.",
        "valves_idle_deenergize": "The overrun ends at {at}, then the heads are without current.",
        "valves_idle_open": "The overrun ends at {at}, then the valves are open.",
        "valves_idle_closed": "The overrun ends at {at}, then the valves are closed.",
        "fault_recovery": "Back from the fault at {at} if the boiler stays fine.",
        "manual_end": "Manual heating ends at {at}.",
        "preheat": "Preheating from {at}: {rooms} (comfort at {target}).",
        "schedule_comfort": "At {at} comfort by schedule: {rooms}.",
        "schedule_eco": "At {at} setback by schedule: {rooms}.",
        "return": "Expected return at {at}: {rooms}.",
        "ventilation_end": "After airing the room heats again at {at} at the earliest: {rooms}.",
        "manual_ventilation_end": "Airing ends at {at}: {rooms}.",
    },
}
# Boiler events need seconds ("05:32:38"), room events only the time of day.
BOILER_KINDS = frozenset(
    {
        "boiler_start",
        "boiler_may_start",
        "boiler_off",
        "min_on_end",
        "duty_stop",
        "valves_idle",
        "fault_recovery",
    }
)


def _names(hass: HomeAssistant, names: list[str] | tuple[str, ...]) -> str:
    texts = SCHEME[language(hass)]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + texts["and"] + names[-1]


def now_lines(hass: HomeAssistant, ctrl: Any) -> list[str]:
    """Describe the present: the boiler, who wants heat, moving valves, airing."""
    texts = SCHEME[language(hass)]
    now = ctrl.last_step
    lines = [detail(hass, ctrl.boiler_status)]
    rooms = list(ctrl.rooms.values())
    calling = sorted((r for r in rooms if r.demand > 0), key=lambda r: -r.demand)
    if calling:
        named = [f"{r.cfg.name} ({number(hass, round(r.demand))} %)" for r in calling]
        lines.append(texts["demand"].format(rooms=_names(hass, named)))
    else:
        lines.append(texts["no_demand"])
    if now is not None:
        for state in ("closing", "opening"):
            moving = [r.cfg.name for r in rooms if r.valve_summary(now) == state]
            if moving:
                lines.append(texts[state].format(rooms=_names(hass, moving)))
    if airing := [r.cfg.name for r in rooms if r.vent.active or r.manual_vent]:
        lines.append(texts["airing"].format(rooms=_names(hass, airing)))
    if frost := [r.cfg.name for r in rooms if r.frost_active]:
        lines.append(texts["frost"].format(rooms=_names(hass, frost)))
    return lines


def upcoming_items(hass: HomeAssistant, events: list[Any]) -> list[dict[str, Any]]:
    """Next events with their sentences (attribute `upcoming`)."""
    texts = SCHEME[language(hass)]
    items = []
    for event in events:
        kind = event.kind
        key = f"valves_idle_{event.params.get('policy')}" if kind == "valves_idle" else kind
        rooms = texts["all_rooms"] if event.params.get("all_rooms") else _names(hass, event.rooms)
        at = clock(event.at) if kind in BOILER_KINDS else moment(event.at)
        text = finish(
            hass,
            texts[key].format_map(
                _Defaults(
                    {"at": at, "rooms": rooms, "target": moment(event.params.get("target_at"))}
                )
            ),
        )
        items.append(
            {"at": event.at.isoformat(), "kind": kind, "rooms": list(event.rooms), "text": text}
        )
    return items


# --- Thresholds of the demand (tile texts) -----------------------------------------

RULES: dict[str, dict[str, str]] = {
    "cs": {
        "start": "{value} % z {threshold} % {join} {calling} z {rooms}",
        "stop": "{value} % z {off} % (vypnutí) {join} {calling} z {rooms}",
        "rooms_1": "1 místnosti",
        "rooms_n": "{n} místností",
        "or": "nebo",
        "and": "a",
        "room": "{value} % z {threshold} %",
    },
    "en": {
        "start": "{value} % of {threshold} % {join} {calling} of {rooms}",
        "stop": "{value} % of {off} % (off) {join} {calling} of {rooms}",
        "rooms_1": "1 room",
        "rooms_n": "{n} rooms",
        "or": "or",
        "and": "and",
        "room": "{value} % of {threshold} %",
    },
}


def demand_rule(hass: HomeAssistant, ctrl: Any) -> str:
    """Compare the demand with its thresholds (FR-ARB-01, FR-ARB-02).

    "0,6 % z 30 % nebo 0 z 2 místností": the boiler starts when the weighted demand
    reaches the threshold or enough rooms call (`combine: all`: both). While it is
    requested the lower threshold of the hysteresis applies, marked as the stop.
    """
    texts = RULES[language(hass)]
    cfg = ctrl.cfg
    n = cfg.min_rooms_calling
    running = ctrl.arbitration.request
    return texts["stop" if running else "start"].format(
        value=number(hass, round(ctrl.arbitration.weighted, 1)),
        threshold=number(hass, cfg.demand_threshold),
        off=number(hass, cfg.demand_threshold - cfg.demand_hysteresis),
        join=texts["or" if cfg.combine == "any" else "and"],
        calling=ctrl.arbitration.calling,
        rooms=texts["rooms_1"] if n == 1 else texts["rooms_n"].format(n=n),
    )


def room_call(hass: HomeAssistant, room: Any, ctrl: Any) -> str:
    """Compare the room demand with the threshold from which it calls: "75 % z 50 %"."""
    return RULES[language(hass)]["room"].format(
        value=number(hass, round(room.demand, 1)),
        threshold=number(hass, ctrl.cfg.room_call_threshold),
    )


def airing_end(hass: HomeAssistant, until: Any) -> str | None:
    """End of airing by hand for a tile: "do 6:45", "zítra do 0:15" (FR-WIN-07)."""
    if not isinstance(until, datetime):
        return None
    word = "do" if language(hass) == "cs" else "until"
    return finish(hass, f"{word} {moment(until)}")
