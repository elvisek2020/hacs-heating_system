"""Texts of notifications (FR-SAFE-04) in Czech and English."""

from __future__ import annotations

from collections.abc import Mapping

from homeassistant.core import HomeAssistant

MESSAGES: dict[str, dict[str, tuple[str, str]]] = {
    "cs": {
        "fault_safe": (
            "Topení je v poruše",
            "Kotel byl přepnut do bezpečného stavu: {reason}. Topení je vypnuté a ventily "
            "jsou v klidovém stavu, protimrazovou ochranu nelze zajistit kotlem.",
        ),
        "no_heat": (
            "Kotel běží, ale netopí",
            "Kotel běží {minutes} min, ale teplota vody nestoupla ani o {rise} °C. "
            "Zkontrolujte kotel (porucha, tlak vody), zavřený okruh nebo vzduch v systému. "
            "Hlášení zmizí, až teplota vody při běhu kotle zase stoupne.",
        ),
        "sensor_failure": (
            "Výpadek čidel: {room}",
            "Žádné teplotní čidlo místnosti {room} nemá platnou hodnotu. Místnost jede "
            "v záložním režimu podle nastavení.",
        ),
        "window_long": (
            "Dlouho otevřené okno: {room}",
            "Okno v místnosti {room} je otevřené déle, než je povolená doba blokace. "
            "Místnost drží jen protimrazovou ochranu.",
        ),
        "not_reached": (
            "Teplota není dosažena: {room}",
            "Místnost {room} ani po 3 hodinách topení nedosáhla cílové teploty "
            "(odchylka větší než 1,5 °C).",
        ),
        "valve_command": (
            "Ventil nereaguje: {room}",
            "Ventil {entity} v místnosti {room} nereaguje na povel ani po opakování.",
        ),
        "valve_not_opening": (
            "Ventil asi neotvírá: {room}",
            "Ventil {entity} v místnosti {room} má být otevřený a kotel topí, ale trubka "
            "u ventilu se neohřála. Zkontrolujte hlavici a ventil. Hlášení zmizí samo, "
            "až kontrola projde.",
        ),
        "valve_not_closing": (
            "Ventil asi nezavírá: {room}",
            "Ventil {entity} v místnosti {room} má být zavřený, ale trubka u ventilu se "
            "ohřívá. Zkontrolujte hlavici a ventil. Hlášení zmizí samo, až kontrola projde.",
        ),
    },
    "en": {
        "fault_safe": (
            "Heating fault",
            "The boiler was switched to the safe state: {reason}. Heating is off and the "
            "valves are in their idle position; frost protection by the boiler is not possible.",
        ),
        "no_heat": (
            "Boiler runs but does not heat",
            "The boiler has run for {minutes} min but the water temperature has not risen by "
            "{rise} °C. Check the boiler (fault, water pressure), a closed circuit or air in "
            "the system. The message clears when the water warms up again while the boiler runs.",
        ),
        "sensor_failure": (
            "Sensor failure: {room}",
            "No temperature sensor of {room} has a valid value. The room runs in the "
            "configured fallback mode.",
        ),
        "window_long": (
            "Window open for too long: {room}",
            "The window in {room} has been open longer than the allowed block time. "
            "The room keeps frost protection only.",
        ),
        "not_reached": (
            "Temperature not reached: {room}",
            "{room} has not reached its target temperature after 3 hours of heating "
            "(deviation above 1.5 °C).",
        ),
        "valve_command": (
            "Valve not responding: {room}",
            "Valve {entity} in {room} does not follow commands, even after retries.",
        ),
        "valve_not_opening": (
            "Valve does not seem to open: {room}",
            "Valve {entity} in {room} should be open and the boiler heats, but the pipe at "
            "the valve did not warm up. Check the head and the valve. The message clears "
            "when the check passes.",
        ),
        "valve_not_closing": (
            "Valve does not seem to close: {room}",
            "Valve {entity} in {room} should be closed, but the pipe at the valve warms up. "
            "Check the head and the valve. The message clears when the check passes.",
        ),
    },
}

REASONS: dict[str, dict[str, str]] = {
    "cs": {
        "boiler_unavailable": "entita kotle je nedostupná",
        "boiler_command": "kotel nereaguje na povel",
        "no_flow": "ventily se neotevřely, chybí průtok",
    },
    "en": {
        "boiler_unavailable": "the boiler entity is unavailable",
        "boiler_command": "the boiler does not follow commands",
        "no_flow": "the valves did not open, no flow",
    },
}


def _language(hass: HomeAssistant) -> str:
    return "cs" if (hass.config.language or "").startswith("cs") else "en"


def reason_text(hass: HomeAssistant, reason: str) -> str:
    """Translate a fault reason code."""
    return REASONS[_language(hass)].get(reason, reason)


def notification_text(
    hass: HomeAssistant, kind: str, placeholders: Mapping[str, str]
) -> tuple[str, str]:
    """Return title and message of a notification."""
    title, message = MESSAGES[_language(hass)][kind]
    return title.format(**placeholders), message.format(**placeholders)
