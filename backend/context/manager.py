"""High-level Whiteboard state management API."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from backend.context import events
from backend.context.models import (
    AGENT_TO_STAGE,
    ALLOWED_AGENTS,
    AgentOutput,
    ArtifactReference,
    WhiteboardState,
)
from backend.context.store import get_by_project, get_by_run_id, load_from_project, persist, register
from backend.context.whiteboard import Whiteboard


SENSITIVE_KEYS = {"api_key", "token", "secret", "password", "gemini_api_key", "github_token", "vercel_token"}


def _summarize_result(result: Dict[str, Any]) -> str:
    if result.get("summary"):
        return str(result["summary"])[:500]
    if result.get("message"):
        return str(result["message"])[:500]
    if result.get("reason"):
        return str(result["reason"])[:500]
    status = result.get("status", "unknown")
    return f"Agent returned status '{status}'."


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
                clean[key] = "[redacted]"
            else:
                clean[key] = _sanitize(item)
        return clean
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


class WhiteboardManager:
    """Convenience operations for run-scoped whiteboards."""

    @staticmethod
    def create_run(
        project_id: str,
        project_path: str,
        user_idea: str,
        user_id: str = "user_default",
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Whiteboard:
        state = WhiteboardState(
            run_id=run_id or f"run_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            project_id=project_id,
            project_path=os.path.abspath(project_path),
            user_idea=user_idea,
            status="pending",
            metadata=metadata or {},
        )
        board = register(Whiteboard(state))
        WhiteboardManager.append_event(
            board,
            event_type="run_created",
            status="pending",
            summary="Run created and waiting for supervisor routing.",
        )
        return board

    @staticmethod
    def get(run_id: str) -> Optional[Whiteboard]:
        return get_by_run_id(run_id)

    @staticmethod
    def get_for_project(project_id_or_path: str) -> Optional[Whiteboard]:
        return get_by_project(project_id_or_path) or load_from_project(project_id_or_path)

    @staticmethod
    def persist(board: Whiteboard) -> str:
        return persist(board)

    @staticmethod
    def append_event(
        board: Whiteboard,
        event_type: str,
        status: str,
        summary: str = "",
        stage: Optional[str] = None,
        agent: Optional[str] = None,
        artifact: str = "",
        attempt: int = 1,
    ):
        event = events.make_event(
            event_type=event_type,
            status=status,
            summary=summary,
            stage=stage,
            agent=agent,
            artifact=artifact,
            attempt=attempt,
        )
        state = board.append_event(event)
        persist(board)
        return state

    @staticmethod
    def start_agent(board: Whiteboard, agent: str):
        if agent not in ALLOWED_AGENTS:
            raise ValueError(f"Invalid AgentForge specialist '{agent}'")
        stage = AGENT_TO_STAGE[agent]
        attempt = board.read().retry_counts.get(agent, 0) + 1

        def _start(state: WhiteboardState) -> WhiteboardState:
            state.status = "running"
            state.current_agent = agent
            state.current_stage = stage
            state.stage_states[stage] = "in_progress"
            return state

        state = board.update(_start)
        WhiteboardManager.append_event(
            board,
            event_type=events.AGENT_STARTED,
            status="in_progress",
            summary=f"Started {agent}.",
            stage=stage,
            agent=agent,
            attempt=attempt,
        )
        return state

    @staticmethod
    def complete_agent(
        board: Whiteboard,
        agent: str,
        result: Dict[str, Any],
        artifact_refs: Optional[List[ArtifactReference]] = None,
    ):
        stage = AGENT_TO_STAGE[agent]
        result = _sanitize(result)
        status = "completed" if result.get("status") in ("success", "passed", "completed") else result.get("status", "completed")
        files_changed = result.get("files_modified") or result.get("files_created") or []
        output = AgentOutput(
            agent=agent,  # type: ignore[arg-type]
            status=status,
            summary=_summarize_result(result),
            data=result,
            files_changed=files_changed,
            errors=result.get("errors") or result.get("failures") or [],
            next_recommendation=(result.get("next_action") or {}).get("agent"),
        )

        def _complete(state: WhiteboardState) -> WhiteboardState:
            state.agent_outputs[agent] = output
            state.stage_states[stage] = "completed"
            if agent == "architect_agent" and result.get("plan"):
                state.agent_context["architecture"] = result["plan"]
            elif agent == "designer_agent" and result.get("design"):
                state.agent_context["design"] = result["design"]
            elif agent == "coder_agent":
                state.agent_context["implementation"] = result
            elif agent == "tester_agent":
                state.agent_context["test_result"] = result
            elif agent == "github_agent":
                state.agent_context["github_result"] = result
            elif agent == "deployer_agent":
                state.agent_context["deployment_result"] = result
            for file_path in files_changed:
                if file_path not in state.files_changed:
                    state.files_changed.append(file_path)
            for artifact in artifact_refs or []:
                state.artifacts[artifact.artifact_type] = artifact
            completed_count = sum(1 for s in state.stage_states.values() if s == "completed")
            state.progress = min(100, int(completed_count / 6 * 100))
            return state

        state = board.update(_complete)
        WhiteboardManager.append_event(
            board,
            event_type=events.AGENT_COMPLETED,
            status="completed",
            summary=output.summary,
            stage=stage,
            agent=agent,
        )
        return state

    @staticmethod
    def fail_agent(board: Whiteboard, agent: str, result: Dict[str, Any]):
        stage = AGENT_TO_STAGE[agent]
        result = _sanitize(result)
        output = AgentOutput(
            agent=agent,  # type: ignore[arg-type]
            status=result.get("status", "failed"),
            summary=_summarize_result(result),
            data=result,
            errors=result.get("errors") or result.get("failures") or result.get("failure") or [],
            next_recommendation=(result.get("next_action") or {}).get("agent"),
        )

        def _fail(state: WhiteboardState) -> WhiteboardState:
            state.agent_outputs[agent] = output
            state.stage_states[stage] = "failed" if result.get("status") != "blocked" else "blocked"
            state.errors.append({"agent": agent, "stage": stage, "result": result})
            return state

        state = board.update(_fail)
        WhiteboardManager.append_event(
            board,
            event_type=events.AGENT_FAILED,
            status=output.status,
            summary=output.summary,
            stage=stage,
            agent=agent,
        )
        return state
