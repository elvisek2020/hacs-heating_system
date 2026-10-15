"""Heating Controller.

Rooms with 1..n sensors and 1..n NO/NC valves, an on/off boiler with
anti-cycling, windows, frost protection, summer mode and manual heating.
"""

from __future__ import annotations

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .card import async_register_card
from .const import (
    ATTR_DURATION,
    ATTR_MINUTES,
    DOMAIN,
    MANUAL_DURATION_MAX,
    MANUAL_DURATION_MIN,
    SERVICE_GENERATE_DASHBOARD,
    SERVICE_START_MANUAL,
    SERVICE_STOP,
    SERVICE_STOP_VENTILATION,
    SERVICE_VENTILATE,
)
from .dashboard import build_dashboard
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime, structure_of

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

START_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=MANUAL_DURATION_MIN, max=MANUAL_DURATION_MAX)
        )
    }
)


VENTILATE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_MINUTES): vol.All(vol.Coerce(float), vol.Range(min=1, max=240)),
    }
)
STOP_VENTILATION_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})


def _airing_rooms(
    hass: HomeAssistant, runtime: HydronicHeatingRuntime, entity_ids: list[str] | None
) -> list[str] | None:
    """Rooms of the entities of a service call; None (all rooms) without entities.

    A room entity stands for its room, a floor airing switch for its floor and the
    airing switch of the house for all rooms (FR-WIN-07).
    """
    if not entity_ids:
        return None
    registry = er.async_get(hass)
    prefix = f"{runtime.entry.entry_id}_"
    found: list[str] = []
    for entity_id in entity_ids:
        entry = registry.async_get(entity_id)
        if entry is None or entry.platform != DOMAIN or not entry.unique_id.startswith(prefix):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_heating_entity",
                translation_placeholders={"entity_id": entity_id},
            )
        key = entry.unique_id.removeprefix(prefix)
        if key == "ventilation":
            rooms = [room.room_id for room in runtime.rooms]
        elif key.startswith("ventilation_"):
            rooms = runtime.floor_room_ids(key.removeprefix("ventilation_"))
        else:
            rooms = [room.room_id for room in runtime.rooms if key.startswith(f"{room.room_id}_")]
        if not rooms:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_heating_entity",
                translation_placeholders={"entity_id": entity_id},
            )
        found += [room for room in rooms if room not in found]
    return found


def _runtime(hass: HomeAssistant) -> HydronicHeatingRuntime:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
    return entries[0].runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services (FR-MAN-01, FR-MAN-03) and the scheme card (FR-UI-25)."""

    async def start_manual(call: ServiceCall) -> None:
        _runtime(hass).start_manual(call.data[ATTR_DURATION])

    async def stop(call: ServiceCall) -> None:
        _runtime(hass).stop_manual()

    hass.services.async_register(DOMAIN, SERVICE_START_MANUAL, start_manual, START_MANUAL_SCHEMA)

    async def generate_dashboard(call: ServiceCall) -> ServiceResponse:
        return build_dashboard(_runtime(hass))

    hass.services.async_register(DOMAIN, SERVICE_STOP, stop)

    async def ventilate(call: ServiceCall) -> None:
        runtime = _runtime(hass)
        rooms = _airing_rooms(hass, runtime, call.data.get(ATTR_ENTITY_ID))
        runtime.ventilate(rooms, call.data.get(ATTR_MINUTES))

    async def stop_ventilation(call: ServiceCall) -> None:
        runtime = _runtime(hass)
        runtime.stop_ventilation(_airing_rooms(hass, runtime, call.data.get(ATTR_ENTITY_ID)))

    hass.services.async_register(DOMAIN, SERVICE_VENTILATE, ventilate, VENTILATE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_VENTILATION, stop_ventilation, STOP_VENTILATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_DASHBOARD,
        generate_dashboard,
        supports_response=SupportsResponse.ONLY,
    )
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HydronicConfigEntry) -> bool:
    """Set up the heating system from a config entry."""
    runtime = HydronicHeatingRuntime(hass, entry)
    entry.runtime_data = runtime
    await runtime.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HydronicConfigEntry) -> bool:
    """Unload a config entry and save the control state."""
    runtime = entry.runtime_data
    # Stop first: the platforms remove our own entities, which must not trigger steps.
    runtime.deactivate()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await runtime.async_save()
    else:
        runtime.reactivate()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: HydronicConfigEntry) -> None:
    """Apply changes live; reload only when entities have to be added or removed."""
    runtime = entry.runtime_data
    if structure_of(entry) != runtime.structure:
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        runtime.apply_config()
