"""Unit tests for AgentForge Shared Context Service."""

import os
import shutil
import pytest

from backend.services.context_service import ContextService, is_context_enabled
from backend.services.context_selector import ContextSelector
from backend.services.context_prompt_builder import ContextPromptBuilder
from backend.tools.context_tools import (
    get_current_context,
    get_relevant_context,
    get_artifact_reference,
    get_artifact,
    record_stage_event,
)


@pytest.fixture
def test_project(tmp_path):
    project_name = "test_context_proj"
    ContextService.create_run_context(
        project_name=project_name,
        user_idea="Build an automated triage system",
        user_id="user_test_1",
    )
    yield project_name
    # Cleanup in-memory context
    from backend.services.context_service import _IN_MEMORY_CONTEXTS
    _IN_MEMORY_CONTEXTS.pop(project_name, None)


def test_create_and_load_context(test_project):
    ctx = ContextService.load_run_context(test_project)
    assert ctx is not None
    assert ctx["project_id"] == test_project
    assert ctx["user_id"] == "user_test_1"
    assert ctx["current_stage"] == "architect"
    assert "stage_status" in ctx
    assert ctx["stage_status"]["architect"] == "waiting"


def test_stage_updates_and_events(test_project):
    ContextService.set_current_stage(test_project, "designer")
    ctx = ContextService.load_run_context(test_project)
    assert ctx["current_stage"] == "designer"
    assert ctx["stage_status"]["designer"] == "in_progress"

    ContextService.record_stage_status(test_project, "designer", "completed")
    ctx = ContextService.load_run_context(test_project)
    assert ctx["stage_status"]["designer"] == "completed"


def test_artifact_registration_and_retrieval(test_project):
    dummy_path = os.path.join(os.getcwd(), "generated", test_project, "docs", "plan.json")
    ContextService.record_artifact(
        project_name=test_project,
        artifact_type="plan",
        file_path=dummy_path,
        stage="architect",
        status="completed",
        summary="Created architecture plan",
    )

    ref = ContextService.get_artifact_reference(test_project, "plan")
    assert ref is not None
    assert ref["path"] == dummy_path
    assert ref["stage"] == "architect"


def test_context_selector(test_project):
    # Setup previous stage completions
    ContextService.record_stage_status(test_project, "architect", "completed")
    ContextService.record_artifact(
        project_name=test_project,
        artifact_type="plan",
        file_path="/path/to/plan.json",
        stage="architect",
        summary="Architect plan summary",
    )

    rel_context = ContextSelector.get_relevant_context(test_project, "designer")
    assert rel_context["current_stage"] == "designer"
    assert "architect" in rel_context["previous_stages"]
    assert rel_context["previous_stages"]["architect"]["status"] == "completed"
    assert "plan" in rel_context["artifacts"]


def test_context_prompt_builder(test_project):
    prompt_block = ContextPromptBuilder.build_context_block(test_project, "coder")
    assert "CURRENT AGENTFORGE CONTEXT" in prompt_block
    assert test_project in prompt_block
    assert "CODER" in prompt_block


def test_user_and_project_isolation(test_project):
    proj2 = "test_context_proj_2"
    ContextService.create_run_context(
        project_name=proj2,
        user_idea="Different prompt",
        user_id="user_test_2",
    )

    ctx1 = ContextService.load_run_context(test_project)
    ctx2 = ContextService.load_run_context(proj2)

    assert ctx1["user_id"] == "user_test_1"
    assert ctx2["user_id"] == "user_test_2"
    assert ctx1["project_id"] != ctx2["project_id"]

    from backend.services.context_service import _IN_MEMORY_CONTEXTS
    _IN_MEMORY_CONTEXTS.pop(proj2, None)


def test_secret_safety_in_context(test_project):
    ctx = ContextService.load_run_context(test_project)
    ctx_str = str(ctx)
    assert "GEMINI_API_KEY" not in ctx_str
    assert "GITHUB_TOKEN" not in ctx_str
    assert "VERCEL_TOKEN" not in ctx_str
