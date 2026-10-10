"""Hydronic Heating Controller.

Rooms with 1..n sensors and 1..n NO/NC valves, an on/off boiler with
anti-cycling, windows, frost protection, summer mode and manual heating.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    ATTR_DURATION,
    DOMAIN,
    MANUAL_DURATION_MAX,
    MANUAL_DURATION_MIN,
    SERVICE_GENERATE_DASHBOARD,
    SERVICE_START_MANUAL,
    SERVICE_STOP,
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


def _runtime(hass: HomeAssistant) -> HydronicHeatingRuntime:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
    return entries[0].runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services (FR-MAN-01, FR-MAN-03)."""

    async def start_manual(call: ServiceCall) -> None:
        _runtime(hass).start_manual(call.data[ATTR_DURATION])

    async def stop(call: ServiceCall) -> None:
        _runtime(hass).stop_manual()

    hass.services.async_register(DOMAIN, SERVICE_START_MANUAL, start_manual, START_MANUAL_SCHEMA)

    async def generate_dashboard(call: ServiceCall) -> ServiceResponse:
        return build_dashboard(_runtime(hass))

    hass.services.async_register(DOMAIN, SERVICE_STOP, stop)
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_DASHBOARD,
        generate_dashboard,
        supports_response=SupportsResponse.ONLY,
    )
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
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: HydronicConfigEntry) -> None:
    """Apply changes live; reload only when entities have to be added or removed."""
    runtime = entry.runtime_data
    if structure_of(entry) != runtime.structure:
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        runtime.apply_config()
