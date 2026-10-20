"""Serve the animated scheme card and load it in the frontend (FR-UI-25).

The card ships with the integration, so it needs no separate install from HACS.
With resources in storage mode the card is a Lovelace resource, which loads
before a dashboard renders; an extra module loaded alongside could come too late
and leave "Custom element doesn't exist" after a reload. With YAML resources the
card is added to every page instead. The file is cached for long, a fast load
leaves less room for that race; the version in the URL changes with the restart
an update needs, so browsers then load the new file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILE = Path(__file__).parent / "frontend" / "hydronic-heating-flow-card.js"
CARD_URL = f"/{DOMAIN}/hydronic-heating-flow-card.js"
CARD_TYPE = "custom:hydronic-heating-flow-card"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card file and load it on the dashboards; skipped without HTTP."""
    if hass.http is None:
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=True)]
    )
    if "frontend" not in hass.config.components:
        return
    version = (await async_get_integration(hass, DOMAIN)).version
    url = f"{CARD_URL}?v={version}"
    if not await _async_set_resource(hass, url):
        add_extra_js_url(hass, url)


async def async_unregister_card(hass: HomeAssistant) -> None:
    """Remove the Lovelace resource of the card when the integration is removed."""
    if (resources := _storage_resources(hass)) is None:
        return
    try:
        await resources.async_get_info()
        for item in _own_items(resources):
            await resources.async_delete_item(item["id"])
    except Exception:
        _LOGGER.exception("Removing the Lovelace resource of the card failed")


def _storage_resources(hass: HomeAssistant) -> ResourceStorageCollection | None:
    """Lovelace resources kept in storage, or None with YAML resources."""
    data = hass.data.get(LOVELACE_DATA)
    resources = getattr(data, "resources", None)
    return resources if isinstance(resources, ResourceStorageCollection) else None


def _own_items(resources: ResourceStorageCollection) -> list[dict]:
    """Resources that load this card, whatever version their URL carries."""
    return [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).split("?", 1)[0] == CARD_URL
    ]


async def _async_set_resource(hass: HomeAssistant, url: str) -> bool:
    """Keep exactly one module resource with the current URL; False without storage."""
    if (resources := _storage_resources(hass)) is None:
        return False
    try:
        await resources.async_get_info()  # loads the stored resources
        first, *duplicates = _own_items(resources) or [None]
        if first is None:
            await resources.async_create_item({"res_type": "module", "url": url})
        elif first.get("url") != url or first.get("type") != "module":
            await resources.async_update_item(first["id"], {"res_type": "module", "url": url})
        for item in duplicates:
            await resources.async_delete_item(item["id"])
    except Exception:
        # The card still loads as an extra module; setup must not fail for it.
        _LOGGER.exception("Registering the card as a Lovelace resource failed")
        return False
    return True
