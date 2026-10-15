"""Constants for the Heating Controller integration.

Keys and defaults follow the PRD, chapter 10.2. This module has no Home Assistant
imports, so the pure core can share the keys (NFR-08).
"""

from __future__ import annotations

from typing import Any, Final

DOMAIN: Final = "hydronic_heating"
DEFAULT_NAME: Final = "Topení"

SUBENTRY_ROOM: Final = "room"

STORAGE_VERSION: Final = 1
UPDATE_INTERVAL_S: Final = 30
ENTITY_PREFIX: Final = "hh"

SERVICE_START_MANUAL: Final = "start_manual"
SERVICE_STOP: Final = "stop"
SERVICE_GENERATE_DASHBOARD: Final = "generate_dashboard"
ATTR_DURATION: Final = "duration"
SERVICE_VENTILATE: Final = "ventilate"
SERVICE_STOP_VENTILATION: Final = "stop_ventilation"
ATTR_MINUTES: Final = "minutes"

# Logbook event with every boiler decision and reverted output.
EVENT_DECISION: Final = "hydronic_heating_decision"

# --- General -------------------------------------------------------------
CONF_SHADOW_MODE: Final = "shadow_mode"
CONF_DEMO_MODE: Final = "demo_mode"
DEMO_OFF: Final = "off"
DEMO_VIRTUAL_OUTPUTS: Final = "virtual_outputs"
DEMO_VIRTUAL_HOUSE: Final = "virtual_house"
DEMO_MODES: Final = [DEMO_OFF, DEMO_VIRTUAL_OUTPUTS, DEMO_VIRTUAL_HOUSE]

# --- Heat source (FR-BOI-01) ---------------------------------------------
CONF_HEAT_SOURCE_TYPE: Final = "heat_source_type"
HEAT_SOURCE_SWITCH: Final = "switch"
HEAT_SOURCE_ACTIONS: Final = "actions"
HEAT_SOURCE_SELECT: Final = "select"
HEAT_SOURCE_TYPES: Final = [HEAT_SOURCE_SWITCH, HEAT_SOURCE_ACTIONS, HEAT_SOURCE_SELECT]

CONF_HEAT_SOURCE_ENTITY: Final = "heat_source_entity"
CONF_HEAT_SOURCE_ON_ENTITY: Final = "heat_source_on_entity"
CONF_HEAT_SOURCE_OFF_ENTITY: Final = "heat_source_off_entity"
CONF_HEAT_SOURCE_SELECT_ENTITY: Final = "heat_source_select_entity"
CONF_HEAT_SOURCE_SELECT_ON: Final = "heat_source_select_on"
CONF_HEAT_SOURCE_SELECT_OFF: Final = "heat_source_select_off"
CONF_FEEDBACK_ENTITY: Final = "feedback_entity"
# Measured flow temperature, e.g. on the riser from the boiler (FR-SAFE-08).
CONF_FLOW_TEMP_ENTITY: Final = "flow_temp_entity"

# Keys owned by each heat source type, used to drop stale keys on type change.
HEAT_SOURCE_KEYS: Final = {
    HEAT_SOURCE_SWITCH: [CONF_HEAT_SOURCE_ENTITY],
    HEAT_SOURCE_ACTIONS: [CONF_HEAT_SOURCE_ON_ENTITY, CONF_HEAT_SOURCE_OFF_ENTITY],
    HEAT_SOURCE_SELECT: [
        CONF_HEAT_SOURCE_SELECT_ENTITY,
        CONF_HEAT_SOURCE_SELECT_ON,
        CONF_HEAT_SOURCE_SELECT_OFF,
    ],
}

# --- Outdoor temperature (FR-EQ-01) --------------------------------------
CONF_OUTDOOR_SENSORS: Final = "outdoor_sensors"
CONF_WEATHER_ENTITY: Final = "weather_entity"

# --- Boiler and arbitration (FR-BOI, FR-ARB) -----------------------------
CONF_BOILER_MIN_ON: Final = "boiler_min_on"
CONF_BOILER_MIN_OFF: Final = "boiler_min_off"
CONF_BOILER_MAX_STARTS: Final = "boiler_max_starts_per_hour"
CONF_BOILER_OVERRUN: Final = "boiler_overrun"
CONF_BOILER_DEMAND_THRESHOLD: Final = "boiler_demand_threshold"
CONF_BOILER_DEMAND_HYSTERESIS: Final = "boiler_demand_hysteresis"
CONF_ROOM_CALL_THRESHOLD: Final = "room_call_threshold"
CONF_MIN_ROOMS_CALLING: Final = "min_rooms_calling"
CONF_COMBINE: Final = "combine"
CONF_AREA_WEIGHTING: Final = "area_weighting"
CONF_MIN_OPEN_VALVES: Final = "min_open_valves"
CONF_HAS_BYPASS: Final = "has_bypass"
COMBINE_OPTIONS: Final = ["any", "all"]

# --- Safety (FR-SAFE) ----------------------------------------------------
CONF_KEEP_ALIVE: Final = "keep_alive"
CONF_COMMAND_VERIFY_TIMEOUT: Final = "command_verify_timeout"
CONF_COMMAND_RETRIES: Final = "command_retries"
CONF_STARTUP_GRACE: Final = "startup_grace"
CONF_FAULT_RECOVERY_TIME: Final = "fault_recovery_time"
CONF_HEARTBEAT_ENTITY: Final = "heartbeat_entity"
CONF_HEARTBEAT_INTERVAL: Final = "heartbeat_interval"
CONF_NOTIFY_SERVICE: Final = "notify_service"
CONF_FLOW_CHECK_TIME: Final = "flow_check_time"
CONF_FLOW_CHECK_RISE: Final = "flow_check_rise"

# --- Valves, system level (FR-VAL-06, FR-VAL-07) -------------------------
CONF_IDLE_VALVE_POLICY: Final = "idle_valve_policy"
CONF_VALVE_CHECK_TIME: Final = "valve_check_time"
CONF_VALVE_CHECK_RISE: Final = "valve_check_rise"
CONF_VALVE_CHECK_CLOSED_RISE: Final = "valve_check_closed_rise"
CONF_VALVE_CHECK_HOT: Final = "valve_check_hot"
CONF_EXERCISE_INTERVAL_DAYS: Final = "exercise_interval_days"
CONF_EXERCISE_DURATION: Final = "exercise_duration"
CONF_EXERCISE_TIME: Final = "exercise_time"
CONF_EXERCISE_PARALLEL: Final = "exercise_parallel"
IDLE_VALVE_POLICIES: Final = ["deenergize", "open", "closed"]

# --- Windows (FR-WIN) ----------------------------------------------------
CONF_WINDOW_OPEN_DELAY: Final = "window_open_delay"
CONF_WINDOW_CLOSE_DELAY: Final = "window_close_delay"
CONF_WINDOW_OUTDOOR_CONDITION: Final = "window_outdoor_condition"
CONF_WINDOW_MAX_BLOCK: Final = "window_max_block"
CONF_GLOBAL_WINDOW_MODE: Final = "global_window_mode"
CONF_GLOBAL_WINDOW_COUNT: Final = "global_window_count"
CONF_GLOBAL_WINDOW_RATIO: Final = "global_window_ratio"
CONF_GLOBAL_WINDOW_DELAY: Final = "global_window_delay"
# Manual airing (FR-WIN-07): duration, what the room switch airs, the floor follows.
CONF_VENT_MANUAL: Final = "vent_manual"
CONF_VENT_SCOPE: Final = "vent_scope"
VENT_SCOPES: Final = ["floor", "room"]
CONF_VENT_FLOOR_AUTO: Final = "vent_floor_auto"
GLOBAL_WINDOW_MODES: Final = ["count", "ratio", "any"]

# --- Manual mode (FR-MAN) ------------------------------------------------
CONF_MANUAL_DURATIONS: Final = "manual_durations"
CONF_MANUAL_RESTART_POLICY: Final = "manual_restart_policy"
CONF_MANUAL_SCOPE: Final = "manual_scope"
CONF_STOP_POLICY: Final = "stop_policy"
CONF_STOP_RESPECTS_MIN_ON: Final = "stop_respects_min_on"
CONF_MIRROR_TIMER_ENTITY: Final = "mirror_timer_entity"
MANUAL_RESTART_POLICIES: Final = ["replace", "extend"]
MANUAL_SCOPES: Final = ["all_rooms", "calling_rooms"]
STOP_POLICIES: Final = ["resume", "off"]
MANUAL_DURATION_MIN: Final = 1
MANUAL_DURATION_MAX: Final = 720
MANUAL_DURATIONS_MAX_COUNT: Final = 6

# --- Equithermal engine (FR-EQ) ------------------------------------------
CONF_DESIGN_OUTDOOR_TEMP: Final = "design_outdoor_temp"
CONF_DESIGN_FLOW_TEMP: Final = "design_flow_temp"
CONF_REFERENCE_ROOM_TEMP: Final = "reference_room_temp"
CONF_RADIATOR_EXPONENT: Final = "radiator_exponent"
CONF_CURVE_OFFSET: Final = "curve_offset"
CONF_FLOW_TEMP_MIN: Final = "flow_temp_min"
CONF_FLOW_TEMP_MAX: Final = "flow_temp_max"
CONF_HEATING_LIMIT: Final = "heating_limit"
CONF_OUTDOOR_DAMPING_HOURS: Final = "outdoor_damping_hours"
CONF_EQUITHERMAL_DUTY_ENABLED: Final = "equithermal_duty_enabled"
CONF_BOILER_FIXED_FLOW_TEMP: Final = "boiler_fixed_flow_temp"
CONF_BOILER_CYCLE_PERIOD: Final = "boiler_cycle_period"
CONF_DUTY_MIN: Final = "duty_min"
CONF_USE_FORECAST: Final = "use_forecast"

# --- Frost, system level (FR-FROST-02) -----------------------------------
CONF_FROST_OUTDOOR_PROTECTION: Final = "frost_outdoor_protection"
CONF_FROST_OUTDOOR_TEMP: Final = "frost_outdoor_temp"
CONF_FROST_IDLE_MAX: Final = "frost_idle_max"

# --- Presence and preheating (FR-SCH-02, FR-SCH-03) ------------------------
CONF_HOUSE_SCHEDULE_ENTITY: Final = "house_schedule_entity"
CONF_HOUSE_PRESENCE_ENTITY: Final = "house_presence_entity"
CONF_LONG_AWAY_ENTITY: Final = "long_away_entity"
CONF_EXPECTED_RETURN_ENTITY: Final = "expected_return_entity"
CONF_ABSENCE_PRESET: Final = "absence_preset"
CONF_PREHEAT_ENABLED: Final = "preheat_enabled"
CONF_PREHEAT_MAX: Final = "preheat_max"
ABSENCE_PRESETS: Final = ["eco", "away"]

# --- Room subentry (FR-ROOM, FR-SCH, FR-WIN, chapter 10.2) ---------------
CONF_ROOM_NAME: Final = "name"
# Order of the room on the dashboard and in the scheme; 0 = by name after the others.
CONF_ROOM_ORDER: Final = "order"
CONF_COMFORT_TEMP: Final = "comfort_temp"
CONF_ECO_TEMP: Final = "eco_temp"
CONF_AWAY_TEMP: Final = "away_temp"
CONF_FROST_TEMP: Final = "frost_temp"
CONF_AREA_M2: Final = "area_m2"
CONF_WEIGHT: Final = "weight"

CONF_SENSORS: Final = "sensors"
CONF_AGGREGATION: Final = "aggregation"
CONF_SENSOR_MIN: Final = "sensor_min"
CONF_SENSOR_MAX: Final = "sensor_max"
CONF_SENSOR_STALE_TIMEOUT: Final = "sensor_stale_timeout"
# A sensor that drops out keeps its last value this long (FR-ROOM-07).
CONF_SENSOR_GRACE: Final = "sensor_grace"
CONF_SENSOR_FALLBACK: Final = "sensor_fallback"
CONF_FALLBACK_HOLD: Final = "fallback_hold"
CONF_FALLBACK_DEMAND: Final = "fallback_demand"
AGGREGATIONS: Final = ["mean", "min", "max", "median", "priority"]
SENSOR_FALLBACKS: Final = ["last_known", "fixed_demand", "valve_open"]

CONF_VALVES: Final = "valves"
CONF_VALVE_ENTITY: Final = "entity_id"
CONF_NORMALLY_OPEN: Final = "normally_open"
CONF_VALVE_OPEN_TIME: Final = "valve_open_time"
CONF_VALVE_CLOSE_TIME: Final = "valve_close_time"
# Temperature of the pipe at the valve (FR-SAFE-09).
CONF_VALVE_TEMP_ENTITY: Final = "valve_temp_entity"

CONF_WINDOWS: Final = "windows"
CONF_WINDOW_INVERT: Final = "window_invert"
# Airing detected by a fast temperature drop (FR-WIN-06).
CONF_VENT_DETECT: Final = "vent_detect"
CONF_VENT_DROP: Final = "vent_drop"
CONF_VENT_TIME: Final = "vent_time"
CONF_VENT_PAUSE: Final = "vent_pause"
CONF_VENT_MAX: Final = "vent_max"

CONF_SCHEDULE_ENTITY: Final = "schedule_entity"
# "house" = the house schedule, "own" = the room's own schedule_entity.
CONF_SCHEDULE_MODE: Final = "schedule_mode"
SCHEDULE_MODES: Final = ["house", "own"]
CONF_PRESENCE_ENTITY: Final = "presence_entity"

CONF_CONTROL_ALGORITHM: Final = "control_algorithm"
CONF_COLD_TOLERANCE: Final = "cold_tolerance"
CONF_HOT_TOLERANCE: Final = "hot_tolerance"
CONF_TPI_COEF_INT: Final = "tpi_coef_int"
CONF_TPI_COEF_EXT: Final = "tpi_coef_ext"
CONF_VALVE_PWM_PERIOD: Final = "valve_pwm_period"
CONF_VALVE_MIN_STATE_TIME: Final = "valve_min_state_time"
CONTROL_ALGORITHMS: Final = ["hysteresis", "tpi"]

# --- Defaults ------------------------------------------------------------
DEFAULT_OPTIONS: Final[dict[str, Any]] = {
    CONF_SHADOW_MODE: True,
    CONF_DEMO_MODE: DEMO_OFF,
    CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_SWITCH,
    CONF_OUTDOOR_SENSORS: [],
    # Boiler and arbitration
    CONF_BOILER_MIN_ON: 5,
    CONF_BOILER_MIN_OFF: 5,
    CONF_BOILER_MAX_STARTS: 4,
    CONF_BOILER_OVERRUN: 180,
    CONF_BOILER_DEMAND_THRESHOLD: 30,
    CONF_BOILER_DEMAND_HYSTERESIS: 10,
    CONF_ROOM_CALL_THRESHOLD: 50,
    CONF_MIN_ROOMS_CALLING: 1,
    CONF_COMBINE: "any",
    CONF_AREA_WEIGHTING: False,
    CONF_MIN_OPEN_VALVES: 1,
    CONF_HAS_BYPASS: False,
    # Safety
    CONF_KEEP_ALIVE: 300,
    CONF_COMMAND_VERIFY_TIMEOUT: 10,
    CONF_COMMAND_RETRIES: 2,
    CONF_STARTUP_GRACE: 120,
    CONF_FAULT_RECOVERY_TIME: 300,
    CONF_HEARTBEAT_INTERVAL: 60,
    CONF_FLOW_CHECK_TIME: 15,
    CONF_FLOW_CHECK_RISE: 5,
    # Valves (system)
    CONF_IDLE_VALVE_POLICY: "deenergize",
    CONF_VALVE_CHECK_TIME: 10,
    CONF_VALVE_CHECK_RISE: 5,
    CONF_VALVE_CHECK_CLOSED_RISE: 3,
    CONF_VALVE_CHECK_HOT: 40,
    CONF_EXERCISE_INTERVAL_DAYS: 7,
    CONF_EXERCISE_DURATION: 600,
    CONF_EXERCISE_TIME: "10:00:00",
    CONF_EXERCISE_PARALLEL: 2,
    # Windows
    CONF_WINDOW_OPEN_DELAY: 60,
    CONF_WINDOW_CLOSE_DELAY: 30,
    CONF_WINDOW_OUTDOOR_CONDITION: True,
    CONF_WINDOW_MAX_BLOCK: 60,
    CONF_GLOBAL_WINDOW_MODE: "count",
    CONF_GLOBAL_WINDOW_COUNT: 2,
    CONF_GLOBAL_WINDOW_RATIO: 0.5,
    CONF_GLOBAL_WINDOW_DELAY: 120,
    CONF_VENT_MANUAL: 15,
    CONF_VENT_SCOPE: "floor",
    CONF_VENT_FLOOR_AUTO: True,
    # Manual
    CONF_MANUAL_DURATIONS: [30, 60, 120, 180],
    CONF_MANUAL_RESTART_POLICY: "replace",
    CONF_MANUAL_SCOPE: "all_rooms",
    CONF_STOP_POLICY: "resume",
    CONF_STOP_RESPECTS_MIN_ON: True,
    # Equithermal (defaults for South Moravia, PRD 10.2)
    CONF_DESIGN_OUTDOOR_TEMP: -12,
    CONF_DESIGN_FLOW_TEMP: 65,
    CONF_REFERENCE_ROOM_TEMP: 20,
    CONF_RADIATOR_EXPONENT: 1.3,
    CONF_CURVE_OFFSET: 0,
    CONF_FLOW_TEMP_MIN: 30,
    CONF_FLOW_TEMP_MAX: 75,
    CONF_HEATING_LIMIT: 13,
    CONF_OUTDOOR_DAMPING_HOURS: 24,
    CONF_EQUITHERMAL_DUTY_ENABLED: False,
    CONF_BOILER_FIXED_FLOW_TEMP: 70,
    CONF_BOILER_CYCLE_PERIOD: 20,
    CONF_DUTY_MIN: 0.2,
    CONF_USE_FORECAST: False,
    # Frost (system)
    CONF_FROST_OUTDOOR_PROTECTION: False,
    CONF_FROST_OUTDOOR_TEMP: -10,
    CONF_FROST_IDLE_MAX: 6,
    # Presence and preheating
    CONF_ABSENCE_PRESET: "eco",
    CONF_PREHEAT_ENABLED: True,
    CONF_PREHEAT_MAX: 4,
}

DEFAULT_ROOM: Final[dict[str, Any]] = {
    CONF_ROOM_ORDER: 0,
    CONF_COMFORT_TEMP: 21.0,
    CONF_ECO_TEMP: 19.0,
    CONF_AWAY_TEMP: 15.0,
    CONF_FROST_TEMP: 5.0,
    CONF_AREA_M2: 0,
    CONF_WEIGHT: 1.0,
    CONF_SENSORS: [],
    CONF_AGGREGATION: "mean",
    CONF_SENSOR_MIN: -20,
    CONF_SENSOR_MAX: 50,
    CONF_SENSOR_STALE_TIMEOUT: 120,
    CONF_SENSOR_GRACE: 5,
    CONF_SENSOR_FALLBACK: "last_known",
    CONF_FALLBACK_HOLD: 60,
    CONF_FALLBACK_DEMAND: 30,
    CONF_VALVES: [],
    CONF_WINDOWS: [],
    CONF_WINDOW_INVERT: False,
    CONF_VENT_DETECT: True,
    CONF_VENT_DROP: 1.0,
    CONF_VENT_TIME: 5,
    CONF_VENT_PAUSE: 20,
    CONF_VENT_MAX: 45,
    CONF_CONTROL_ALGORITHM: "tpi",
    CONF_COLD_TOLERANCE: 0.3,
    CONF_HOT_TOLERANCE: 0.2,
    CONF_TPI_COEF_INT: 0.6,
    CONF_TPI_COEF_EXT: 0.01,
    CONF_VALVE_PWM_PERIOD: 30,
    CONF_VALVE_MIN_STATE_TIME: 5,
}

DEFAULT_VALVE: Final[dict[str, Any]] = {
    CONF_NORMALLY_OPEN: True,
    CONF_VALVE_OPEN_TIME: 120,
    CONF_VALVE_CLOSE_TIME: 120,
}

# Valve entity domains (FR-VAL-01). Script pairs follow in F1.
VALVE_DOMAINS: Final = ["switch", "input_boolean", "valve"]
