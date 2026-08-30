"""Long-Term Memory Service for AgentForge.

Provides an optional, non-critical persistence layer for storing reusable insights,
architecture decisions, user preferences, and successful execution patterns across runs.
"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

_IN_MEMORY_STORE: Dict[str, Dict[str, Any]] = {}

VALID_MEMORY_TYPES = {
    "user_preference",
    "project_preference",
    "architecture_decision",
    "known_issue",
    "successful_pattern",
    "deployment_preference",
}


def is_memory_enabled() -> bool:
    """Check if the optional long-term memory feature is enabled via environment variable."""
    return os.getenv("AGENT_MEMORY_ENABLED", "false").lower() == "true"


class MemoryService:
    """Service to persist, search, and manage long-term reusable memories."""

    @classmethod
    def remember(
        cls,
        user_id: str,
        project_id: str,
        memory_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist a new memory entry if memory feature is enabled."""
        memory_id = f"mem_{uuid.uuid4().hex[:8]}"
        mtype = memory_type if memory_type in VALID_MEMORY_TYPES else "project_preference"

        memory_entry = {
            "id": memory_id,
            "user_id": user_id,
            "project_id": project_id,
            "memory_type": mtype,
            "content": content,
            "metadata": metadata or {},
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        _IN_MEMORY_STORE[memory_id] = memory_entry

        if is_memory_enabled():
            cls._persist_memory_file(project_id, memory_entry)

        return memory_id

    @classmethod
    def search_memory(
        cls,
        user_id: str,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search memory entries matching user_id, optional project_id, and search terms."""
        results = []
        query_lower = query.lower()

        for mem in _IN_MEMORY_STORE.values():
            if mem.get("user_id") != user_id:
                continue
            if project_id and mem.get("project_id") != project_id:
                continue
            if memory_type and mem.get("memory_type") != memory_type:
                continue

            content = mem.get("content", "").lower()
            if not query or query_lower in content:
                results.append(mem)

        return results

    @classmethod
    def get_memory(cls, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory entry by ID."""
        return _IN_MEMORY_STORE.get(memory_id)

    @classmethod
    def forget_memory(cls, memory_id: str) -> bool:
        """Remove a memory entry."""
        if memory_id in _IN_MEMORY_STORE:
            del _IN_MEMORY_STORE[memory_id]
            return True
        return False

    @classmethod
    def _persist_memory_file(cls, project_id: str, entry: Dict[str, Any]) -> str:
        """Save memory entry to generated/<project_id>/docs/memories.json."""
        project_dir = os.path.join(os.getcwd(), "generated", project_id)
        docs_dir = os.path.join(project_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        filepath = os.path.join(docs_dir, "memories.json")

        memories = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    memories = json.load(f)
            except Exception:
                memories = []

        memories.append(entry)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=2)

        return filepath
