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
    },
    "en": {
        "fault_safe": (
            "Heating fault",
            "The boiler was switched to the safe state: {reason}. Heating is off and the "
            "valves are in their idle position; frost protection by the boiler is not possible.",
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
