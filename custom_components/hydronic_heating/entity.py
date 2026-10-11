"""Base entity: devices, unique IDs and `hh_` entity IDs (PRD chapter 9)."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, ENTITY_PREFIX
from .core.controller import HydronicController
from .core.model import RoomConfig
from .core.room import RoomController
from .demo import DemoSimulator
from .runtime import HydronicHeatingRuntime

MANUFACTURER = "Heating Controller"


class HydronicEntity(Entity):
    """Entity of the heating system or of one room."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: HydronicHeatingRuntime,
        domain: str,
        key: str,
        room: RoomConfig | None = None,
    ) -> None:
        """Set identity; `key` is the translation key and the entity ID suffix."""
        self.runtime = runtime
        self.room_id = room.room_id if room else None
        entry = runtime.entry
        if key:
            self._attr_translation_key = key
        system_device = (DOMAIN, entry.entry_id)
        if room is None:
            self._attr_unique_id = f"{entry.entry_id}_{key}"
            self._attr_device_info = DeviceInfo(
                identifiers={system_device},
                name=entry.title,
                manufacturer=MANUFACTURER,
                model="Heating system",
                entry_type=DeviceEntryType.SERVICE,
            )
            object_id = f"{ENTITY_PREFIX}_{key}"
        else:
            self._attr_unique_id = f"{entry.entry_id}_{room.room_id}_{key or 'climate'}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, room.room_id)},
                name=room.name,
                manufacturer=MANUFACTURER,
                model="Room",
            )
            object_id = "_".join(p for p in (ENTITY_PREFIX, room.slug, key) if p)
        self.entity_id = f"{domain}.{object_id}"

    @property
    def controller(self) -> HydronicController:
        """The control core."""
        return self.runtime.controller

    @property
    def room(self) -> RoomController:
        """The room controller of a room entity."""
        assert self.room_id is not None
        return self.controller.rooms[self.room_id]

    @property
    def available(self) -> bool:
        """Room entities disappear with their room on reconfiguration."""
        return self.room_id is None or self.room_id in self.controller.rooms

    async def async_added_to_hass(self) -> None:
        """Follow controller updates."""
        self.async_on_remove(self.runtime.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class DemoEntity(HydronicEntity):
    """Entity of the demo mode; follows the simulator as well as the controller."""

    @property
    def simulator(self) -> DemoSimulator:
        """The demo simulator (only exists while the demo is active)."""
        assert self.runtime.demo is not None
        return self.runtime.demo

    async def async_added_to_hass(self) -> None:
        """Follow simulator updates too."""
        await super().async_added_to_hass()
        self.async_on_remove(self.simulator.async_add_listener(self._handle_update))
