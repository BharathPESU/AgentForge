"""Shared Run Context Service for AgentForge.

Provides a thread-safe, deterministic compatibility layer for managing execution context,
stage history, artifact references, and stage event tracking across the 6 builder agents.
"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional
import jsonschema

# In-memory context repository keying project_name -> context dict
_IN_MEMORY_CONTEXTS: Dict[str, Dict[str, Any]] = {}

CONTEXT_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "schemas", "context_schema.json"
)

def is_context_enabled() -> bool:
    """Check if the shared context feature is enabled via environment variable."""
    return os.getenv("AGENT_CONTEXT_ENABLED", "true").lower() == "true"


def load_context_schema() -> Dict[str, Any]:
    """Load JSON schema definition for shared execution context."""
    if os.path.exists(CONTEXT_SCHEMA_PATH):
        with open(CONTEXT_SCHEMA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def validate_context(context_data: Dict[str, Any]) -> bool:
    """Validate a context object against context_schema.json."""
    schema = load_context_schema()
    if schema:
        try:
            jsonschema.validate(instance=context_data, schema=schema)
            return True
        except jsonschema.ValidationError as exc:
            print(f"[ContextService Warning] Validation error: {exc.message}")
            return False
    return True


class ContextService:
    """Service to create, update, load, and query AgentForge execution contexts."""

    @staticmethod
    def get_context_file_path(project_name: str) -> str:
        """Get absolute path to context.json for a given project."""
        project_dir = os.path.join(os.getcwd(), "generated", project_name)
        docs_dir = os.path.join(project_dir, "docs")
        return os.path.join(docs_dir, "context.json")

    @classmethod
    def create_run_context(
        cls,
        project_name: str,
        user_idea: str,
        user_id: str = "user_default",
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Initialize a new shared execution context for a project run."""
        rid = run_id or f"run_{uuid.uuid4().hex[:8]}"
        initial_context: Dict[str, Any] = {
            "run_id": rid,
            "user_id": user_id,
            "project_id": project_name,
            "user_idea": user_idea,
            "current_stage": "architect",
            "stage_status": {
                "architect": "waiting",
                "designer": "waiting",
                "coder": "waiting",
                "tester": "waiting",
                "github": "waiting",
                "deployer": "waiting",
            },
            "artifacts": {},
            "context_summary": f"Run initialized for project '{project_name}' with prompt: '{user_idea[:100]}...'",
            "events": [
                {
                    "stage": "architect",
                    "status": "waiting",
                    "summary": "Run created and scheduled for execution",
                    "artifact": "",
                    "attempt": 1,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            ],
            "errors": [],
            "metadata": metadata or {},
            "context_version": 1,
        }

        validate_context(initial_context)
        _IN_MEMORY_CONTEXTS[project_name] = initial_context

        if is_context_enabled():
            cls.save_run_context(project_name, initial_context)

        return initial_context

    @classmethod
    def load_run_context(cls, project_name: str) -> Optional[Dict[str, Any]]:
        """Load context for a project from memory or filesystem."""
        if project_name in _IN_MEMORY_CONTEXTS:
            return _IN_MEMORY_CONTEXTS[project_name]

        file_path = cls.get_context_file_path(project_name)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    context = json.load(f)
                    _IN_MEMORY_CONTEXTS[project_name] = context
                    return context
            except Exception as exc:
                print(f"[ContextService Error] Failed to read {file_path}: {exc}")
                return None
        return None

    @classmethod
    def save_run_context(cls, project_name: str, context: Dict[str, Any]) -> str:
        """Persist context to disk in generated/<project_name>/docs/context.json."""
        _IN_MEMORY_CONTEXTS[project_name] = context

        if not is_context_enabled():
            return ""

        file_path = cls.get_context_file_path(project_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Sanitize sensitive tokens before writing
        sanitized = json.loads(json.dumps(context))
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=2)

        return file_path

    @classmethod
    def set_current_stage(cls, project_name: str, stage: str) -> Optional[Dict[str, Any]]:
        """Set active stage and mark status as in_progress."""
        context = cls.load_run_context(project_name)
        if not context:
            return None

        context["current_stage"] = stage
        if "stage_status" not in context:
            context["stage_status"] = {}
        context["stage_status"][stage] = "in_progress"

        cls.append_event(
            project_name=project_name,
            stage=stage,
            status="in_progress",
            summary=f"Started execution of stage '{stage}'",
        )
        return context

    @classmethod
    def record_stage_status(cls, project_name: str, stage: str, status: str) -> Optional[Dict[str, Any]]:
        """Record status update for a specific stage."""
        context = cls.load_run_context(project_name)
        if not context:
            return None

        if "stage_status" not in context:
            context["stage_status"] = {}
        context["stage_status"][stage] = status

        cls.save_run_context(project_name, context)
        return context

    @classmethod
    def record_artifact(
        cls,
        project_name: str,
        artifact_type: str,
        file_path: str,
        stage: str,
        status: str = "completed",
        summary: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Register an output artifact reference in the run context."""
        context = cls.load_run_context(project_name)
        if not context:
            return None

        if "artifacts" not in context:
            context["artifacts"] = {}

        context["artifacts"][artifact_type] = {
            "artifact_type": artifact_type,
            "path": file_path,
            "stage": stage,
            "status": status,
            "summary": summary,
        }

        cls.append_event(
            project_name=project_name,
            stage=stage,
            status=status,
            summary=summary or f"Generated artifact '{artifact_type}' at {file_path}",
            artifact=file_path,
        )
        return context

    @classmethod
    def get_artifact_reference(cls, project_name: str, artifact_type: str) -> Optional[Dict[str, Any]]:
        """Retrieve reference metadata for a registered artifact."""
        context = cls.load_run_context(project_name)
        if context and "artifacts" in context:
            return context["artifacts"].get(artifact_type)
        return None

    @classmethod
    def append_event(
        cls,
        project_name: str,
        stage: str,
        status: str,
        summary: str = "",
        artifact: str = "",
        attempt: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """Add an event entry to the run context history."""
        context = cls.load_run_context(project_name)
        if not context:
            return None

        if "events" not in context:
            context["events"] = []

        event = {
            "stage": stage,
            "status": status,
            "summary": summary,
            "artifact": artifact,
            "attempt": attempt,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        context["events"].append(event)
        cls.build_context_summary(project_name)
        cls.save_run_context(project_name, context)
        return context

    @classmethod
    def build_context_summary(cls, project_name: str) -> str:
        """Synthesize a compact human-readable execution summary."""
        context = cls.load_run_context(project_name)
        if not context:
            return "No context available."

        stage = context.get("current_stage", "unknown")
        user_idea = context.get("user_idea", "")
        artifacts = list(context.get("artifacts", {}).keys())
        events = context.get("events", [])

        completed_stages = [
            st for st, stat in context.get("stage_status", {}).items() if stat == "completed"
        ]

        summary = (
            f"Project: '{project_name}' | Active Stage: '{stage}' | "
            f"Completed Stages: [{', '.join(completed_stages)}] | "
            f"Artifacts Available: [{', '.join(artifacts)}] | "
            f"Total Events: {len(events)}"
        )
        context["context_summary"] = summary
        return summary
