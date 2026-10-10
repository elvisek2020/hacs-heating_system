"""System mode select (`select.hh_system_mode`, FR-MODE-01)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .core.model import SystemMode
from .entity import HydronicEntity
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the system mode select."""
    async_add_entities([SystemModeSelect(entry.runtime_data)])


class SystemModeSelect(HydronicEntity, SelectEntity):
    """auto / manual / off / away / summer."""

    _attr_options = [mode.value for mode in SystemMode]

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        """Initialize."""
        super().__init__(runtime, "select", "system_mode")

    @property
    def current_option(self) -> str:
        """Selected mode."""
        return self.controller.modes.mode.value

    async def async_select_option(self, option: str) -> None:
        """Select a mode; manual starts the first configured duration."""
        self.runtime.set_mode(option)
