"""Configuration, inputs and outputs of the control core.

All durations inside the core are in seconds and all times are aware datetimes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from .. import const as c

STATE_UNAVAILABLE = "unavailable"
STATE_UNKNOWN = "unknown"


class SystemMode(StrEnum):
    """Mode selected by the user (FR-MODE-01)."""

    AUTO = "auto"
    MANUAL = "manual"
    OFF = "off"
    AWAY = "away"


class SystemState(StrEnum):
    """Effective state of the system automaton (chapter 11.6)."""

    STARTUP = "startup"
    AUTO = "auto"
    AWAY = "away"
    OFF = "off"
    SUMMER = "summer"
    MANUAL = "manual"
    FAULT_SAFE = "fault_safe"


class RoomHvacMode(StrEnum):
    """HVAC mode of a room (FR-MODE-02)."""

    AUTO = "auto"
    HEAT = "heat"
    OFF = "off"


class Preset(StrEnum):
    """Room preset (FR-MODE-02)."""

    COMFORT = "comfort"
    ECO = "eco"
    AWAY = "away"
    NONE = "none"


class ValvePhysical(StrEnum):
    """Modelled physical state of a valve (FR-VAL-03)."""

    OPENING = "opening"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class WindowState(StrEnum):
    """Window state machine of a room (chapter 11.4)."""

    CLOSED = "closed"
    PENDING_OPEN = "pending_open"
    BLOCKED = "blocked"
    PENDING_CLOSE = "pending_close"


class BoilerPhase(StrEnum):
    """Valve to boiler sequence (chapter 11.3)."""

    IDLE = "idle"
    PRE_OPEN = "pre_open"
    FIRING = "firing"
    OVERRUN = "overrun"


class BoilerReason(StrEnum):
    """Why the boiler is in its current state (FR-SAFE-07, `sensor.hh_boiler_reason`)."""

    STARTUP = "startup"
    IDLE = "idle"
    OFF = "off"
    SUMMER = "summer"
    WINDOW_BLOCK = "window_block"
    PRE_OPEN = "pre_open"
    PRE_CLOSE = "pre_close"
    NO_FLOW_HOLD = "no_flow_hold"
    MIN_OFF_HOLD = "min_off_hold"
    MAX_STARTS_HOLD = "max_starts_hold"
    DUTY_HOLD = "duty_hold"
    FIRING_DEMAND = "firing_demand"
    FIRING_MANUAL = "firing_manual"
    FIRING_FROST = "firing_frost"
    MIN_ON_HOLD = "min_on_hold"
    OVERRUN = "overrun"
    FAULT_SAFE = "fault_safe"
    FAULT_RECOVERY = "fault_recovery"


# A time rule keeps the boiler in its state against or regardless of the demand.
HOLD_REASONS = frozenset(
    {
        BoilerReason.PRE_OPEN,
        BoilerReason.PRE_CLOSE,
        BoilerReason.NO_FLOW_HOLD,
        BoilerReason.MIN_OFF_HOLD,
        BoilerReason.MAX_STARTS_HOLD,
        BoilerReason.DUTY_HOLD,
        BoilerReason.MIN_ON_HOLD,
        BoilerReason.FAULT_RECOVERY,
    }
)


class ValveReason(StrEnum):
    """Why a valve is commanded to its position (attributes of the valve state)."""

    STARTUP = "startup"
    FAULT_SAFE = "fault_safe"
    FROST = "frost"
    WINDOW = "window"
    VENTILATION = "ventilation"
    MANUAL = "manual"
    MANUAL_EXCLUDED = "manual_excluded"
    IDLE_POLICY = "idle_policy"
    ROOM_OFF = "room_off"
    PWM = "pwm"
    MIN_STATE_HOLD = "min_state_hold"
    PREHEAT = "preheat"
    EXERCISE = "exercise"
    OVERRUN = "overrun"
    MIN_FLOW = "min_flow"


class TargetReason(StrEnum):
    """Why a room has its current target (attribute `target_reason`)."""

    FROST = "frost"
    WINDOW = "window"
    VENTILATION = "ventilation"
    MANUAL = "manual"
    ROOM_OFF = "room_off"
    SUMMER = "summer"
    SYSTEM_OFF = "system_off"
    SYSTEM_AWAY = "system_away"
    OVERRIDE = "override"
    PREHEAT = "preheat"
    LONG_AWAY = "long_away"
    ABSENT = "absent"
    SCHEDULE_ECO = "schedule_eco"
    SCHEDULE_COMFORT = "schedule_comfort"
    COMFORT = "comfort"


# Reasons that follow presence or the schedule; their changes go to the logbook.
PRESENCE_SCHEDULE_REASONS = frozenset(
    {
        TargetReason.LONG_AWAY,
        TargetReason.ABSENT,
        TargetReason.SCHEDULE_ECO,
        TargetReason.SCHEDULE_COMFORT,
        TargetReason.COMFORT,
    }
)


# --- Configuration --------------------------------------------------------


def _get(data: Mapping[str, Any], defaults: Mapping[str, Any], key: str) -> Any:
    value = data.get(key)
    return defaults.get(key) if value is None else value


@dataclass(frozen=True, slots=True)
class ValveConfig:
    """One valve head (FR-VAL-01 to 03)."""

    entity_id: str
    normally_open: bool
    open_time_s: float
    close_time_s: float
    temp_entity: str | None = None

    @property
    def is_valve_domain(self) -> bool:
        """Return True for `valve.*` entities, which report the physical state."""
        return self.entity_id.startswith("valve.")

    @property
    def travel_time_s(self) -> float:
        """Return the longer of the two travel times."""
        return max(self.open_time_s, self.close_time_s)

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> ValveConfig:
        """Build from a stored valve dict."""
        entity_id = data[c.CONF_VALVE_ENTITY]
        return cls(
            entity_id=entity_id,
            normally_open=True
            if entity_id.startswith("valve.")
            else bool(_get(data, c.DEFAULT_VALVE, c.CONF_NORMALLY_OPEN)),
            open_time_s=float(_get(data, c.DEFAULT_VALVE, c.CONF_VALVE_OPEN_TIME)),
            close_time_s=float(_get(data, c.DEFAULT_VALVE, c.CONF_VALVE_CLOSE_TIME)),
            temp_entity=data.get(c.CONF_VALVE_TEMP_ENTITY),
        )


@dataclass(frozen=True, slots=True)
class RoomConfig:
    """Room configuration (config subentry, chapter 10.2)."""

    room_id: str
    slug: str
    name: str
    comfort_temp: float
    eco_temp: float
    away_temp: float
    frost_temp: float
    area_m2: float
    weight: float
    sensors: tuple[str, ...]
    aggregation: str
    sensor_min: float
    sensor_max: float
    stale_timeout_s: float
    sensor_fallback: str
    fallback_hold_s: float
    fallback_demand: float
    valves: tuple[ValveConfig, ...]
    windows: tuple[str, ...]
    window_invert: bool
    vent_detect: bool
    vent_drop_k: float
    vent_window_s: float
    vent_hold_s: float
    vent_max_s: float
    schedule_entity: str | None
    presence_entity: str | None
    expected_return_entity: str | None
    algorithm: str
    cold_tolerance: float
    hot_tolerance: float
    tpi_coef_int: float
    tpi_coef_ext: float
    pwm_period_s: float
    min_state_s: float

    @classmethod
    def from_data(cls, room_id: str, slug: str, data: Mapping[str, Any]) -> RoomConfig:
        """Build from subentry data."""
        d = c.DEFAULT_ROOM

        def num(key: str) -> float:
            return float(_get(data, d, key))

        return cls(
            room_id=room_id,
            slug=slug,
            name=str(data.get(c.CONF_ROOM_NAME, slug)),
            comfort_temp=num(c.CONF_COMFORT_TEMP),
            eco_temp=num(c.CONF_ECO_TEMP),
            away_temp=num(c.CONF_AWAY_TEMP),
            frost_temp=num(c.CONF_FROST_TEMP),
            area_m2=num(c.CONF_AREA_M2),
            weight=num(c.CONF_WEIGHT),
            sensors=tuple(data.get(c.CONF_SENSORS, ())),
            aggregation=str(_get(data, d, c.CONF_AGGREGATION)),
            sensor_min=num(c.CONF_SENSOR_MIN),
            sensor_max=num(c.CONF_SENSOR_MAX),
            stale_timeout_s=num(c.CONF_SENSOR_STALE_TIMEOUT) * 60,
            sensor_fallback=str(_get(data, d, c.CONF_SENSOR_FALLBACK)),
            fallback_hold_s=num(c.CONF_FALLBACK_HOLD) * 60,
            fallback_demand=num(c.CONF_FALLBACK_DEMAND),
            valves=tuple(ValveConfig.from_data(v) for v in data.get(c.CONF_VALVES, ())),
            windows=tuple(data.get(c.CONF_WINDOWS, ())),
            window_invert=bool(_get(data, d, c.CONF_WINDOW_INVERT)),
            vent_detect=bool(_get(data, d, c.CONF_VENT_DETECT)),
            vent_drop_k=num(c.CONF_VENT_DROP),
            vent_window_s=num(c.CONF_VENT_TIME) * 60,
            vent_hold_s=num(c.CONF_VENT_PAUSE) * 60,
            vent_max_s=num(c.CONF_VENT_MAX) * 60,
            # An own schedule only when chosen; before 0.9 a filled entity meant own.
            schedule_entity=data.get(c.CONF_SCHEDULE_ENTITY)
            if data.get(c.CONF_SCHEDULE_MODE, "own") == "own"
            else None,
            presence_entity=data.get(c.CONF_PRESENCE_ENTITY),
            expected_return_entity=data.get(c.CONF_EXPECTED_RETURN_ENTITY),
            algorithm=str(_get(data, d, c.CONF_CONTROL_ALGORITHM)),
            cold_tolerance=num(c.CONF_COLD_TOLERANCE),
            hot_tolerance=num(c.CONF_HOT_TOLERANCE),
            tpi_coef_int=num(c.CONF_TPI_COEF_INT),
            tpi_coef_ext=num(c.CONF_TPI_COEF_EXT),
            pwm_period_s=num(c.CONF_VALVE_PWM_PERIOD) * 60,
            min_state_s=num(c.CONF_VALVE_MIN_STATE_TIME) * 60,
        )

    def temp_for(self, preset: Preset) -> float:
        """Return the target temperature of a preset."""
        if preset is Preset.ECO:
            return self.eco_temp
        if preset is Preset.AWAY:
            return self.away_temp
        return self.comfort_temp


@dataclass(frozen=True, slots=True)
class HeatSourceConfig:
    """How the boiler is switched (FR-BOI-01)."""

    type: str
    entity: str | None = None
    on_entity: str | None = None
    off_entity: str | None = None
    select_entity: str | None = None
    select_on: str | None = None
    select_off: str | None = None
    feedback_entity: str | None = None
    flow_temp_entity: str | None = None

    @property
    def state_entity(self) -> str | None:
        """Return the entity whose state tells whether the boiler is enabled."""
        if self.type == c.HEAT_SOURCE_SWITCH:
            return self.entity
        if self.type == c.HEAT_SOURCE_SELECT:
            return self.select_entity
        return None

    @property
    def entities(self) -> tuple[str, ...]:
        """Return all entities used to control the boiler."""
        found = [self.entity, self.on_entity, self.off_entity, self.select_entity]
        return tuple(e for e in found if e)

    @property
    def verifiable(self) -> bool:
        """Return True when the command can be verified by a state."""
        return self.state_entity is not None


@dataclass(frozen=True, slots=True)
class SystemConfig:
    """System options (chapter 10.2), converted to seconds."""

    shadow_mode: bool
    heat_source: HeatSourceConfig
    outdoor_sensors: tuple[str, ...]
    weather_entity: str | None
    boiler_min_on_s: float
    boiler_min_off_s: float
    boiler_max_starts: int
    boiler_overrun_s: float
    demand_threshold: float
    demand_hysteresis: float
    room_call_threshold: float
    min_rooms_calling: int
    combine: str
    area_weighting: bool
    min_open_valves: int
    has_bypass: bool
    keep_alive_s: float
    verify_timeout_s: float
    command_retries: int
    startup_grace_s: float
    fault_recovery_s: float
    heartbeat_entity: str | None
    heartbeat_interval_s: float
    notify_service: str | None
    idle_valve_policy: str
    exercise_interval_days: float
    exercise_duration_s: float
    exercise_time: time
    exercise_parallel: int
    window_open_delay_s: float
    window_close_delay_s: float
    window_outdoor_condition: bool
    window_max_block_s: float
    global_window_mode: str
    global_window_count: int
    global_window_ratio: float
    global_window_delay_s: float
    manual_durations: tuple[int, ...]
    manual_restart_policy: str
    manual_scope: str
    stop_policy: str
    stop_respects_min_on: bool
    mirror_timer_entity: str | None
    heating_limit: float
    outdoor_damping_s: float
    frost_outdoor_protection: bool
    frost_outdoor_temp: float
    frost_idle_max_s: float
    design_outdoor_temp: float = -12.0
    design_flow_temp: float = 65.0
    reference_room_temp: float = 20.0
    radiator_exponent: float = 1.3
    curve_offset: float = 0.0
    flow_temp_min: float = 30.0
    flow_temp_max: float = 75.0
    duty_enabled: bool = False
    boiler_fixed_flow_temp: float = 70.0
    boiler_cycle_period_s: float = 1200.0
    duty_min: float = 0.2
    use_forecast: bool = False
    flow_check_s: float = 15 * 60
    flow_check_rise: float = 5.0
    valve_check_s: float = 10 * 60
    valve_check_rise: float = 5.0
    valve_check_closed_rise: float = 3.0
    valve_check_hot: float = 40.0
    house_schedule_entity: str | None = None
    house_presence_entity: str | None = None
    long_away_entity: str | None = None
    expected_return_entity: str | None = None
    absence_preset: str = "eco"
    preheat_enabled: bool = True
    preheat_max_s: float = 4 * 3600
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))

    @classmethod
    def from_options(cls, options: Mapping[str, Any], timezone: ZoneInfo) -> SystemConfig:
        """Build from config entry options."""
        d = c.DEFAULT_OPTIONS

        def num(key: str) -> float:
            return float(_get(options, d, key))

        def opt(key: str) -> Any:
            return _get(options, d, key)

        hours, minutes, *_ = (int(p) for p in str(opt(c.CONF_EXERCISE_TIME)).split(":"))
        return cls(
            shadow_mode=bool(opt(c.CONF_SHADOW_MODE)),
            heat_source=HeatSourceConfig(
                type=str(opt(c.CONF_HEAT_SOURCE_TYPE)),
                entity=options.get(c.CONF_HEAT_SOURCE_ENTITY),
                on_entity=options.get(c.CONF_HEAT_SOURCE_ON_ENTITY),
                off_entity=options.get(c.CONF_HEAT_SOURCE_OFF_ENTITY),
                select_entity=options.get(c.CONF_HEAT_SOURCE_SELECT_ENTITY),
                select_on=options.get(c.CONF_HEAT_SOURCE_SELECT_ON),
                select_off=options.get(c.CONF_HEAT_SOURCE_SELECT_OFF),
                feedback_entity=options.get(c.CONF_FEEDBACK_ENTITY),
                flow_temp_entity=options.get(c.CONF_FLOW_TEMP_ENTITY),
            ),
            outdoor_sensors=tuple(opt(c.CONF_OUTDOOR_SENSORS) or ()),
            weather_entity=options.get(c.CONF_WEATHER_ENTITY),
            boiler_min_on_s=num(c.CONF_BOILER_MIN_ON) * 60,
            boiler_min_off_s=num(c.CONF_BOILER_MIN_OFF) * 60,
            boiler_max_starts=int(num(c.CONF_BOILER_MAX_STARTS)),
            boiler_overrun_s=num(c.CONF_BOILER_OVERRUN),
            demand_threshold=num(c.CONF_BOILER_DEMAND_THRESHOLD),
            demand_hysteresis=num(c.CONF_BOILER_DEMAND_HYSTERESIS),
            room_call_threshold=num(c.CONF_ROOM_CALL_THRESHOLD),
            min_rooms_calling=int(num(c.CONF_MIN_ROOMS_CALLING)),
            combine=str(opt(c.CONF_COMBINE)),
            area_weighting=bool(opt(c.CONF_AREA_WEIGHTING)),
            min_open_valves=int(num(c.CONF_MIN_OPEN_VALVES)),
            has_bypass=bool(opt(c.CONF_HAS_BYPASS)),
            keep_alive_s=num(c.CONF_KEEP_ALIVE),
            verify_timeout_s=num(c.CONF_COMMAND_VERIFY_TIMEOUT),
            command_retries=int(num(c.CONF_COMMAND_RETRIES)),
            startup_grace_s=num(c.CONF_STARTUP_GRACE),
            fault_recovery_s=num(c.CONF_FAULT_RECOVERY_TIME),
            heartbeat_entity=options.get(c.CONF_HEARTBEAT_ENTITY),
            heartbeat_interval_s=num(c.CONF_HEARTBEAT_INTERVAL),
            notify_service=options.get(c.CONF_NOTIFY_SERVICE),
            idle_valve_policy=str(opt(c.CONF_IDLE_VALVE_POLICY)),
            exercise_interval_days=num(c.CONF_EXERCISE_INTERVAL_DAYS),
            exercise_duration_s=num(c.CONF_EXERCISE_DURATION),
            exercise_time=time(hours, minutes),
            exercise_parallel=int(num(c.CONF_EXERCISE_PARALLEL)),
            window_open_delay_s=num(c.CONF_WINDOW_OPEN_DELAY),
            window_close_delay_s=num(c.CONF_WINDOW_CLOSE_DELAY),
            window_outdoor_condition=bool(opt(c.CONF_WINDOW_OUTDOOR_CONDITION)),
            window_max_block_s=num(c.CONF_WINDOW_MAX_BLOCK) * 60,
            global_window_mode=str(opt(c.CONF_GLOBAL_WINDOW_MODE)),
            global_window_count=int(num(c.CONF_GLOBAL_WINDOW_COUNT)),
            global_window_ratio=num(c.CONF_GLOBAL_WINDOW_RATIO),
            global_window_delay_s=num(c.CONF_GLOBAL_WINDOW_DELAY),
            manual_durations=tuple(int(m) for m in opt(c.CONF_MANUAL_DURATIONS)),
            manual_restart_policy=str(opt(c.CONF_MANUAL_RESTART_POLICY)),
            manual_scope=str(opt(c.CONF_MANUAL_SCOPE)),
            stop_policy=str(opt(c.CONF_STOP_POLICY)),
            stop_respects_min_on=bool(opt(c.CONF_STOP_RESPECTS_MIN_ON)),
            mirror_timer_entity=options.get(c.CONF_MIRROR_TIMER_ENTITY),
            heating_limit=num(c.CONF_HEATING_LIMIT),
            outdoor_damping_s=num(c.CONF_OUTDOOR_DAMPING_HOURS) * 3600,
            frost_outdoor_protection=bool(opt(c.CONF_FROST_OUTDOOR_PROTECTION)),
            frost_outdoor_temp=num(c.CONF_FROST_OUTDOOR_TEMP),
            frost_idle_max_s=num(c.CONF_FROST_IDLE_MAX) * 3600,
            design_outdoor_temp=num(c.CONF_DESIGN_OUTDOOR_TEMP),
            design_flow_temp=num(c.CONF_DESIGN_FLOW_TEMP),
            reference_room_temp=num(c.CONF_REFERENCE_ROOM_TEMP),
            radiator_exponent=num(c.CONF_RADIATOR_EXPONENT),
            curve_offset=num(c.CONF_CURVE_OFFSET),
            flow_temp_min=num(c.CONF_FLOW_TEMP_MIN),
            flow_temp_max=num(c.CONF_FLOW_TEMP_MAX),
            duty_enabled=bool(opt(c.CONF_EQUITHERMAL_DUTY_ENABLED)),
            boiler_fixed_flow_temp=num(c.CONF_BOILER_FIXED_FLOW_TEMP),
            boiler_cycle_period_s=num(c.CONF_BOILER_CYCLE_PERIOD) * 60,
            duty_min=num(c.CONF_DUTY_MIN),
            use_forecast=bool(opt(c.CONF_USE_FORECAST)),
            flow_check_s=num(c.CONF_FLOW_CHECK_TIME) * 60,
            flow_check_rise=num(c.CONF_FLOW_CHECK_RISE),
            valve_check_s=num(c.CONF_VALVE_CHECK_TIME) * 60,
            valve_check_rise=num(c.CONF_VALVE_CHECK_RISE),
            valve_check_closed_rise=num(c.CONF_VALVE_CHECK_CLOSED_RISE),
            valve_check_hot=num(c.CONF_VALVE_CHECK_HOT),
            house_schedule_entity=options.get(c.CONF_HOUSE_SCHEDULE_ENTITY),
            house_presence_entity=options.get(c.CONF_HOUSE_PRESENCE_ENTITY),
            long_away_entity=options.get(c.CONF_LONG_AWAY_ENTITY),
            expected_return_entity=options.get(c.CONF_EXPECTED_RETURN_ENTITY),
            absence_preset=str(opt(c.CONF_ABSENCE_PRESET)),
            preheat_enabled=bool(opt(c.CONF_PREHEAT_ENABLED)),
            preheat_max_s=num(c.CONF_PREHEAT_MAX) * 3600,
            timezone=timezone,
        )


# --- Inputs ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntityReading:
    """State of one Home Assistant entity, as seen by the core."""

    state: str | None
    value: float | None = None
    last_reported: datetime | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        """Return False for missing, unavailable or unknown entities."""
        return self.state not in (None, STATE_UNAVAILABLE, STATE_UNKNOWN)


MISSING = EntityReading(state=None)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Inputs of one control step."""

    now: datetime
    entities: Mapping[str, EntityReading]
    forecast_24h: float | None = None

    def get(self, entity_id: str | None) -> EntityReading:
        """Return the reading of an entity, MISSING when unknown."""
        if entity_id is None:
            return MISSING
        return self.entities.get(entity_id, MISSING)


# --- Outputs --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Command:
    """A service call the runtime should make.

    Actions: `turn_on`, `turn_off`, `open`, `close`, `select` (with `option`),
    `run` (script/button) and `toggle`.
    """

    entity_id: str
    action: str
    option: str | None = None


@dataclass(slots=True)
class Plan:
    """Result of one control step."""

    commands: list[Command] = field(default_factory=list)
    boiler_on: bool = False
    valves_open: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BoilerStatus:
    """Reason of the boiler state and the end of the time rule behind it.

    `rule` names the setting in the options (technical, not translated) and
    `params` holds the values the explanation text needs.
    """

    reason: BoilerReason
    until: datetime | None = None
    rule: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValveStatus:
    """Reason of one valve position and when it is expected to change."""

    reason: ValveReason
    until: datetime | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    """A boiler decision or a reverted output, written to the logbook.

    Kinds: `boiler_on`, `boiler_off`, `hold` (a time rule delays the command)
    and `reverted` (an output switched outside the controller was set back).
    """

    kind: str
    status: BoilerStatus
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Problem:
    """An active problem, reported as notification and repair issue (FR-SAFE-04)."""

    key: str
    kind: str
    placeholders: Mapping[str, str] = field(default_factory=dict)
    repair: bool = False
