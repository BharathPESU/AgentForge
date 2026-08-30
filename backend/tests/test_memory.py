"""Unit tests for AgentForge MemoryService."""

import pytest
from backend.services.memory_service import MemoryService, is_memory_enabled


def test_remember_and_get_memory():
    mem_id = MemoryService.remember(
        user_id="user_123",
        project_id="proj_abc",
        memory_type="architecture_decision",
        content="Prefer FastAPI over Flask for microservices",
        metadata={"priority": "high"},
    )
    assert mem_id.startswith("mem_")

    mem = MemoryService.get_memory(mem_id)
    assert mem is not None
    assert mem["content"] == "Prefer FastAPI over Flask for microservices"
    assert mem["memory_type"] == "architecture_decision"


def test_search_memory():
    user_id = "user_search_test"
    MemoryService.remember(
        user_id=user_id,
        project_id="proj_1",
        memory_type="user_preference",
        content="Always use dark mode themes",
    )
    MemoryService.remember(
        user_id=user_id,
        project_id="proj_1",
        memory_type="known_issue",
        content="Vercel rate limit on deployment endpoints",
    )

    results = MemoryService.search_memory(user_id=user_id, query="dark mode")
    assert len(results) == 1
    assert "dark mode" in results[0]["content"]


def test_forget_memory():
    mem_id = MemoryService.remember(
        user_id="user_forget",
        project_id="proj_x",
        memory_type="successful_pattern",
        content="Use round robin for API keys",
    )
    assert MemoryService.get_memory(mem_id) is not None

    deleted = MemoryService.forget_memory(mem_id)
    assert deleted is True
    assert MemoryService.get_memory(mem_id) is None
