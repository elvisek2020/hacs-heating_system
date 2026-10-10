"""System mode and the manual timer (FR-MODE-01, FR-MAN, chapter 11.5)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .model import SystemMode


class ModeManager:
    """Selected system mode and manual heating with a timer."""

    def __init__(self) -> None:
        """Start in auto."""
        self.mode = SystemMode.AUTO
        self.mode_before_manual = SystemMode.AUTO
        self.manual_ends_at: datetime | None = None
        self.last_transition: dict[str, str] | None = None

    def _transition(self, new: SystemMode, now: datetime, reason: str) -> None:
        if new is not self.mode:
            self.last_transition = {
                "from": self.mode.value,
                "to": new.value,
                "reason": reason,
                "at": now.isoformat(),
            }
        self.mode = new

    def set_mode(self, mode: SystemMode, now: datetime, default_minutes: int) -> None:
        """Select a mode; `manual` starts the default duration (FR-MODE-01)."""
        if mode is SystemMode.MANUAL:
            self.start_manual(default_minutes, now, "replace")
            return
        self.manual_ends_at = None
        self._transition(mode, now, "user")

    def start_manual(self, minutes: int, now: datetime, restart_policy: str) -> None:
        """Start or prolong manual heating (FR-MAN-01)."""
        if self.mode is SystemMode.MANUAL and self.manual_ends_at and restart_policy == "extend":
            self.manual_ends_at += timedelta(minutes=minutes)
        else:
            self.manual_ends_at = now + timedelta(minutes=minutes)
        if self.mode is not SystemMode.MANUAL:
            self.mode_before_manual = self.mode
        self._transition(SystemMode.MANUAL, now, "manual_start")

    def stop(self, now: datetime, stop_policy: str) -> bool:
        """Stop manual heating (FR-MAN-03). Returns True if manual was running."""
        if self.mode is not SystemMode.MANUAL:
            return False
        target = self.mode_before_manual if stop_policy == "resume" else SystemMode.OFF
        self.manual_ends_at = None
        self._transition(target, now, "stop")
        return True

    def tick(self, now: datetime) -> None:
        """End manual heating when the timer expires (also after a restart)."""
        if self.mode is SystemMode.MANUAL and (
            self.manual_ends_at is None or now >= self.manual_ends_at
        ):
            self.manual_ends_at = None
            self._transition(self.mode_before_manual, now, "expired")

    def remaining_s(self, now: datetime) -> int | None:
        """Seconds of manual heating left."""
        if self.manual_ends_at is None:
            return None
        return max(0, int((self.manual_ends_at - now).total_seconds()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize (FR-MAN-05)."""
        return {
            "mode": self.mode.value,
            "mode_before_manual": self.mode_before_manual.value,
            "manual_ends_at": self.manual_ends_at.isoformat() if self.manual_ends_at else None,
            "last_transition": self.last_transition,
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore; an expired manual ends on the next tick."""
        self.mode = SystemMode(data.get("mode", SystemMode.AUTO))
        self.mode_before_manual = SystemMode(data.get("mode_before_manual", SystemMode.AUTO))
        ends = data.get("manual_ends_at")
        self.manual_ends_at = datetime.fromisoformat(ends) if ends else None
        self.last_transition = data.get("last_transition")
