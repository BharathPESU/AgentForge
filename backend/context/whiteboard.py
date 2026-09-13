"""Synchronized versioned Whiteboard access."""

from __future__ import annotations

import copy
import threading
from typing import Any, Callable, Dict

from backend.context.models import WhiteboardState


class StaleWhiteboardUpdateError(RuntimeError):
    """Raised when compare-and-update detects a stale state version."""


def _deep_merge(target: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key] = _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


class Whiteboard:
    """Thread-safe whiteboard wrapper with optimistic version checks."""

    def __init__(self, state: WhiteboardState):
        self._state = state
        self._lock = threading.RLock()

    @property
    def run_id(self) -> str:
        return self._state.run_id

    def read(self) -> WhiteboardState:
        """Return a detached snapshot of the current state."""
        with self._lock:
            return self._state.model_copy(deep=True)

    def update(self, updater: Callable[[WhiteboardState], WhiteboardState | None]) -> WhiteboardState:
        """Apply a synchronized state mutation and increment state_version."""
        with self._lock:
            working = self._state.model_copy(deep=True)
            updated = updater(working) or working
            updated.state_version = self._state.state_version + 1
            self._state = updated
            return self.read()

    def patch(self, patch_data: Dict[str, Any]) -> WhiteboardState:
        """Merge a dict patch into state atomically."""
        with self._lock:
            data = self._state.model_dump(mode="python")
            merged = _deep_merge(data, copy.deepcopy(patch_data))
            merged["state_version"] = self._state.state_version + 1
            self._state = WhiteboardState.model_validate(merged)
            return self.read()

    def append_event(self, event: Any) -> WhiteboardState:
        """Append an execution event atomically."""
        def _append(state: WhiteboardState) -> WhiteboardState:
            state.execution_history.append(event)
            return state

        return self.update(_append)

    def compare_and_update(
        self,
        expected_version: int,
        updater: Callable[[WhiteboardState], WhiteboardState | None],
    ) -> WhiteboardState:
        """Update only when caller observed the latest state_version."""
        with self._lock:
            if self._state.state_version != expected_version:
                raise StaleWhiteboardUpdateError(
                    f"stale whiteboard version: expected {expected_version}, current {self._state.state_version}"
                )
            working = self._state.model_copy(deep=True)
            updated = updater(working) or working
            updated.state_version = self._state.state_version + 1
            self._state = updated
            return self.read()
