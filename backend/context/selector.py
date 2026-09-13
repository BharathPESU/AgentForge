"""Compact per-agent Whiteboard context selection."""

from __future__ import annotations

from typing import Any, Dict

from backend.context.models import AGENT_TO_STAGE, WhiteboardState


class WhiteboardContextSelector:
    """Select only the whiteboard fields a specialist needs."""

    @staticmethod
    def for_agent(state: WhiteboardState, agent: str) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "run_id": state.run_id,
            "project_id": state.project_id,
            "project_path": state.project_path,
            "user_id": state.user_id,
            "user_idea": state.user_idea,
            "current_stage": AGENT_TO_STAGE.get(agent, state.current_stage),
            "retry_count": state.retry_counts.get(agent, 0),
        }

        context = state.agent_context
        if agent == "architect_agent":
            return base
        if agent == "designer_agent":
            base["architecture"] = context.get("architecture")
            return base
        if agent == "coder_agent":
            base["architecture"] = context.get("architecture")
            base["design"] = context.get("design")
            base["project_state"] = {"artifacts": state.artifacts, "files_changed": state.files_changed}
            return base
        if agent == "tester_agent":
            base["architecture"] = context.get("architecture")
            base["design"] = context.get("design")
            base["implementation"] = context.get("implementation")
            base["project_state"] = {"artifacts": state.artifacts, "files_changed": state.files_changed}
            return base
        if agent == "github_agent":
            base["architecture"] = context.get("architecture")
            base["test_result"] = context.get("test_result")
            base["project_state"] = {"artifacts": state.artifacts, "files_changed": state.files_changed}
            return base
        if agent == "deployer_agent":
            base["test_result"] = context.get("test_result")
            base["github_result"] = context.get("github_result")
            base["project_state"] = {"artifacts": state.artifacts, "files_changed": state.files_changed}
            return base
        return base
