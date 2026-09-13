"""In-memory Whiteboard store with optional lightweight disk persistence."""

from __future__ import annotations

import json
import os
import threading
from typing import Dict, Optional

from backend.context.models import WhiteboardState
from backend.context.whiteboard import Whiteboard


_LOCK = threading.RLock()
_RUNS: Dict[str, Whiteboard] = {}
_PROJECT_TO_RUN: Dict[str, str] = {}


def whiteboard_file_path(project_path: str) -> str:
    return os.path.join(os.path.abspath(project_path), "docs", "whiteboard.json")


def register(whiteboard: Whiteboard) -> Whiteboard:
    with _LOCK:
        state = whiteboard.read()
        _RUNS[state.run_id] = whiteboard
        _PROJECT_TO_RUN[state.project_id] = state.run_id
        _PROJECT_TO_RUN[os.path.abspath(state.project_path)] = state.run_id
        return whiteboard


def get_by_run_id(run_id: str) -> Optional[Whiteboard]:
    with _LOCK:
        board = _RUNS.get(run_id)
        if board:
            return board
    # Disk fallback: scan generated/*/docs/whiteboard.json
    try:
        from pathlib import Path
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        generated_root = os.path.join(workspace_root, "generated")
        if os.path.isdir(generated_root):
            for entry in os.listdir(generated_root):
                cand = os.path.join(generated_root, entry, "docs", "whiteboard.json")
                if os.path.isfile(cand):
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if data.get("run_id") == run_id:
                            state = WhiteboardState.model_validate(data)
                            return register(Whiteboard(state))
                    except Exception:
                        continue
        # also check legacy context file fallback for run_id?
    except Exception:
        pass
    return None


def get_by_project(project_id_or_path: str) -> Optional[Whiteboard]:
    with _LOCK:
        key = os.path.abspath(project_id_or_path) if os.path.exists(project_id_or_path) else project_id_or_path
        run_id = _PROJECT_TO_RUN.get(key) or _PROJECT_TO_RUN.get(project_id_or_path)
        return _RUNS.get(run_id) if run_id else None


def persist(whiteboard: Whiteboard) -> str:
    state = whiteboard.read()
    path = whiteboard_file_path(state.project_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.model_dump(mode="json"), f, indent=2)
        f.write("\n")
    return path


def load_from_project(project_path: str) -> Optional[Whiteboard]:
    path = whiteboard_file_path(project_path)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        state = WhiteboardState.model_validate(json.load(f))
    return register(Whiteboard(state))
