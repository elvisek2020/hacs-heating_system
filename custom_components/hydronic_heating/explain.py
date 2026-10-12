"""Readable explanations of the boiler state and of logged decisions (cs/en).

The core says what happened and why (`BoilerStatus`, `Decision`); this module
turns it into sentences for the `detail` attribute, the logbook and the log.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
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
        "summer": (
            "Léto: tlumená venkovní teplota je nad mezí vytápění, kotel netopí. "
            "Protimrazová ochrana platí dál."
        ),
        "window_block": "Otevřená okna blokují topení, kotel stojí.",
        "pre_open": "Kotel čeká, až se otevřou ventily. Start nejdříve v {until}.",
        "pre_open_now": "Kotel čeká na start.",
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
            "Summer: the damped outdoor temperature is above the heating limit, the boiler "
            "does not heat. Frost protection still applies."
        ),
        "window_block": "Open windows block heating, the boiler is idle.",
        "pre_open": "The boiler waits for the valves to open. Start at {until} at the earliest.",
        "pre_open_now": "The boiler waits to start.",
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
        "off_summer": "léto, venku je nad mezí vytápění",
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
        "off_summer": "summer, the outdoor temperature is above the heating limit",
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
        "summer": "léto",
    },
    "en": {"auto": "auto", "manual": "manual", "off": "off", "away": "away", "summer": "summer"},
}


def language(hass: HomeAssistant) -> str:
    """Return cs or en from the Home Assistant language."""
    return "cs" if (hass.config.language or "").startswith("cs") else "en"


def clock(value: Any) -> str:
    """Local time of day, e.g. 00:55:12."""
    if not isinstance(value, datetime):
        return "?"
    return dt_util.as_local(value).strftime("%H:%M:%S")


def moment(value: Any) -> str:
    """Time of day today ("v 15:00"), with the date on another day ("12. 10. v 15:00")."""
    if not isinstance(value, datetime):
        return "?"
    local = dt_util.as_local(value)
    if local.date() == dt_util.now().date():
        return local.strftime("%H:%M")
    return f"{local.day}. {local.month}. {local:%H:%M}"


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
    return text


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
    return message


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
