"""Agent Context Tools for AgentForge.

Exposes deterministic, lightweight helper functions for agents to query shared execution context,
read registered artifact references, retrieve artifact JSON contents on demand, and record stage events.
"""

import json
import os
from typing import Any, Dict, Optional

from backend.services.context_service import ContextService
from backend.services.context_selector import ContextSelector


def get_current_context(project_name: str) -> Dict[str, Any]:
    """Retrieve full active execution context for a project (sans secrets)."""
    ctx = ContextService.load_run_context(project_name)
    if not ctx:
        return {"status": "error", "message": f"No context found for project '{project_name}'"}
    return ctx


def get_relevant_context(project_name: str, stage: str) -> Dict[str, Any]:
    """Retrieve stage-filtered context optimized for token efficiency."""
    return ContextSelector.get_relevant_context(project_name, stage)


def get_previous_stage_summary(project_name: str, stage: str) -> str:
    """Get compact summary string of previous stage executions."""
    rel = ContextSelector.get_relevant_context(project_name, stage)
    prev = rel.get("previous_stages", {})
    if not prev:
        return "No previous stage executions."
    
    parts = []
    for stg, info in prev.items():
        parts.append(f"{stg.capitalize()} ({info.get('status')}): {info.get('summary')}")
    return " | ".join(parts)


def get_artifact_reference(project_name: str, artifact_type: str) -> Dict[str, Any]:
    """Retrieve path and metadata for a registered artifact."""
    ref = ContextService.get_artifact_reference(project_name, artifact_type)
    if not ref:
        return {"status": "not_found", "artifact_type": artifact_type}
    return ref


def get_artifact(project_name: str, artifact_type: str) -> Dict[str, Any]:
    """Retrieve full JSON content of a specific artifact on demand."""
    ref = ContextService.get_artifact_reference(project_name, artifact_type)
    if not ref or "path" not in ref:
        # Fallback to standard path conventions
        path = os.path.join(os.getcwd(), "generated", project_name, "docs", f"{artifact_type}.json")
    else:
        path = ref["path"]

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = json.load(f)
                return {"status": "success", "artifact_type": artifact_type, "path": path, "content": content}
        except Exception as exc:
            return {"status": "error", "message": f"Failed to read artifact: {str(exc)}"}

    return {"status": "not_found", "message": f"Artifact '{artifact_type}' not found at {path}"}


def record_stage_event(
    project_name: str,
    stage: str,
    status: str,
    summary: str = "",
    artifact: str = "",
    attempt: int = 1,
) -> Dict[str, Any]:
    """Append a new stage event to the shared context timeline."""
    res = ContextService.append_event(
        project_name=project_name,
        stage=stage,
        status=status,
        summary=summary,
        artifact=artifact,
        attempt=attempt,
    )
    if res:
        return {"status": "success", "stage": stage, "event_status": status}
    return {"status": "error", "message": "Failed to record stage event"}


def update_stage_status(project_name: str, stage: str, status: str) -> Dict[str, Any]:
    """Update execution status for a compiler stage."""
    res = ContextService.record_stage_status(project_name, stage, status)
    if res:
        return {"status": "success", "stage": stage, "new_status": status}
    return {"status": "error", "message": "Failed to update stage status"}
