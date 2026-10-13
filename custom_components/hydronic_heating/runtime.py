"""Runtime: connects the pure core to Home Assistant (PRD chapter 8.2).

Event driven: every state change of an input entity and a 30 s tick run one
control step. Commands are executed as service calls in the background.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_BOILER_FIXED_FLOW_TEMP,
    CONF_DEMO_MODE,
    CONF_MANUAL_DURATIONS,
    CONF_SHADOW_MODE,
    CONF_VALVES,
    DEFAULT_OPTIONS,
    DEMO_OFF,
    DOMAIN,
    EVENT_DECISION,
    STORAGE_VERSION,
    SUBENTRY_ROOM,
    UPDATE_INTERVAL_S,
)
from .core.controller import HydronicController
from .core.model import (
    Command,
    Decision,
    EntityReading,
    Plan,
    Preset,
    Problem,
    RoomConfig,
    RoomHvacMode,
    Snapshot,
    SystemConfig,
    SystemMode,
)
from .demo import DemoLayout, DemoSimulator, build_layout, remap
from .explain import decision_text
from .notifications import notification_text, reason_text

_LOGGER = logging.getLogger(__name__)

SAVE_DELAY_S = 10
# A step right after a time rule ends, so the boiler follows the countdown.
HOLD_STEP_DELAY = timedelta(seconds=1)
FORECAST_INTERVAL = timedelta(minutes=30)
ROOM_PROBLEM_KINDS = ("sensor_failure", "window_long", "not_reached")
FORECAST_HOURS = 24

type HydronicConfigEntry = ConfigEntry[HydronicHeatingRuntime]


def structure_of(entry: ConfigEntry) -> tuple[Any, ...]:
    """Parts of the configuration that define which entities exist."""
    rooms = tuple(
        (sub.subentry_id, sub.title)
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_ROOM
    )
    durations = tuple(
        entry.options.get(CONF_MANUAL_DURATIONS, DEFAULT_OPTIONS[CONF_MANUAL_DURATIONS])
    )
    demo = entry.options.get(CONF_DEMO_MODE, DEMO_OFF)
    # Demo entities exist per valve, so the valve count is part of the structure.
    valves = tuple(
        len(sub.data.get(CONF_VALVES, []))
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_ROOM
    )
    return (entry.title, rooms, durations, demo, valves if demo != DEMO_OFF else ())


def room_configs(entry: ConfigEntry) -> list[RoomConfig]:
    """Room configurations from the config subentries."""
    return [
        RoomConfig.from_data(sub.subentry_id, sub.unique_id or slugify(sub.title), sub.data)
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_ROOM
    ]


FORECAST_ENTRIES = {"hourly": FORECAST_HOURS, "twice_daily": 2, "daily": 1}


def _forecast_mean(forecast: list[dict[str, Any]], forecast_type: str) -> float | None:
    """Mean forecast temperature of the next 24 hours (24 hourly, 2 half-day or 1 day)."""
    since = dt_util.utcnow() - timedelta(hours=1)
    upcoming = [
        item
        for item in forecast
        if (when := dt_util.parse_datetime(str(item.get("datetime", "")))) is None or when >= since
    ][: FORECAST_ENTRIES[forecast_type]]
    values = [
        float(item[key])
        for item in upcoming
        for key in ("temperature", "templow")
        if isinstance(item.get(key), int | float)
    ]
    return round(sum(values) / len(values), 1) if values else None


def _numeric(entity_id: str, state: str, attributes: Mapping[str, Any]) -> float | None:
    if entity_id.startswith("climate."):
        value = attributes.get("current_temperature")
        return float(value) if isinstance(value, int | float) else None
    try:
        return float(state)
    except ValueError:
        return None


def _event_data(decision: Decision) -> dict[str, Any]:
    """Machine readable part of the decision event (for automations)."""
    status = decision.status

    def plain(value: Any) -> Any:
        return value.isoformat() if isinstance(value, datetime) else value

    return {
        "kind": decision.kind,
        "reason": status.reason.value,
        "until": plain(status.until),
        "rule": status.rule,
        **{key: plain(value) for key, value in decision.params.items() if key != "entity_id"},
    }


class HydronicHeatingRuntime:
    """Owns the controller, its subscriptions and the command execution."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Create the controller from the entry."""
        self.hass = hass
        self.entry = entry
        self.structure = structure_of(entry)
        self.rooms = room_configs(entry)
        self.demo_mode = str(entry.options.get(CONF_DEMO_MODE, DEMO_OFF))
        self.layout: DemoLayout | None = None
        self.demo: DemoSimulator | None = None
        if self.demo_mode != DEMO_OFF:
            self.layout = build_layout(hass, entry.entry_id, self.demo_mode, self.rooms)
            water_temp = float(
                entry.options.get(
                    CONF_BOILER_FIXED_FLOW_TEMP, DEFAULT_OPTIONS[CONF_BOILER_FIXED_FLOW_TEMP]
                )
            )
            self.demo = DemoSimulator(hass, self.layout, water_temp)
        self.controller = HydronicController(*self._controller_configs())
        # The demo keeps its own state, so it never mixes with the real boiler history.
        suffix = ".demo" if self.demo else ""
        self.store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}{suffix}"
        )
        self.context = Context()
        self.last_plan = Plan()
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._state_unsub: Callable[[], None] | None = None
        self._watched: list[str] = []
        self._known_problems: dict[str, Problem] = {}
        self._mirror_ends_at: datetime | None = None
        self._stopped = False
        self._trigger: tuple[str, str | None] | None = None
        self._hold_unsub: Callable[[], None] | None = None
        self._hold_at: datetime | None = None
        self.forecast_24h: float | None = None

    def _system_config(self) -> SystemConfig:
        options = {**DEFAULT_OPTIONS, **self.entry.options}
        return SystemConfig.from_options(options, dt_util.get_default_time_zone())

    def real_system_config(self) -> SystemConfig:
        """System configuration with the real entities, also during the demo."""
        return self._system_config()

    def _controller_configs(self) -> tuple[SystemConfig, list[RoomConfig]]:
        """Return the core configuration; in the demo it points at the demo entities."""
        system = self._system_config()
        if self.demo is None:
            return system, self.rooms
        self.layout = build_layout(self.hass, self.entry.entry_id, self.demo_mode, self.rooms)
        self.demo.layout = self.layout
        return remap(system, self.rooms, self.layout)

    def _stored(self) -> dict[str, Any]:
        if self.demo is None:
            return self.controller.to_dict()
        return {"controller": self.controller.to_dict(), "sim": self.demo.to_dict()}

    # --- Lifecycle ----------------------------------------------------------

    async def async_start(self) -> None:
        """Restore state, subscribe to entities and run the first step."""
        data = await self.store.async_load()
        if self.demo is not None:
            data = data or {}
            self.demo.restore(data.get("sim", {}))
            data = data.get("controller")
        self.controller.restore(data, dt_util.utcnow())
        self._mirror_ends_at = self.controller.modes.manual_ends_at
        self._activate()
        self.async_step()
        self._cleanup_stale_problems()
        self._schedule_forecast()

    @callback
    def _activate(self) -> None:
        """Follow entity changes and timers."""
        self._stopped = False
        if self.demo is not None:
            self.demo.start()
        self._subscribe()
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_tick, timedelta(seconds=UPDATE_INTERVAL_S)
            )
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_forecast_tick, FORECAST_INTERVAL)
        )

    @callback
    def deactivate(self) -> None:
        """Stop reacting to entities and timers. Outputs are left as they are.

        Called before the platforms unload: removing our own entities (the demo
        boiler above all) must not be seen as a failing boiler.
        """
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        self._cancel_hold_step()
        if self.demo is not None:
            self.demo.stop()

    @callback
    def reactivate(self) -> None:
        """Resume after an unload that did not complete."""
        self._activate()
        self.async_step()

    async def async_save(self) -> None:
        """Save the control state now."""
        await self.store.async_save(self._stored())

    async def async_stop(self) -> None:
        """Deactivate and save the state."""
        self.deactivate()
        await self.async_save()

    @callback
    def apply_config(self) -> None:
        """Apply changed options or room data without reloading (NFR-13)."""
        self.rooms = room_configs(self.entry)
        self.controller.reconfigure(*self._controller_configs())
        self._subscribe()
        self.async_step()
        self._schedule_forecast()

    @callback
    def _subscribe(self) -> None:
        if self._state_unsub:
            self._state_unsub()
        self._watched = sorted(self.controller.watched_entities())
        self._state_unsub = async_track_state_change_event(
            self.hass, self._watched, self._async_state_changed
        )

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register an entity update callback."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    # --- Step ---------------------------------------------------------------

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        self.async_step()

    @callback
    def _async_tick(self, now: datetime) -> None:
        self.async_step()

    def _snapshot(self) -> Snapshot:
        entities: dict[str, EntityReading] = {}
        for entity_id in self._watched:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            entities[entity_id] = EntityReading(
                state=state.state,
                value=_numeric(entity_id, state.state, state.attributes),
                last_reported=state.last_reported,
                attributes=state.attributes,
            )
        return Snapshot(dt_util.utcnow(), entities, self.forecast_24h)

    @callback
    def async_step(self) -> None:
        """Run one control step and execute its plan (NFR-01: never raise)."""
        if self._stopped:
            return
        try:
            plan = self.controller.step(self._snapshot())
        except Exception:
            _LOGGER.exception("Control step failed")
            return
        self.last_plan = plan
        # Log before executing: a command can change an entity at once and run a
        # nested step, which would replace the decisions of this one.
        self._log_decisions(list(self.controller.decisions))
        for command in plan.commands:
            self.entry.async_create_background_task(
                self.hass, self._async_execute(command), f"{DOMAIN} {command.entity_id}"
            )
        self._handle_problems()
        self._sync_mirror_timer()
        self._sync_hold_step()
        self.store.async_delay_save(self._stored, SAVE_DELAY_S)
        for listener in list(self._listeners):
            listener()

    # --- Step at the end of a time rule ---------------------------------------------

    @callback
    def _sync_hold_step(self) -> None:
        """Schedule one step when the current time rule ends (min run, pause, overrun…)."""
        until = self.controller.boiler_status.until
        if until == self._hold_at:
            return
        self._cancel_hold_step()
        if until is None or until <= dt_util.utcnow():
            return
        self._hold_at = until
        self._hold_unsub = async_track_point_in_utc_time(
            self.hass, self._async_hold_ended, until + HOLD_STEP_DELAY
        )

    @callback
    def _async_hold_ended(self, now: datetime) -> None:
        self._hold_unsub = None
        self._hold_at = None
        self.async_step()

    @callback
    def _cancel_hold_step(self) -> None:
        if self._hold_unsub is not None:
            self._hold_unsub()
        self._hold_unsub = None
        self._hold_at = None

    # --- Decision log (logbook and log) ------------------------------------------

    def system_entity_id(self, domain: str, key: str) -> str | None:
        """Entity ID of a system entity of this entry (renames are kept)."""
        return er.async_get(self.hass).async_get_entity_id(
            domain, DOMAIN, f"{self.entry.entry_id}_{key}"
        )

    @callback
    def _log_decisions(self, decisions: list[Decision]) -> None:
        """Write boiler decisions and reverted outputs to the logbook and the log."""
        trigger, self._trigger = self._trigger, None
        if not decisions:
            return
        reason_entity = self.system_entity_id("sensor", "boiler_reason")
        registry = er.async_get(self.hass)
        for decision in decisions:
            if decision.kind == "reverted":
                entity_id = decision.params.get("entity_id")
            elif decision.kind == "presence":
                entity_id = self.system_entity_id("climate", "system")
            elif decision.kind == "season":
                entity_id = self.system_entity_id("binary_sensor", "heating_season")
            elif decision.kind in ("preheat", "room_target"):
                entity_id = registry.async_get_entity_id(
                    "climate",
                    DOMAIN,
                    f"{self.entry.entry_id}_{decision.params.get('room_id')}_climate",
                )
            else:
                entity_id = reason_entity
            state = self.hass.states.get(entity_id) if entity_id else None
            options = {
                "trigger": trigger,
                "shadow": self.controller.cfg.shadow_mode,
                "demo": self.demo is not None,
                "name": state.name if state else None,
            }
            message = decision_text(self.hass, decision, **options)
            _LOGGER.info("%s", decision_text(self.hass, decision, subject=True, **options))
            self.hass.bus.async_fire(
                EVENT_DECISION,
                {
                    "name": self.entry.title,
                    "message": message,
                    "entity_id": entity_id,
                    **_event_data(decision),
                },
                context=self.context,
            )

    def _owned(self, entity_id: str) -> bool:
        """Return True when the entity belongs to this config entry (demo safety net)."""
        entry = er.async_get(self.hass).async_get(entity_id)
        return (
            entry is not None
            and entry.platform == DOMAIN
            and entry.config_entry_id == self.entry.entry_id
        )

    # --- Weather forecast (FR-EQ-06) -------------------------------------------

    @callback
    def _schedule_forecast(self) -> None:
        self.entry.async_create_background_task(
            self.hass, self.async_update_forecast(), f"{DOMAIN} forecast"
        )

    @callback
    def _async_forecast_tick(self, now: datetime) -> None:
        self._schedule_forecast()

    async def async_update_forecast(self) -> None:
        """Average forecast temperature for the next 24 hours."""
        cfg = self.controller.cfg
        entity = cfg.weather_entity
        if not cfg.use_forecast or not entity:
            self.forecast_24h = None
            return
        value = None
        for forecast_type in ("hourly", "twice_daily", "daily"):
            try:
                response = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": entity, "type": forecast_type},
                    blocking=True,
                    return_response=True,
                )
            except Exception:  # unsupported forecast type or unavailable entity
                continue
            value = _forecast_mean(response.get(entity, {}).get("forecast", []), forecast_type)
            if value is not None:
                break
        if value is None:
            _LOGGER.debug("No forecast available from %s", entity)
        self.forecast_24h = value
        self.async_step()

    async def _async_execute(self, command: Command) -> None:
        if self.demo is not None and not self._owned(command.entity_id):
            _LOGGER.error(
                "Demo mode: refused %s for %s, the entity is not a demo entity",
                command.action,
                command.entity_id,
            )
            return
        domain = command.entity_id.split(".", 1)[0]
        data: dict[str, Any] = {"entity_id": command.entity_id}
        if command.action in ("open", "close"):
            service = f"{command.action}_valve"
        elif command.action == "select":
            service = "select_option"
            data["option"] = command.option
        elif command.action == "run":
            service = "turn_on" if domain == "script" else "press"
        else:
            service = command.action
        try:
            await self.hass.services.async_call(
                domain, service, data, blocking=True, context=self.context
            )
        except Exception as err:
            _LOGGER.warning("%s.%s for %s failed: %s", domain, service, command.entity_id, err)

    # --- Problems, notifications and repairs (FR-SAFE-04) ---------------------

    def _placeholders(self, problem: Problem) -> dict[str, str]:
        placeholders = dict(problem.placeholders)
        if "reason" in placeholders:
            placeholders["reason"] = reason_text(self.hass, placeholders["reason"])
        return placeholders

    def _problem_keys(self) -> set[str]:
        """All problem keys the current configuration can produce."""
        keys = {"fault_safe"}
        for room in [*self.rooms, *(r.cfg for r in self.controller.rooms.values())]:
            keys.update(f"{kind}_{room.slug}" for kind in ROOM_PROBLEM_KINDS)
            keys.update(f"valve_command_{valve.entity_id}" for valve in room.valves)
        return keys

    @callback
    def _cleanup_stale_problems(self) -> None:
        """Remove issues and notifications left by a previous instance.

        A problem that is still real is reported again as soon as the controller
        detects it.
        """
        current = set(self.controller.problems)
        registry = ir.async_get(self.hass)
        for domain, issue_id in list(registry.issues):
            if domain == DOMAIN and issue_id not in current:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        for key in self._problem_keys() - current:
            persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{key}")

    @callback
    def _handle_problems(self) -> None:
        if self._stopped:
            return
        current = self.controller.problems
        for key in current.keys() - self._known_problems.keys():
            self._report(current[key])
        for key in self._known_problems.keys() - current.keys():
            self._clear(self._known_problems[key])
        self._known_problems = dict(current)

    @callback
    def _report(self, problem: Problem) -> None:
        if self._stopped:
            return
        placeholders = self._placeholders(problem)
        title, message = notification_text(self.hass, problem.kind, placeholders)
        if self.demo is not None:
            title = f"[Demo] {title}"
        _LOGGER.warning("%s: %s", title, message)
        persistent_notification.async_create(self.hass, message, title, f"{DOMAIN}_{problem.key}")
        if service := self.controller.cfg.notify_service:
            notify_domain, _, name = service.partition(".")
            self.hass.async_create_task(
                self.hass.services.async_call(
                    notify_domain, name, {"title": title, "message": message}, blocking=False
                ),
                eager_start=True,
            )
        if problem.repair:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                problem.key,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=problem.kind,
                translation_placeholders=placeholders,
            )

    @callback
    def _clear(self, problem: Problem) -> None:
        persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{problem.key}")
        if problem.repair:
            ir.async_delete_issue(self.hass, DOMAIN, problem.key)

    # --- Manual timer mirror (FR-MAN-02) ----------------------------------------

    @callback
    def _sync_mirror_timer(self) -> None:
        ends_at = self.controller.modes.manual_ends_at
        if ends_at == self._mirror_ends_at:
            return
        self._mirror_ends_at = ends_at
        timer = self.controller.cfg.mirror_timer_entity
        if not timer:
            return
        if ends_at is None:
            service, data = "cancel", {"entity_id": timer}
        else:
            seconds = max(1, int((ends_at - dt_util.utcnow()).total_seconds()))
            duration = str(timedelta(seconds=seconds))
            service, data = "start", {"entity_id": timer, "duration": duration}
        self.hass.async_create_task(
            self.hass.services.async_call("timer", service, data, blocking=False),
            eager_start=True,
        )

    # --- User actions -------------------------------------------------------------

    @callback
    def _after_action(self) -> None:
        self.async_step()
        self.hass.async_create_task(self.store.async_save(self._stored()))

    @callback
    def set_mode(self, mode: str) -> None:
        """Select the system mode (FR-MODE-01)."""
        self.controller.set_mode(SystemMode(mode), dt_util.utcnow())
        self._trigger = ("mode", mode)
        self._after_action()

    @callback
    def set_season_mode(self, mode: str) -> None:
        """Heating season: auto, on or off (FR-EQ-03)."""
        self.controller.set_season_mode(mode, dt_util.utcnow())
        self._after_action()

    @callback
    def start_manual(self, minutes: int) -> None:
        """Start manual heating (FR-MAN-01)."""
        self.controller.start_manual(minutes, dt_util.utcnow())
        self._after_action()

    @callback
    def stop_manual(self) -> None:
        """Stop manual heating (FR-MAN-03)."""
        self.controller.stop(dt_util.utcnow())
        self._trigger = ("stop", None)
        self._after_action()

    @callback
    def set_room_hvac_mode(self, room_id: str, mode: str) -> None:
        """Set the HVAC mode of a room."""
        self.controller.rooms[room_id].set_hvac_mode(RoomHvacMode(mode), dt_util.utcnow())
        self._after_action()

    @callback
    def set_room_preset(self, room_id: str, preset: str) -> None:
        """Set the preset of a room (override in auto)."""
        self.controller.rooms[room_id].set_preset(Preset(preset), dt_util.utcnow())
        self._after_action()

    @callback
    def set_room_target(self, room_id: str, temperature: float) -> None:
        """Set a manual target temperature (override in auto)."""
        self.controller.rooms[room_id].set_target(temperature, dt_util.utcnow())
        self._after_action()

    @callback
    def set_shadow_mode(self, enabled: bool) -> None:
        """Store the shadow mode in the options; the update listener applies it."""
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, CONF_SHADOW_MODE: enabled}
        )

    @callback
    def set_room_value(self, room_id: str, key: str, value: Any) -> None:
        """Store a room setting in its subentry; the update listener applies it."""
        subentry = self.entry.subentries[room_id]
        self.hass.config_entries.async_update_subentry(
            self.entry, subentry, data={**subentry.data, key: value}
        )
