"""Serve the animated scheme card and load it in the frontend (FR-UI-25).

The card ships with the integration, so it needs no separate install from HACS.
The version in the URL makes browsers load the new file after an update.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

CARD_FILE = Path(__file__).parent / "frontend" / "hydronic-heating-flow-card.js"
CARD_URL = f"/{DOMAIN}/hydronic-heating-flow-card.js"
CARD_TYPE = "custom:hydronic-heating-flow-card"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card file and add it to every dashboard; skipped without HTTP."""
    if hass.http is None:
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    if "frontend" in hass.config.components:
        version = (await async_get_integration(hass, DOMAIN)).version
        add_extra_js_url(hass, f"{CARD_URL}?v={version}")
