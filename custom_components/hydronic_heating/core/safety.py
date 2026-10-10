"""Command verification, retries and keep-alive (FR-VAL-04, FR-BOI-04, FR-BOI-05)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_RETRY_BACKOFF_S = 60


@dataclass(slots=True)
class OutputState:
    """Command bookkeeping of one output entity."""

    expected: bool | None = None
    deadline: datetime | None = None
    attempts: int = 0
    sent_at: datetime | None = None
    last_sent: datetime | None = None
    last_desired: bool | None = None
    failed: bool = False
    latency_ms: int | None = None


class OutputTracker:
    """Decides when to send a command and verifies that the entity followed it."""

    def __init__(self) -> None:
        """Start with no history."""
        self.outputs: dict[str, OutputState] = {}

    def state(self, key: str) -> OutputState:
        """Return the bookkeeping of an output."""
        return self.outputs.setdefault(key, OutputState())

    def failed(self, key: str) -> bool:
        """Return True when the last command was not confirmed after all retries."""
        return key in self.outputs and self.outputs[key].failed

    def evaluate(
        self,
        key: str,
        now: datetime,
        *,
        desired: bool,
        observed: bool | None,
        available: bool,
        verifiable: bool,
        verify_timeout_s: float,
        retries: int,
        keep_alive_s: float,
    ) -> bool:
        """Return True when a command for `desired` should be sent now."""
        st = self.state(key)
        if st.last_sent is None:
            # Start the keep-alive clock without sending anything yet.
            st.last_sent = now
        if not verifiable:
            return self._evaluate_blind(st, now, desired, keep_alive_s)

        if st.expected is not None:
            if observed == st.expected:
                st.latency_ms = int((now - st.sent_at).total_seconds() * 1000)  # type: ignore[operator]
                st.expected, st.failed, st.attempts = None, False, 0
            elif desired != st.expected:
                st.expected = None
            elif now >= st.deadline:  # type: ignore[operator]
                if st.attempts <= retries and available:
                    return self._send(st, now, desired, verify_timeout_s, retry=True)
                st.expected, st.failed = None, True
                return False
            else:
                return False

        if not available:
            return False
        if desired != observed:
            backoff = max(keep_alive_s, MIN_RETRY_BACKOFF_S)
            if st.failed and (now - st.last_sent).total_seconds() < backoff:
                return False
            return self._send(st, now, desired, verify_timeout_s, retry=False)
        if keep_alive_s > 0 and (now - st.last_sent).total_seconds() >= keep_alive_s:
            st.last_sent = now
            return True
        return False

    @staticmethod
    def _send(
        st: OutputState, now: datetime, desired: bool, timeout_s: float, *, retry: bool
    ) -> bool:
        st.expected = desired
        st.deadline = now + timedelta(seconds=timeout_s)
        st.attempts = st.attempts + 1 if retry else 1
        st.sent_at = st.sent_at if retry else now
        st.last_sent = now
        return True

    @staticmethod
    def _evaluate_blind(st: OutputState, now: datetime, desired: bool, keep_alive_s: float) -> bool:
        """Send stateless outputs (scripts, buttons) on change and on keep-alive."""
        due = keep_alive_s > 0 and (now - st.last_sent).total_seconds() >= keep_alive_s  # type: ignore[operator]
        if desired != st.last_desired or due:
            st.last_desired = desired
            st.last_sent = now
            return True
        return False

    def reset(self) -> None:
        """Forget pending verifications (shadow mode, reconfiguration)."""
        for st in self.outputs.values():
            st.expected = None
            st.attempts = 0
