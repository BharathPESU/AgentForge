"""Context Prompt Builder for AgentForge.

Formats filtered context into a compact markdown string block suitable for injection
into system instructions or runtime prompts.
"""

from typing import Any, Dict
from backend.services.context_selector import ContextSelector


class ContextPromptBuilder:
    """Builds formatted Markdown context blocks for LLM prompt injection."""

    @classmethod
    def build_context_block(cls, project_name: str, stage: str) -> str:
        """Construct compact context block string for the specified stage."""
        relevant_context = ContextSelector.get_relevant_context(project_name, stage)
        user_idea = relevant_context.get("user_idea", "")
        prev_stages = relevant_context.get("previous_stages", {})
        artifacts = relevant_context.get("artifacts", {})

        lines = [
            "### CURRENT AGENTFORGE CONTEXT",
            f"**Project**: `{project_name}`",
            f"**Current Stage**: `{stage.upper()}`",
            f"**User Prompt**: \"{user_idea}\"",
        ]

        if prev_stages:
            lines.append("\n**Previous Stage Status & Summaries**:")
            for stg, info in prev_stages.items():
                status = info.get("status", "unknown")
                summary = info.get("summary", "")
                lines.append(f"- **{stg.capitalize()}**: `{status}` — {summary}")

        if artifacts:
            lines.append("\n**Available Artifact References**:")
            for art_key, art_info in artifacts.items():
                art_path = art_info.get("path", "")
                lines.append(f"- `{art_key}`: `{art_path}`")

        return "\n".join(lines)
