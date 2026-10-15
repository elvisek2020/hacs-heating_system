"""Config flow, options flow and room subentry flow (PRD chapter 10.1)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.util import slugify
import voluptuous as vol

from .const import (
    ABSENCE_PRESETS,
    AGGREGATIONS,
    COMBINE_OPTIONS,
    CONF_ABSENCE_PRESET,
    CONF_AGGREGATION,
    CONF_AREA_M2,
    CONF_AREA_WEIGHTING,
    CONF_AWAY_TEMP,
    CONF_BOILER_CYCLE_PERIOD,
    CONF_BOILER_DEMAND_HYSTERESIS,
    CONF_BOILER_DEMAND_THRESHOLD,
    CONF_BOILER_FIXED_FLOW_TEMP,
    CONF_BOILER_MAX_STARTS,
    CONF_BOILER_MIN_OFF,
    CONF_BOILER_MIN_ON,
    CONF_BOILER_OVERRUN,
    CONF_COLD_TOLERANCE,
    CONF_COMBINE,
    CONF_COMFORT_TEMP,
    CONF_COMMAND_RETRIES,
    CONF_COMMAND_VERIFY_TIMEOUT,
    CONF_CONTROL_ALGORITHM,
    CONF_CURVE_OFFSET,
    CONF_DEMO_MODE,
    CONF_DESIGN_FLOW_TEMP,
    CONF_DESIGN_OUTDOOR_TEMP,
    CONF_DUTY_MIN,
    CONF_ECO_TEMP,
    CONF_EQUITHERMAL_DUTY_ENABLED,
    CONF_EXERCISE_DURATION,
    CONF_EXERCISE_INTERVAL_DAYS,
    CONF_EXERCISE_PARALLEL,
    CONF_EXERCISE_TIME,
    CONF_EXPECTED_RETURN_ENTITY,
    CONF_FALLBACK_DEMAND,
    CONF_FALLBACK_HOLD,
    CONF_FAULT_RECOVERY_TIME,
    CONF_FEEDBACK_ENTITY,
    CONF_FLOW_CHECK_RISE,
    CONF_FLOW_CHECK_TIME,
    CONF_FLOW_TEMP_ENTITY,
    CONF_FLOW_TEMP_MAX,
    CONF_FLOW_TEMP_MIN,
    CONF_FROST_IDLE_MAX,
    CONF_FROST_OUTDOOR_PROTECTION,
    CONF_FROST_OUTDOOR_TEMP,
    CONF_FROST_TEMP,
    CONF_GLOBAL_WINDOW_COUNT,
    CONF_GLOBAL_WINDOW_DELAY,
    CONF_GLOBAL_WINDOW_MODE,
    CONF_GLOBAL_WINDOW_RATIO,
    CONF_HAS_BYPASS,
    CONF_HEARTBEAT_ENTITY,
    CONF_HEARTBEAT_INTERVAL,
    CONF_HEAT_SOURCE_ENTITY,
    CONF_HEAT_SOURCE_OFF_ENTITY,
    CONF_HEAT_SOURCE_ON_ENTITY,
    CONF_HEAT_SOURCE_SELECT_ENTITY,
    CONF_HEAT_SOURCE_SELECT_OFF,
    CONF_HEAT_SOURCE_SELECT_ON,
    CONF_HEAT_SOURCE_TYPE,
    CONF_HEATING_LIMIT,
    CONF_HOT_TOLERANCE,
    CONF_HOUSE_PRESENCE_ENTITY,
    CONF_HOUSE_SCHEDULE_ENTITY,
    CONF_IDLE_VALVE_POLICY,
    CONF_KEEP_ALIVE,
    CONF_LONG_AWAY_ENTITY,
    CONF_MANUAL_DURATIONS,
    CONF_MANUAL_RESTART_POLICY,
    CONF_MANUAL_SCOPE,
    CONF_MIN_OPEN_VALVES,
    CONF_MIN_ROOMS_CALLING,
    CONF_MIRROR_TIMER_ENTITY,
    CONF_NORMALLY_OPEN,
    CONF_NOTIFY_SERVICE,
    CONF_OUTDOOR_DAMPING_HOURS,
    CONF_OUTDOOR_SENSORS,
    CONF_PREHEAT_ENABLED,
    CONF_PREHEAT_MAX,
    CONF_PRESENCE_ENTITY,
    CONF_RADIATOR_EXPONENT,
    CONF_REFERENCE_ROOM_TEMP,
    CONF_ROOM_CALL_THRESHOLD,
    CONF_ROOM_NAME,
    CONF_ROOM_ORDER,
    CONF_SCHEDULE_ENTITY,
    CONF_SCHEDULE_MODE,
    CONF_SENSOR_FALLBACK,
    CONF_SENSOR_GRACE,
    CONF_SENSOR_MAX,
    CONF_SENSOR_MIN,
    CONF_SENSOR_STALE_TIMEOUT,
    CONF_SENSORS,
    CONF_SHADOW_MODE,
    CONF_STARTUP_GRACE,
    CONF_STOP_POLICY,
    CONF_STOP_RESPECTS_MIN_ON,
    CONF_TPI_COEF_EXT,
    CONF_TPI_COEF_INT,
    CONF_USE_FORECAST,
    CONF_VALVE_CHECK_CLOSED_RISE,
    CONF_VALVE_CHECK_HOT,
    CONF_VALVE_CHECK_RISE,
    CONF_VALVE_CHECK_TIME,
    CONF_VALVE_CLOSE_TIME,
    CONF_VALVE_ENTITY,
    CONF_VALVE_MIN_STATE_TIME,
    CONF_VALVE_OPEN_TIME,
    CONF_VALVE_PWM_PERIOD,
    CONF_VALVE_TEMP_ENTITY,
    CONF_VALVES,
    CONF_VENT_DETECT,
    CONF_VENT_DROP,
    CONF_VENT_FLOOR_AUTO,
    CONF_VENT_MANUAL,
    CONF_VENT_MAX,
    CONF_VENT_PAUSE,
    CONF_VENT_SCOPE,
    CONF_VENT_TIME,
    CONF_WEATHER_ENTITY,
    CONF_WEIGHT,
    CONF_WINDOW_CLOSE_DELAY,
    CONF_WINDOW_INVERT,
    CONF_WINDOW_MAX_BLOCK,
    CONF_WINDOW_OPEN_DELAY,
    CONF_WINDOW_OUTDOOR_CONDITION,
    CONF_WINDOWS,
    CONTROL_ALGORITHMS,
    DEFAULT_NAME,
    DEFAULT_OPTIONS,
    DEFAULT_ROOM,
    DEFAULT_VALVE,
    DEMO_MODES,
    DOMAIN,
    GLOBAL_WINDOW_MODES,
    HEAT_SOURCE_ACTIONS,
    HEAT_SOURCE_KEYS,
    HEAT_SOURCE_SELECT,
    HEAT_SOURCE_SWITCH,
    HEAT_SOURCE_TYPES,
    IDLE_VALVE_POLICIES,
    MANUAL_DURATION_MAX,
    MANUAL_DURATION_MIN,
    MANUAL_DURATIONS_MAX_COUNT,
    MANUAL_RESTART_POLICIES,
    MANUAL_SCOPES,
    SCHEDULE_MODES,
    SENSOR_FALLBACKS,
    STOP_POLICIES,
    SUBENTRY_ROOM,
    VALVE_DOMAINS,
    VENT_SCOPES,
)

type Errors = dict[str, str]
type Placeholders = dict[str, str]
type SchemaBuilder = Callable[[Mapping[str, Any]], vol.Schema]

OPTIONS_MENU = [
    "general",
    "heat_source",
    "outdoor",
    "boiler",
    "safety",
    "valves",
    "windows",
    "manual",
    "equithermal",
    "frost",
    "presence",
]

# --- Selector helpers ----------------------------------------------------


def _number(
    minimum: float, maximum: float, step: float = 1, unit: str | None = None
) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(
        min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
    )
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _choice(options: list[str], key: str, *, as_list: bool = False) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            translation_key=key,
            mode=selector.SelectSelectorMode.LIST
            if as_list
            else selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _entity(domain: str | list[str], *, multiple: bool = False) -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain, multiple=multiple))


_BOOL = selector.BooleanSelector()
_TEXT = selector.TextSelector()
_CELSIUS = UnitOfTemperature.CELSIUS


def _required(key: str, values: Mapping[str, Any]) -> vol.Required:
    """Return a required field prefilled with the current value, if any."""
    if values.get(key) is not None:
        return vol.Required(key, default=values[key])
    return vol.Required(key)


def _optional(key: str, values: Mapping[str, Any]) -> vol.Optional:
    """Return an optional field that can be cleared (suggested value, no default)."""
    return vol.Optional(key, description={"suggested_value": values.get(key)})


def _normalize(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _apply(current: Mapping[str, Any], schema: vol.Schema, user_input: Mapping[str, Any]) -> dict:
    """Merge a submitted form into stored values; cleared optional fields are removed."""
    result = dict(current)
    for marker in schema.schema:
        key = str(marker)
        if key in user_input:
            result[key] = _normalize(user_input[key])
        else:
            result.pop(key, None)
    return result


# --- Schemas: system -----------------------------------------------------


def _user_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=values.get(CONF_NAME, DEFAULT_NAME)): _TEXT,
            _required(CONF_SHADOW_MODE, values): _BOOL,
        }
    )


def _general_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_SHADOW_MODE, values): _BOOL,
            _required(CONF_DEMO_MODE, values): _choice(DEMO_MODES, CONF_DEMO_MODE, as_list=True),
        }
    )


def _heat_source_type_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_HEAT_SOURCE_TYPE, values): _choice(
                HEAT_SOURCE_TYPES, CONF_HEAT_SOURCE_TYPE, as_list=True
            )
        }
    )


_FEEDBACK_DOMAINS = ["binary_sensor", "switch", "input_boolean"]


def _heat_source_switch_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_HEAT_SOURCE_ENTITY, values): _entity(["switch", "input_boolean"]),
            _optional(CONF_FEEDBACK_ENTITY, values): _entity(_FEEDBACK_DOMAINS),
            _optional(CONF_FLOW_TEMP_ENTITY, values): _entity("sensor"),
        }
    )


def _heat_source_actions_schema(values: Mapping[str, Any]) -> vol.Schema:
    action_domains = ["script", "button", "input_button"]
    return vol.Schema(
        {
            _required(CONF_HEAT_SOURCE_ON_ENTITY, values): _entity(action_domains),
            _required(CONF_HEAT_SOURCE_OFF_ENTITY, values): _entity(action_domains),
            _optional(CONF_FEEDBACK_ENTITY, values): _entity(_FEEDBACK_DOMAINS),
            _optional(CONF_FLOW_TEMP_ENTITY, values): _entity("sensor"),
        }
    )


def _heat_source_select_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_HEAT_SOURCE_SELECT_ENTITY, values): _entity(["select", "input_select"]),
            _required(CONF_HEAT_SOURCE_SELECT_ON, values): _TEXT,
            _required(CONF_HEAT_SOURCE_SELECT_OFF, values): _TEXT,
            _optional(CONF_FEEDBACK_ENTITY, values): _entity(_FEEDBACK_DOMAINS),
            _optional(CONF_FLOW_TEMP_ENTITY, values): _entity("sensor"),
        }
    )


_HEAT_SOURCE_SCHEMAS: dict[str, SchemaBuilder] = {
    HEAT_SOURCE_SWITCH: _heat_source_switch_schema,
    HEAT_SOURCE_ACTIONS: _heat_source_actions_schema,
    HEAT_SOURCE_SELECT: _heat_source_select_schema,
}


def _outdoor_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_OUTDOOR_SENSORS, default=list(values.get(CONF_OUTDOOR_SENSORS, []))
            ): _entity("sensor", multiple=True),
            _optional(CONF_WEATHER_ENTITY, values): _entity("weather"),
        }
    )


def _protection_schema(values: Mapping[str, Any]) -> vol.Schema:
    """Return the main protection parameters asked during the initial setup."""
    return vol.Schema(
        {
            _required(CONF_BOILER_MIN_ON, values): _number(0, 60, unit="min"),
            _required(CONF_BOILER_MIN_OFF, values): _number(0, 60, unit="min"),
            _required(CONF_BOILER_MAX_STARTS, values): _number(1, 12),
            _required(CONF_BOILER_OVERRUN, values): _number(0, 900, unit="s"),
            _required(CONF_HAS_BYPASS, values): _BOOL,
            _required(CONF_MIN_OPEN_VALVES, values): _number(0, 20),
        }
    )


def _boiler_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_BOILER_MIN_ON, values): _number(0, 60, unit="min"),
            _required(CONF_BOILER_MIN_OFF, values): _number(0, 60, unit="min"),
            _required(CONF_BOILER_MAX_STARTS, values): _number(1, 12),
            _required(CONF_BOILER_OVERRUN, values): _number(0, 900, unit="s"),
            _required(CONF_BOILER_DEMAND_THRESHOLD, values): _number(1, 100, unit="%"),
            _required(CONF_BOILER_DEMAND_HYSTERESIS, values): _number(0, 50, unit="%"),
            _required(CONF_ROOM_CALL_THRESHOLD, values): _number(1, 100, unit="%"),
            _required(CONF_MIN_ROOMS_CALLING, values): _number(1, 20),
            _required(CONF_COMBINE, values): _choice(COMBINE_OPTIONS, CONF_COMBINE),
            _required(CONF_AREA_WEIGHTING, values): _BOOL,
            _required(CONF_HAS_BYPASS, values): _BOOL,
            _required(CONF_MIN_OPEN_VALVES, values): _number(0, 20),
        }
    )


def _safety_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_KEEP_ALIVE, values): _number(0, 3600, unit="s"),
            _required(CONF_COMMAND_VERIFY_TIMEOUT, values): _number(2, 120, unit="s"),
            _required(CONF_COMMAND_RETRIES, values): _number(0, 5),
            _required(CONF_STARTUP_GRACE, values): _number(30, 600, unit="s"),
            _required(CONF_FAULT_RECOVERY_TIME, values): _number(60, 1800, unit="s"),
            _optional(CONF_HEARTBEAT_ENTITY, values): _entity(["switch", "input_boolean"]),
            _required(CONF_HEARTBEAT_INTERVAL, values): _number(10, 600, unit="s"),
            _required(CONF_FLOW_CHECK_TIME, values): _number(0, 120, unit="min"),
            _required(CONF_FLOW_CHECK_RISE, values): _number(1, 30, step=0.5, unit=_CELSIUS),
            _optional(CONF_NOTIFY_SERVICE, values): _TEXT,
        }
    )


def _valves_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_IDLE_VALVE_POLICY, values): _choice(
                IDLE_VALVE_POLICIES, CONF_IDLE_VALVE_POLICY
            ),
            _required(CONF_EXERCISE_INTERVAL_DAYS, values): _number(0, 60, unit="d"),
            _required(CONF_EXERCISE_DURATION, values): _number(60, 1800, unit="s"),
            _required(CONF_EXERCISE_TIME, values): selector.TimeSelector(),
            _required(CONF_EXERCISE_PARALLEL, values): _number(1, 10),
            # FR-SAFE-09: check of the valves by the pipe temperature.
            _required(CONF_VALVE_CHECK_TIME, values): _number(0, 60, unit="min"),
            _required(CONF_VALVE_CHECK_RISE, values): _number(1, 20, step=0.5, unit="K"),
            _required(CONF_VALVE_CHECK_CLOSED_RISE, values): _number(1, 20, step=0.5, unit="K"),
            _required(CONF_VALVE_CHECK_HOT, values): _number(25, 70, unit=_CELSIUS),
        }
    )


def _windows_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_WINDOW_OPEN_DELAY, values): _number(0, 900, unit="s"),
            _required(CONF_WINDOW_CLOSE_DELAY, values): _number(0, 900, unit="s"),
            _required(CONF_WINDOW_OUTDOOR_CONDITION, values): _BOOL,
            _required(CONF_WINDOW_MAX_BLOCK, values): _number(5, 480, unit="min"),
            _required(CONF_GLOBAL_WINDOW_MODE, values): _choice(
                GLOBAL_WINDOW_MODES, CONF_GLOBAL_WINDOW_MODE
            ),
            _required(CONF_GLOBAL_WINDOW_COUNT, values): _number(1, 20),
            _required(CONF_GLOBAL_WINDOW_RATIO, values): _number(0.1, 1, step=0.05),
            _required(CONF_GLOBAL_WINDOW_DELAY, values): _number(0, 900, unit="s"),
            # FR-WIN-07: airing by hand.
            _required(CONF_VENT_MANUAL, values): _number(1, 120, unit="min"),
            _required(CONF_VENT_SCOPE, values): _choice(VENT_SCOPES, CONF_VENT_SCOPE),
            _required(CONF_VENT_FLOOR_AUTO, values): _BOOL,
        }
    )


def _manual_schema(values: Mapping[str, Any]) -> vol.Schema:
    current = [str(item) for item in values.get(CONF_MANUAL_DURATIONS, [])]
    defaults = [str(item) for item in DEFAULT_OPTIONS[CONF_MANUAL_DURATIONS]]
    options = sorted(set(current) | set(defaults), key=int)
    return vol.Schema(
        {
            vol.Required(CONF_MANUAL_DURATIONS, default=current): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options, multiple=True, custom_value=True, sort=True
                )
            ),
            _required(CONF_MANUAL_RESTART_POLICY, values): _choice(
                MANUAL_RESTART_POLICIES, CONF_MANUAL_RESTART_POLICY
            ),
            _required(CONF_MANUAL_SCOPE, values): _choice(MANUAL_SCOPES, CONF_MANUAL_SCOPE),
            _required(CONF_STOP_POLICY, values): _choice(STOP_POLICIES, CONF_STOP_POLICY),
            _required(CONF_STOP_RESPECTS_MIN_ON, values): _BOOL,
            _optional(CONF_MIRROR_TIMER_ENTITY, values): _entity("timer"),
        }
    )


def _equithermal_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_DESIGN_OUTDOOR_TEMP, values): _number(-25, 0, unit=_CELSIUS),
            _required(CONF_DESIGN_FLOW_TEMP, values): _number(35, 80, unit=_CELSIUS),
            _required(CONF_REFERENCE_ROOM_TEMP, values): _number(15, 25, 0.5, _CELSIUS),
            _required(CONF_RADIATOR_EXPONENT, values): _number(1.0, 1.5, step=0.05),
            _required(CONF_CURVE_OFFSET, values): _number(-10, 10, 0.5, "K"),
            _required(CONF_FLOW_TEMP_MIN, values): _number(20, 85, unit=_CELSIUS),
            _required(CONF_FLOW_TEMP_MAX, values): _number(20, 85, unit=_CELSIUS),
            _required(CONF_HEATING_LIMIT, values): _number(10, 22, 0.5, _CELSIUS),
            _required(CONF_OUTDOOR_DAMPING_HOURS, values): _number(0, 72, unit="h"),
            _required(CONF_EQUITHERMAL_DUTY_ENABLED, values): _BOOL,
            _required(CONF_BOILER_FIXED_FLOW_TEMP, values): _number(30, 85, unit=_CELSIUS),
            _required(CONF_BOILER_CYCLE_PERIOD, values): _number(10, 60, unit="min"),
            _required(CONF_DUTY_MIN, values): _number(0, 1, step=0.05),
            _required(CONF_USE_FORECAST, values): _BOOL,
        }
    )


def _frost_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_FROST_OUTDOOR_PROTECTION, values): _BOOL,
            _required(CONF_FROST_OUTDOOR_TEMP, values): _number(-25, 0, unit=_CELSIUS),
            _required(CONF_FROST_IDLE_MAX, values): _number(1, 48, unit="h"),
        }
    )


# Entities that say "present": on/off, home/not_home, or a count such as zone.home.
PRESENCE_DOMAINS = ["binary_sensor", "input_boolean", "person", "group", "zone", "sensor"]


SCHEDULE_DOMAINS = ["schedule", "input_boolean", "switch", "binary_sensor"]


def _presence_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _optional(CONF_HOUSE_SCHEDULE_ENTITY, values): _entity(SCHEDULE_DOMAINS),
            _optional(CONF_HOUSE_PRESENCE_ENTITY, values): _entity(PRESENCE_DOMAINS),
            _optional(CONF_LONG_AWAY_ENTITY, values): _entity(["binary_sensor", "input_boolean"]),
            _optional(CONF_EXPECTED_RETURN_ENTITY, values): _entity(["sensor", "input_datetime"]),
            _required(CONF_ABSENCE_PRESET, values): _choice(ABSENCE_PRESETS, CONF_ABSENCE_PRESET),
            _required(CONF_PREHEAT_ENABLED, values): _BOOL,
            _required(CONF_PREHEAT_MAX, values): _number(0.5, 12, 0.5, "h"),
        }
    )


# --- Schemas: room -------------------------------------------------------


def _room_basics_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_ROOM_NAME, values): _TEXT,
            _required(CONF_ROOM_ORDER, values): _number(0, 99),
            _required(CONF_COMFORT_TEMP, values): _number(5, 30, 0.5, _CELSIUS),
            _required(CONF_ECO_TEMP, values): _number(5, 30, 0.5, _CELSIUS),
            _required(CONF_AWAY_TEMP, values): _number(5, 25, 0.5, _CELSIUS),
            _required(CONF_FROST_TEMP, values): _number(3, 12, 0.5, _CELSIUS),
            _required(CONF_AREA_M2, values): _number(0, 200, 0.5, "m²"),
            _required(CONF_WEIGHT, values): _number(0, 5, step=0.1),
        }
    )


def _room_sensors_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_SENSORS, values): _entity(["sensor", "climate"], multiple=True),
            _required(CONF_AGGREGATION, values): _choice(AGGREGATIONS, CONF_AGGREGATION),
            _required(CONF_SENSOR_MIN, values): _number(-40, 80, unit=_CELSIUS),
            _required(CONF_SENSOR_MAX, values): _number(-40, 80, unit=_CELSIUS),
            _required(CONF_SENSOR_STALE_TIMEOUT, values): _number(0, 720, unit="min"),
            _required(CONF_SENSOR_GRACE, values): _number(0, 60, unit="min"),
            _required(CONF_SENSOR_FALLBACK, values): _choice(
                SENSOR_FALLBACKS, CONF_SENSOR_FALLBACK
            ),
            _required(CONF_FALLBACK_HOLD, values): _number(0, 480, unit="min"),
            _required(CONF_FALLBACK_DEMAND, values): _number(0, 100, unit="%"),
        }
    )


def _room_valves_schema(values: Mapping[str, Any]) -> vol.Schema:
    valve_ids = [valve[CONF_VALVE_ENTITY] for valve in values.get(CONF_VALVES, [])]
    key = vol.Required(CONF_VALVES, default=valve_ids) if valve_ids else vol.Required(CONF_VALVES)
    return vol.Schema({key: _entity(VALVE_DOMAINS, multiple=True)})


def _valve_schema(entity_id: str, values: Mapping[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    # Entities of the `valve` domain already report the physical state (FR-VAL-01).
    if not entity_id.startswith("valve."):
        fields[_required(CONF_NORMALLY_OPEN, values)] = _BOOL
    fields[_required(CONF_VALVE_OPEN_TIME, values)] = _number(0, 900, unit="s")
    fields[_required(CONF_VALVE_CLOSE_TIME, values)] = _number(0, 900, unit="s")
    fields[_optional(CONF_VALVE_TEMP_ENTITY, values)] = _entity("sensor")
    return vol.Schema(fields)


def _room_windows_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_WINDOWS, default=list(values.get(CONF_WINDOWS, []))): _entity(
                ["binary_sensor", "input_boolean"], multiple=True
            ),
            _required(CONF_WINDOW_INVERT, values): _BOOL,
            # FR-WIN-06: airing noticed by a fast temperature drop.
            _required(CONF_VENT_DETECT, values): _BOOL,
            _required(CONF_VENT_DROP, values): _number(0.3, 5, step=0.1, unit="K"),
            _required(CONF_VENT_TIME, values): _number(1, 30, unit="min"),
            _required(CONF_VENT_PAUSE, values): _number(5, 120, unit="min"),
            _required(CONF_VENT_MAX, values): _number(10, 240, unit="min"),
        }
    )


def _room_schedule_schema(values: Mapping[str, Any]) -> vol.Schema:
    mode = values.get(CONF_SCHEDULE_MODE) or (
        "own" if values.get(CONF_SCHEDULE_ENTITY) else "house"
    )
    return vol.Schema(
        {
            vol.Required(CONF_SCHEDULE_MODE, default=mode): _choice(
                SCHEDULE_MODES, CONF_SCHEDULE_MODE, as_list=True
            ),
            _optional(CONF_SCHEDULE_ENTITY, values): _entity(SCHEDULE_DOMAINS),
            _optional(CONF_PRESENCE_ENTITY, values): _entity(PRESENCE_DOMAINS),
            _optional(CONF_EXPECTED_RETURN_ENTITY, values): _entity(["sensor", "input_datetime"]),
        }
    )


def _room_control_schema(values: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_CONTROL_ALGORITHM, values): _choice(
                CONTROL_ALGORITHMS, CONF_CONTROL_ALGORITHM
            ),
            _required(CONF_COLD_TOLERANCE, values): _number(0, 2, 0.1, "K"),
            _required(CONF_HOT_TOLERANCE, values): _number(0, 2, 0.1, "K"),
            _required(CONF_TPI_COEF_INT, values): _number(0, 2, step=0.05),
            _required(CONF_TPI_COEF_EXT, values): _number(0, 0.2, step=0.005),
            _required(CONF_VALVE_PWM_PERIOD, values): _number(10, 120, unit="min"),
            _required(CONF_VALVE_MIN_STATE_TIME, values): _number(1, 30, unit="min"),
        }
    )


# --- Validation helpers --------------------------------------------------


def _non_temperature_entities(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    """Return sensors that report something other than a temperature."""
    bad = []
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if (
            entity_id.startswith("climate.")
            or state is None
            or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            continue
        if state.attributes.get(ATTR_DEVICE_CLASS) == "temperature":
            continue
        if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) in (
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        ):
            continue
        bad.append(entity_id)
    return bad


def _room_subentries(entry: ConfigEntry) -> list[ConfigSubentry]:
    return [sub for sub in entry.subentries.values() if sub.subentry_type == SUBENTRY_ROOM]


def _max_valve_time(rooms: list[Mapping[str, Any]]) -> int:
    times = [
        max(valve.get(CONF_VALVE_OPEN_TIME, 0), valve.get(CONF_VALVE_CLOSE_TIME, 0))
        for room in rooms
        for valve in room.get(CONF_VALVES, [])
    ]
    return int(max(times, default=0))


def _parse_durations(raw: list[str]) -> list[int] | None:
    try:
        durations = sorted({int(str(item).strip()) for item in raw})
    except ValueError:
        return None
    if not 1 <= len(durations) <= MANUAL_DURATIONS_MAX_COUNT:
        return None
    if not all(MANUAL_DURATION_MIN <= item <= MANUAL_DURATION_MAX for item in durations):
        return None
    return durations


# --- Steps shared by the config flow and the options flow -----------------


class _SystemSteps:
    """Heat source and outdoor steps, shared by the config and options flow."""

    hass: HomeAssistant
    _values: dict[str, Any]

    async def _async_heat_source_done(self) -> ConfigFlowResult:
        raise NotImplementedError

    async def _async_outdoor_done(self) -> ConfigFlowResult:
        raise NotImplementedError

    async def async_step_heat_source(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how the heat source is controlled (FR-BOI-01)."""
        if user_input is not None:
            heat_type = user_input[CONF_HEAT_SOURCE_TYPE]
            for other_type, keys in HEAT_SOURCE_KEYS.items():
                if other_type != heat_type:
                    for key in keys:
                        self._values.pop(key, None)
            self._values[CONF_HEAT_SOURCE_TYPE] = heat_type
            return await self._async_heat_source_form(heat_type)
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="heat_source", data_schema=_heat_source_type_schema(self._values)
        )

    async def async_step_heat_source_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Heat source controlled by a switch or input_boolean."""
        return await self._async_heat_source_form(HEAT_SOURCE_SWITCH, user_input)

    async def async_step_heat_source_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Heat source controlled by a pair of scripts or buttons."""
        return await self._async_heat_source_form(HEAT_SOURCE_ACTIONS, user_input)

    async def async_step_heat_source_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Heat source controlled by a select entity."""
        return await self._async_heat_source_form(HEAT_SOURCE_SELECT, user_input)

    async def _async_heat_source_form(
        self, heat_type: str, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        schema = _HEAT_SOURCE_SCHEMAS[heat_type](self._values)
        errors: Errors = {}
        if user_input is not None:
            if heat_type == HEAT_SOURCE_SELECT:
                errors = self._validate_select_heat_source(user_input)
            if not errors:
                self._values = _apply(self._values, schema, user_input)
                return await self._async_heat_source_done()
            schema = self.add_suggested_values_to_schema(schema, user_input)  # type: ignore[attr-defined]
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id=f"heat_source_{heat_type}", data_schema=schema, errors=errors
        )

    def _validate_select_heat_source(self, user_input: Mapping[str, Any]) -> Errors:
        on_option = user_input[CONF_HEAT_SOURCE_SELECT_ON]
        off_option = user_input[CONF_HEAT_SOURCE_SELECT_OFF]
        if on_option == off_option:
            return {"base": "select_options_equal"}
        state = self.hass.states.get(user_input[CONF_HEAT_SOURCE_SELECT_ENTITY])
        options = state.attributes.get("options") if state else None
        if options and on_option not in options:
            return {CONF_HEAT_SOURCE_SELECT_ON: "invalid_select_option"}
        if options and off_option not in options:
            return {CONF_HEAT_SOURCE_SELECT_OFF: "invalid_select_option"}
        return {}

    async def async_step_outdoor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Outdoor temperature sources (FR-EQ-01)."""
        schema = _outdoor_schema(self._values)
        errors: Errors = {}
        if user_input is not None:
            if _non_temperature_entities(self.hass, user_input.get(CONF_OUTDOOR_SENSORS, [])):
                errors[CONF_OUTDOOR_SENSORS] = "not_temperature_sensor"
            else:
                self._values = _apply(self._values, schema, user_input)
                return await self._async_outdoor_done()
            schema = self.add_suggested_values_to_schema(schema, user_input)  # type: ignore[attr-defined]
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="outdoor", data_schema=schema, errors=errors
        )


# --- Config flow ---------------------------------------------------------


class HydronicHeatingConfigFlow(_SystemSteps, ConfigFlow, domain=DOMAIN):
    """Initial setup: name, heat source, outdoor temperature, protection."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Start with the PRD defaults."""
        self._values = dict(DEFAULT_OPTIONS)
        self._name = DEFAULT_NAME

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HydronicHeatingOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Rooms are config subentries (FR-ROOM-01)."""
        return {SUBENTRY_ROOM: RoomSubentryFlowHandler}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """System name and shadow mode."""
        if user_input is not None:
            self._name = user_input[CONF_NAME].strip() or DEFAULT_NAME
            self._values[CONF_SHADOW_MODE] = user_input[CONF_SHADOW_MODE]
            return await self.async_step_heat_source()
        return self.async_show_form(step_id="user", data_schema=_user_schema(self._values))

    async def _async_heat_source_done(self) -> ConfigFlowResult:
        return await self.async_step_outdoor()

    async def _async_outdoor_done(self) -> ConfigFlowResult:
        return await self.async_step_protection()

    async def async_step_protection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the main protection parameters, then create the entry."""
        schema = _protection_schema(self._values)
        if user_input is not None:
            self._values = _apply(self._values, schema, user_input)
            return self.async_create_entry(title=self._name, data={}, options=self._values)
        return self.async_show_form(step_id="protection", data_schema=schema)


# --- Options flow --------------------------------------------------------


class HydronicHeatingOptionsFlow(_SystemSteps, OptionsFlow):
    """All system parameters, grouped in a menu (NFR-13)."""

    def __init__(self) -> None:
        """Values are loaded in the first step, when config_entry is available."""
        self._values: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the settings menu."""
        self._values = {**DEFAULT_OPTIONS, **self.config_entry.options}
        return self.async_show_menu(step_id="init", menu_options=OPTIONS_MENU)

    def _save(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._values)

    async def _async_heat_source_done(self) -> ConfigFlowResult:
        return self._save()

    async def _async_outdoor_done(self) -> ConfigFlowResult:
        return self._save()

    async def _async_form(
        self,
        step_id: str,
        builder: SchemaBuilder,
        user_input: dict[str, Any] | None,
        validate: Callable[[dict[str, Any]], tuple[Errors, Placeholders]] | None = None,
    ) -> ConfigFlowResult:
        schema = builder(self._values)
        errors: Errors = {}
        placeholders: Placeholders = {}
        if user_input is not None:
            if validate is not None:
                errors, placeholders = validate(user_input)
            if not errors:
                self._values = _apply(self._values, schema, user_input)
                return self._save()
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    def _rooms(self) -> list[Mapping[str, Any]]:
        return [sub.data for sub in _room_subentries(self.config_entry)]

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Shadow mode."""
        return await self._async_form("general", _general_schema, user_input)

    async def async_step_boiler(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Boiler protection and demand arbitration."""

        def validate(data: dict[str, Any]) -> tuple[Errors, Placeholders]:
            if data[CONF_BOILER_DEMAND_HYSTERESIS] >= data[CONF_BOILER_DEMAND_THRESHOLD]:
                return {CONF_BOILER_DEMAND_HYSTERESIS: "hysteresis_too_large"}, {}
            if data[CONF_AREA_WEIGHTING]:
                missing = [
                    room.get(CONF_ROOM_NAME, "?")
                    for room in self._rooms()
                    if not room.get(CONF_AREA_M2)
                ]
                if missing:
                    return {CONF_AREA_WEIGHTING: "area_missing"}, {"rooms": ", ".join(missing)}
            return {}, {}

        return await self._async_form("boiler", _boiler_schema, user_input, validate)

    async def async_step_safety(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Command verification, watchdog and notifications."""

        def validate(data: dict[str, Any]) -> tuple[Errors, Placeholders]:
            service = data.get(CONF_NOTIFY_SERVICE)
            if service:
                domain, _, name = service.partition(".")
                if (
                    domain != "notify"
                    or not name
                    or not self.hass.services.has_service("notify", name)
                ):
                    return {CONF_NOTIFY_SERVICE: "notify_service_not_found"}, {}
            return {}, {}

        return await self._async_form("safety", _safety_schema, user_input, validate)

    async def async_step_valves(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Idle valve policy and valve exercise (FR-VAL-06, FR-VAL-07)."""

        def validate(data: dict[str, Any]) -> tuple[Errors, Placeholders]:
            minimum = _max_valve_time(self._rooms()) + 60
            if data[CONF_EXERCISE_DURATION] < minimum:
                return {CONF_EXERCISE_DURATION: "exercise_too_short"}, {"minimum": str(minimum)}
            return {}, {}

        return await self._async_form("valves", _valves_schema, user_input, validate)

    async def async_step_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Window delays and the global window threshold (FR-WIN)."""
        return await self._async_form("windows", _windows_schema, user_input)

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manual mode with timer (FR-MAN)."""

        def validate(data: dict[str, Any]) -> tuple[Errors, Placeholders]:
            durations = _parse_durations(data[CONF_MANUAL_DURATIONS])
            if durations is None:
                return {CONF_MANUAL_DURATIONS: "invalid_durations"}, {}
            data[CONF_MANUAL_DURATIONS] = durations
            return {}, {}

        return await self._async_form("manual", _manual_schema, user_input, validate)

    async def async_step_equithermal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Heating curve, heating limit and duty limit (FR-EQ)."""
        schema = _equithermal_schema(self._values)
        errors: Errors = {}
        if user_input is not None:
            if user_input[CONF_FLOW_TEMP_MIN] >= user_input[CONF_FLOW_TEMP_MAX]:
                errors[CONF_FLOW_TEMP_MIN] = "flow_range"
            elif user_input[CONF_USE_FORECAST] and not self._values.get(CONF_WEATHER_ENTITY):
                errors[CONF_USE_FORECAST] = "forecast_needs_weather"
            else:
                self._values = _apply(self._values, schema, user_input)
                # FR-EQ-05: a curve above the fixed boiler temperature disables the limit.
                if (
                    self._values[CONF_EQUITHERMAL_DUTY_ENABLED]
                    and self._values[CONF_DESIGN_FLOW_TEMP]
                    > self._values[CONF_BOILER_FIXED_FLOW_TEMP]
                ):
                    return await self.async_step_equithermal_confirm()
                return self._save()
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="equithermal", data_schema=schema, errors=errors)

    async def async_step_equithermal_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Warn that the duty limit has little effect with this curve."""
        if user_input is not None:
            return self._save()
        return self.async_show_form(
            step_id="equithermal_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "design_flow_temp": str(self._values[CONF_DESIGN_FLOW_TEMP]),
                "boiler_fixed_flow_temp": str(self._values[CONF_BOILER_FIXED_FLOW_TEMP]),
            },
        )

    async def async_step_frost(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """System frost protection (FR-FROST-02)."""
        return await self._async_form("frost", _frost_schema, user_input)

    async def async_step_presence(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Presence of the household and preheating (FR-SCH-02, FR-SCH-03)."""
        return await self._async_form("presence", _presence_schema, user_input)


# --- Room subentry flow --------------------------------------------------


class RoomSubentryFlowHandler(ConfigSubentryFlow):
    """Add or reconfigure a room: basics, sensors, valves, windows, schedule, control."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}
        self._valve_queue: list[str] = []
        self._previous_valves: dict[str, dict[str, Any]] = {}
        self._valves: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a new room."""
        self._data = dict(DEFAULT_ROOM)
        return await self.async_step_basics()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing room."""
        self._data = {**DEFAULT_ROOM, **self._get_reconfigure_subentry().data}
        return await self.async_step_basics()

    def _other_rooms(self) -> list[ConfigSubentry]:
        rooms = _room_subentries(self._get_entry())
        if self.source == SOURCE_USER:
            return rooms
        current_id = self._get_reconfigure_subentry().subentry_id
        return [room for room in rooms if room.subentry_id != current_id]

    async def _async_room_form(
        self,
        step_id: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
        errors: Errors,
        placeholders: Placeholders | None = None,
    ) -> SubentryFlowResult:
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_basics(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Name, target temperatures, area and weight."""
        schema = _room_basics_schema(self._data)
        errors: Errors = {}
        if user_input is not None:
            name = user_input[CONF_ROOM_NAME].strip()
            if not name or not slugify(name):
                errors[CONF_ROOM_NAME] = "name_invalid"
            elif any(room.unique_id == slugify(name) for room in self._other_rooms()):
                errors[CONF_ROOM_NAME] = "name_exists"
            elif user_input[CONF_ECO_TEMP] > user_input[CONF_COMFORT_TEMP]:
                errors[CONF_ECO_TEMP] = "eco_above_comfort"
            elif user_input[CONF_FROST_TEMP] >= min(
                user_input[CONF_ECO_TEMP], user_input[CONF_AWAY_TEMP]
            ):
                errors[CONF_FROST_TEMP] = "frost_too_high"
            if not errors:
                self._data = _apply(self._data, schema, {**user_input, CONF_ROOM_NAME: name})
                return await self.async_step_sensors()
        return await self._async_room_form("basics", schema, user_input, errors)

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Temperature sensors and their validation (FR-ROOM-02 to 05)."""
        schema = _room_sensors_schema(self._data)
        errors: Errors = {}
        if user_input is not None:
            if not user_input[CONF_SENSORS]:
                errors[CONF_SENSORS] = "sensors_required"
            elif _non_temperature_entities(self.hass, user_input[CONF_SENSORS]):
                errors[CONF_SENSORS] = "not_temperature_sensor"
            elif user_input[CONF_SENSOR_MIN] >= user_input[CONF_SENSOR_MAX]:
                errors[CONF_SENSOR_MIN] = "sensor_range"
            if not errors:
                self._data = _apply(self._data, schema, user_input)
                return await self.async_step_valves()
        return await self._async_room_form("sensors", schema, user_input, errors)

    async def async_step_valves(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the valve entities (FR-VAL-01)."""
        schema = _room_valves_schema(self._data)
        errors: Errors = {}
        if user_input is not None:
            if not user_input[CONF_VALVES]:
                errors[CONF_VALVES] = "valves_required"
            else:
                self._previous_valves = {
                    valve[CONF_VALVE_ENTITY]: valve for valve in self._data.get(CONF_VALVES, [])
                }
                self._valve_queue = list(user_input[CONF_VALVES])
                self._valves = []
                return await self.async_step_valve()
        return await self._async_room_form("valves", schema, user_input, errors)

    async def async_step_valve(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure one valve: NO/NC and travel times (FR-VAL-02, FR-VAL-03)."""
        entity_id = self._valve_queue[0]
        current = {**DEFAULT_VALVE, **self._previous_valves.get(entity_id, {})}
        schema = _valve_schema(entity_id, current)
        if user_input is not None:
            valve = _apply(current, schema, user_input)
            valve[CONF_VALVE_ENTITY] = entity_id
            if entity_id.startswith("valve."):
                valve.pop(CONF_NORMALLY_OPEN, None)
            self._valves.append(valve)
            self._valve_queue.pop(0)
            if self._valve_queue:
                return await self.async_step_valve()
            self._data[CONF_VALVES] = self._valves
            return await self.async_step_windows()
        state = self.hass.states.get(entity_id)
        return self.async_show_form(
            step_id="valve",
            data_schema=schema,
            description_placeholders={"valve": state.name if state else entity_id},
        )

    async def async_step_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Window contacts, optional (FR-WIN-01), and airing detection (FR-WIN-06)."""
        schema = _room_windows_schema(self._data)
        errors: Errors = {}
        if user_input is not None:
            if user_input[CONF_VENT_MAX] < user_input[CONF_VENT_PAUSE]:
                errors[CONF_VENT_MAX] = "vent_max_below_pause"
            else:
                self._data = _apply(self._data, schema, user_input)
                return await self.async_step_schedule()
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="windows", data_schema=schema, errors=errors)

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Schedule (house or own), presence and expected return (FR-SCH-01, FR-SCH-02)."""
        schema = _room_schedule_schema(self._data)
        errors: Errors = {}
        if user_input is not None:
            if user_input[CONF_SCHEDULE_MODE] == "own" and not user_input.get(CONF_SCHEDULE_ENTITY):
                errors[CONF_SCHEDULE_ENTITY] = "schedule_required"
            else:
                if user_input[CONF_SCHEDULE_MODE] == "house":
                    user_input.pop(CONF_SCHEDULE_ENTITY, None)
                self._data = _apply(self._data, schema, user_input)
                return await self.async_step_control()
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="schedule", data_schema=schema, errors=errors)

    async def async_step_control(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Control algorithm and valve PWM (FR-VAL-05, chapter 11.1)."""
        schema = _room_control_schema(self._data)
        errors: Errors = {}
        placeholders: Placeholders = {}
        if user_input is not None:
            valve_time = _max_valve_time([self._data])
            if user_input[CONF_VALVE_MIN_STATE_TIME] * 60 < valve_time:
                errors[CONF_VALVE_MIN_STATE_TIME] = "min_state_too_short"
                placeholders["valve_time"] = str(valve_time)
            else:
                self._data = _apply(self._data, schema, user_input)
                return self._async_finish()
        return await self._async_room_form("control", schema, user_input, errors, placeholders)

    def _async_finish(self) -> SubentryFlowResult:
        name = self._data[CONF_ROOM_NAME]
        if self.source == SOURCE_USER:
            return self.async_create_entry(title=name, data=self._data, unique_id=slugify(name))
        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            title=name,
            data=self._data,
            unique_id=slugify(name),
        )
