"""Context Selector Service for AgentForge.

Filters and extracts compact, stage-relevant execution context for downstream agents,
keeping token usage low while avoiding prompt bloat.
"""

from typing import Any, Dict, List, Optional
from backend.services.context_service import ContextService


STAGE_DEPENDENCIES: Dict[str, List[str]] = {
    "architect": [],
    "designer": ["architect"],
    "coder": ["architect", "designer"],
    "tester": ["architect", "designer", "coder"],
    "github": ["coder", "tester"],
    "deployer": ["tester", "github"],
}

STAGE_ARTIFACT_MAPPING: Dict[str, List[str]] = {
    "architect": [],
    "designer": ["plan"],
    "coder": ["plan", "design"],
    "tester": ["plan", "design", "coder_result"],
    "github": ["test_result"],
    "deployer": ["test_result", "github_result"],
}


class ContextSelector:
    """Extracts targeted context payloads optimized for each agent's responsibility."""

    @classmethod
    def get_relevant_context(cls, project_name: str, stage: str) -> Dict[str, Any]:
        """Build compact, stage-filtered context object for an agent invocation."""
        full_context = ContextService.load_run_context(project_name)
        if not full_context:
            return {
                "project_id": project_name,
                "current_stage": stage,
                "user_idea": "",
                "previous_stages": {},
                "artifacts": {},
            }

        dependencies = STAGE_DEPENDENCIES.get(stage, [])
        artifact_keys = STAGE_ARTIFACT_MAPPING.get(stage, [])

        previous_stages_info: Dict[str, Any] = {}
        for dep_stage in dependencies:
            status = full_context.get("stage_status", {}).get(dep_stage, "unknown")
            events = [e for e in full_context.get("events", []) if e.get("stage") == dep_stage]
            last_event = events[-1] if events else {}
            previous_stages_info[dep_stage] = {
                "status": status,
                "summary": last_event.get("summary", f"{dep_stage} stage {status}"),
                "artifact": last_event.get("artifact", ""),
            }

        filtered_artifacts: Dict[str, Any] = {}
        all_artifacts = full_context.get("artifacts", {})
        for key in artifact_keys:
            if key in all_artifacts:
                filtered_artifacts[key] = all_artifacts[key]

        return {
            "run_id": full_context.get("run_id"),
            "project_id": project_name,
            "current_stage": stage,
            "user_idea": full_context.get("user_idea", ""),
            "context_summary": full_context.get("context_summary", ""),
            "previous_stages": previous_stages_info,
            "artifacts": filtered_artifacts,
        }
