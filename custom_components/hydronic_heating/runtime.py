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
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
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
    STORAGE_VERSION,
    SUBENTRY_ROOM,
    UPDATE_INTERVAL_S,
)
from .core.controller import HydronicController
from .core.model import (
    Command,
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
from .notifications import notification_text, reason_text

_LOGGER = logging.getLogger(__name__)

SAVE_DELAY_S = 10

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


def _numeric(entity_id: str, state: str, attributes: Mapping[str, Any]) -> float | None:
    if entity_id.startswith("climate."):
        value = attributes.get("current_temperature")
        return float(value) if isinstance(value, int | float) else None
    try:
        return float(state)
    except ValueError:
        return None


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
            self.demo.start()
            data = data.get("controller")
        self.controller.restore(data, dt_util.utcnow())
        self._mirror_ends_at = self.controller.modes.manual_ends_at
        self._subscribe()
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_tick, timedelta(seconds=UPDATE_INTERVAL_S)
            )
        )
        self.async_step()

    async def async_stop(self) -> None:
        """Unsubscribe and save the state. Outputs are left as they are."""
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        if self.demo is not None:
            self.demo.stop()
        await self.store.async_save(self._stored())

    @callback
    def apply_config(self) -> None:
        """Apply changed options or room data without reloading (NFR-13)."""
        self.rooms = room_configs(self.entry)
        self.controller.reconfigure(*self._controller_configs())
        self._subscribe()
        self.async_step()

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
        return Snapshot(dt_util.utcnow(), entities)

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
        for command in plan.commands:
            self.entry.async_create_background_task(
                self.hass, self._async_execute(command), f"{DOMAIN} {command.entity_id}"
            )
        self._handle_problems()
        self._sync_mirror_timer()
        self.store.async_delay_save(self._stored, SAVE_DELAY_S)
        for listener in list(self._listeners):
            listener()

    def _owned(self, entity_id: str) -> bool:
        """Return True when the entity belongs to this config entry (demo safety net)."""
        entry = er.async_get(self.hass).async_get(entity_id)
        return (
            entry is not None
            and entry.platform == DOMAIN
            and entry.config_entry_id == self.entry.entry_id
        )

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

    @callback
    def _handle_problems(self) -> None:
        current = self.controller.problems
        for key in current.keys() - self._known_problems.keys():
            self._report(current[key])
        for key in self._known_problems.keys() - current.keys():
            self._clear(self._known_problems[key])
        self._known_problems = dict(current)

    @callback
    def _report(self, problem: Problem) -> None:
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
