"""Shadow mode switch (`switch.hh_shadow_mode`, FR-SAFE-05)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HydronicEntity
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the shadow mode switch."""
    async_add_entities([ShadowModeSwitch(entry.runtime_data)])


class ShadowModeSwitch(HydronicEntity, SwitchEntity):
    """Calculate everything but switch no outputs."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        """Initialize."""
        super().__init__(runtime, "switch", "shadow_mode")

    @property
    def is_on(self) -> bool:
        """Shadow mode is active."""
        return self.controller.cfg.shadow_mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Stop switching outputs."""
        self.runtime.set_shadow_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Start switching outputs."""
        self.runtime.set_shadow_mode(False)
