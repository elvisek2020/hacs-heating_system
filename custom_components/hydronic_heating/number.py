"""Comfort and eco temperature of each room (`number.hh_<room>_comfort`, `_eco`)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_COMFORT_TEMP, CONF_ECO_TEMP
from .core.model import RoomConfig
from .entity import DemoEntity, HydronicEntity
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime

PARALLEL_UPDATES = 0

ROOM_NUMBERS = {"comfort": CONF_COMFORT_TEMP, "eco": CONF_ECO_TEMP}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the temperature settings of each room."""
    runtime = entry.runtime_data
    if runtime.layout is not None and runtime.layout.house:
        async_add_entities([DemoOutdoorTemperature(runtime)])
    for room in runtime.rooms:
        async_add_entities(
            (RoomTemperature(runtime, room, key, conf) for key, conf in ROOM_NUMBERS.items()),
            config_subentry_id=room.room_id,
        )


class RoomTemperature(HydronicEntity, NumberEntity):
    """A preset temperature stored in the room settings."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 5
    _attr_native_max_value = 30
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX

    def __init__(
        self, runtime: HydronicHeatingRuntime, room: RoomConfig, key: str, conf_key: str
    ) -> None:
        """Initialize."""
        super().__init__(runtime, "number", key, room)
        self.conf_key = conf_key

    @property
    def native_value(self) -> float:
        """Stored temperature."""
        cfg = self.room.cfg
        return cfg.comfort_temp if self.conf_key == CONF_COMFORT_TEMP else cfg.eco_temp

    async def async_set_native_value(self, value: float) -> None:
        """Store the temperature in the room settings."""
        self.runtime.set_room_value(self.room_id, self.conf_key, value)


class DemoOutdoorTemperature(DemoEntity, NumberEntity):
    """Outdoor temperature of the virtual house."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = -25
    _attr_native_max_value = 35
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX

    def __init__(self, runtime: HydronicHeatingRuntime) -> None:
        """Initialize."""
        super().__init__(runtime, "number", "demo_outdoor_temperature")

    @property
    def native_value(self) -> float:
        """Simulated outdoor temperature."""
        return self.simulator.outdoor

    async def async_set_native_value(self, value: float) -> None:
        """Change the simulated outdoor temperature."""
        self.simulator.set_value("outdoor", None, value)
