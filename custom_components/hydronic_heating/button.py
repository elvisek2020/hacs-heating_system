"""Manual heating buttons and stop (FR-MAN-01, FR-MAN-03)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Add one button per manual duration and a stop button."""
    runtime = entry.runtime_data
    buttons: list[ButtonEntity] = [
        ManualButton(runtime, minutes) for minutes in runtime.controller.cfg.manual_durations
    ]
    buttons.append(StopButton(runtime))
    async_add_entities(buttons)


class ManualButton(HydronicEntity, ButtonEntity):
    """Start manual heating for a fixed time (`button.hh_manual_<minutes>`)."""

    def __init__(self, runtime: HydronicHeatingRuntime, minutes: int) -> None:
        """Initialize."""
        super().__init__(runtime, "button", f"manual_{minutes}")
        self._attr_translation_key = "manual"
        self._attr_translation_placeholders = {"minutes": str(minutes)}
        self.minutes = minutes

    async def async_press(self) -> None:
        """Start or prolong manual heating."""
        self.runtime.start_manual(self.minutes)


class StopButton(HydronicEntity, ButtonEntity):
    """Stop manual heating (`button.hh_stop`)."""

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        """Initialize."""
        super().__init__(runtime, "button", "stop")

    async def async_press(self) -> None:
        """Stop manual heating."""
        self.runtime.stop_manual()
