"""Comfort, eco and away temperature of each room (`number.hh_<room>_comfort`, ...)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_AWAY_TEMP, CONF_COMFORT_TEMP, CONF_ECO_TEMP
from .core.model import RoomConfig
from .entity import DemoEntity, HydronicEntity
from .runtime import HydronicConfigEntry, HydronicHeatingRuntime

PARALLEL_UPDATES = 0

ROOM_NUMBERS = {"comfort": CONF_COMFORT_TEMP, "eco": CONF_ECO_TEMP, "away": CONF_AWAY_TEMP}
STEP = 0.5


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
    _attr_native_step = STEP
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
        return {
            CONF_COMFORT_TEMP: cfg.comfort_temp,
            CONF_ECO_TEMP: cfg.eco_temp,
            CONF_AWAY_TEMP: cfg.away_temp,
        }[self.conf_key]

    # The bounds keep the rules of the room settings: frost < eco <= comfort and
    # frost < away, so the -/+ buttons cannot store an invalid combination.
    @property
    def native_min_value(self) -> float:
        """Comfort not below eco; eco and away above frost protection."""
        cfg = self.room.cfg
        if self.conf_key == CONF_COMFORT_TEMP:
            return max(5.0, cfg.eco_temp)
        return max(5.0, cfg.frost_temp + STEP)

    @property
    def native_max_value(self) -> float:
        """Eco not above comfort; away as in the room settings."""
        cfg = self.room.cfg
        if self.conf_key == CONF_ECO_TEMP:
            return cfg.comfort_temp
        return 25.0 if self.conf_key == CONF_AWAY_TEMP else 30.0

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
