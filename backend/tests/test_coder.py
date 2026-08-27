"""Tests for AgentForge Coder Agent and supporting tools."""

import json
import os
import shutil
import tempfile
import pytest

from backend.agents.coder_agent import CoderAgent
from backend.tools.coder_tools import (
    copy_template,
    edit_file,
    inspect_generated_structure,
    list_directory,
    read_file,
    write_file,
)
from backend.tools.designer_tools import write_design_json
from backend.tools.file_tools import write_plan_json


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for project tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_plan():
    return {
        "project": {
            "name": "ai_customer_support",
            "description": "AI Customer Support System",
            "goal": "Answer inquiries, check orders, escalate issues",
        },
        "assumptions": ["Documentation search is available"],
        "agents": [
            {
                "id": "agent1",
                "name": "support_orchestrator",
                "description": "Coordinates the support workflow",
                "responsibility": "Routes requests to specialized agents",
                "input": ["user_query"],
                "output": ["final_response"],
                "is_root": True,
                "tools_required": [],
            },
            {
                "id": "agent2",
                "name": "knowledge_agent",
                "description": "Searches company documentation",
                "responsibility": "Find relevant information",
                "input": ["user_query"],
                "output": ["knowledge_context"],
                "is_root": False,
                "tools_required": ["document_search"],
            },
        ],
        "wiring": [
            {
                "from": "agent1",
                "to": "agent2",
                "condition": "question_requires_documentation",
                "input": ["user_query"],
                "output": ["knowledge_context"],
                "execution": "sequential",
            }
        ],
    }


@pytest.fixture
def sample_design(sample_plan):
    return {
        "project": {
            "name": sample_plan["project"]["name"],
            "description": sample_plan["project"]["description"],
        },
        "agents": [
            {
                "id": "agent1",
                "name": "support_orchestrator",
                "description": "Coordinates support workflow",
                "responsibility": "Routes requests to specialized agents",
                "model": {
                    "provider": "google",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.2,
                },
                "system_prompt": "You are the Support Orchestrator Agent.",
                "inputs": [
                    {
                        "name": "user_query",
                        "type": "string",
                        "description": "User question",
                        "required": True,
                    }
                ],
                "outputs": [
                    {
                        "name": "final_response",
                        "type": "string",
                        "description": "Response to user",
                    }
                ],
                "tools": [],
                "constraints": ["Do not answer out-of-scope questions"],
                "error_handling": ["Fallback to human escalation"],
                "handoff": {
                    "upstream": [],
                    "downstream": ["agent2"],
                },
            },
            {
                "id": "agent2",
                "name": "knowledge_agent",
                "description": "Searches company docs",
                "responsibility": "Find relevant documentation",
                "model": {
                    "provider": "google",
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.2,
                },
                "system_prompt": "You are the Knowledge Agent.",
                "inputs": [
                    {
                        "name": "user_query",
                        "type": "string",
                        "description": "User question",
                        "required": True,
                    }
                ],
                "outputs": [
                    {
                        "name": "knowledge_context",
                        "type": "string",
                        "description": "Retrieved documentation context",
                    }
                ],
                "tools": [
                    {
                        "name": "document_search",
                        "description": "Searches internal documentation",
                        "purpose": "Find documentation relevant to user_query",
                        "inputs": [
                            {
                                "name": "query",
                                "type": "string",
                                "description": "Search term",
                            }
                        ],
                        "outputs": [
                            {
                                "name": "results",
                                "type": "string",
                                "description": "Search snippets",
                            }
                        ],
                        "when_to_use": "When question requires company docs",
                        "restrictions": ["Read only access"],
                    }
                ],
                "constraints": ["Only cite verified documentation"],
                "error_handling": ["Return empty result if docs not found"],
                "handoff": {
                    "upstream": ["agent1"],
                    "downstream": [],
                },
            },
        ],
        "wiring": sample_plan["wiring"],
    }


def test_1_missing_plan(temp_project_dir):
    """Test 1 — Missing plan.json causes Coder Agent to fail with reason missing_plan."""
    coder = CoderAgent()
    res = coder.generate_code(project_path=temp_project_dir)
    assert res["status"] == "failed"
    assert res["reason"] == "missing_plan"
    assert res["ready_for_testing"] is False


def test_2_missing_design(temp_project_dir, sample_plan):
    """Test 2 — Missing design.json causes Coder Agent to fail with reason missing_design."""
    write_plan_json(temp_project_dir, sample_plan)
    coder = CoderAgent()
    res = coder.generate_code(project_path=temp_project_dir)
    assert res["status"] == "failed"
    assert res["reason"] == "missing_design"
    assert res["ready_for_testing"] is False


def test_3_template_copying(temp_project_dir):
    """Test 3 — Template copying helper successfully copies backend template to target."""
    dest = os.path.join(temp_project_dir, "new_project")
    res = copy_template(dest)
    assert res["status"] == "success"
    assert os.path.isfile(os.path.join(dest, "agent.py"))
    assert os.path.isfile(os.path.join(dest, "app.py"))
    assert os.path.isfile(os.path.join(dest, "settings.yaml"))


def test_4_existing_project_reuse(temp_project_dir, sample_plan, sample_design):
    """Test 4 — Existing project directory is reused without destroying existing files."""
    dest = os.path.join(temp_project_dir, "existing_project")
    copy_template(dest)
    write_plan_json(dest, sample_plan)
    write_design_json(dest, sample_design, sample_plan)

    # Add custom file
    custom_file = os.path.join(dest, "custom.txt")
    write_file(custom_file, "custom content")

    coder = CoderAgent()
    res = coder.generate_code(project_path=dest)

    assert res["status"] == "success"
    assert os.path.isfile(custom_file)
    assert read_file(custom_file) == "custom content"


def test_5_dynamic_agent_count(temp_project_dir, sample_plan, sample_design):
    """Test 5 — Coder Agent generates agent files matching dynamic agent count from plan/design."""
    dest = os.path.join(temp_project_dir, "proj")
    write_plan_json(dest, sample_plan)
    write_design_json(dest, sample_design, sample_plan)

    coder = CoderAgent()
    res = coder.generate_code(project_path=dest)

    assert res["status"] == "success"
    assert set(res["agents_updated"]) == {"agent1", "agent2"}
    assert os.path.isdir(os.path.join(dest, "agents", "agent1"))
    assert os.path.isdir(os.path.join(dest, "agents", "agent2"))


def test_6_agent_file_generation(temp_project_dir, sample_plan, sample_design):
    """Test 6 — Every agent gets agent.py, prompt.py, tools.py."""
    dest = os.path.join(temp_project_dir, "proj")
    write_plan_json(dest, sample_plan)
    write_design_json(dest, sample_design, sample_plan)

    coder = CoderAgent()
    res = coder.generate_code(project_path=dest)

    for aid in ["agent1", "agent2"]:
        dir_path = os.path.join(dest, "agents", aid)
        assert os.path.isfile(os.path.join(dir_path, "agent.py"))
        assert os.path.isfile(os.path.join(dir_path, "prompt.py"))
        assert os.path.isfile(os.path.join(dir_path, "tools.py"))


def test_7_tool_implementation(temp_project_dir, sample_plan, sample_design):
    """Test 7 — Tool functions match assigned tools in design.json and export TOOLS_LIST."""
    dest = os.path.join(temp_project_dir, "proj")
    write_plan_json(dest, sample_plan)
    write_design_json(dest, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=dest)

    tools_py = read_file(os.path.join(dest, "agents", "agent2", "tools.py"))
    assert "def document_search" in tools_py
    assert "TOOLS_LIST = [document_search]" in tools_py

    no_tools_py = read_file(os.path.join(dest, "agents", "agent1", "tools.py"))
    assert "TOOLS_LIST = []" in no_tools_py


def test_8_root_orchestrator(temp_project_dir, sample_plan, sample_design):
    """Test 8 — Root agent.py imports and wires active sub-agents."""
    dest = os.path.join(temp_project_dir, "proj")
    write_plan_json(dest, sample_plan)
    write_design_json(dest, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=dest)

    root_py = read_file(os.path.join(dest, "agent.py"))
    assert "from agents.agent1.agent import get_agent as get_agent1" in root_py
    assert "from agents.agent2.agent import get_agent as get_agent2" in root_py


def test_9_handoff_contract(temp_project_dir, sample_plan, sample_design):
    """Test 9 — Successful execution returns structured result matching handoff contract."""
    dest = os.path.join(temp_project_dir, "proj")
    write_plan_json(dest, sample_plan)
    write_design_json(dest, sample_design, sample_plan)

    coder = CoderAgent()
    res = coder.generate_code(project_path=dest)

    assert res["status"] == "success"
    assert res["project_path"] == dest
    assert res["ready_for_testing"] is True
    assert isinstance(res["files_modified"], list)
    assert len(res["files_modified"]) > 0


def test_10_coder_tools_helpers(temp_project_dir):
    """Test 10 — Helper functions in coder_tools (inspect_generated_structure, edit_file)."""
    test_file = os.path.join(temp_project_dir, "sample.txt")
    write_file(test_file, "Hello World")
    assert read_file(test_file) == "Hello World"

    res_edit = edit_file(test_file, "World", "AgentForge")
    assert res_edit == "replaced"
    assert read_file(test_file) == "Hello AgentForge"

    struct = inspect_generated_structure(temp_project_dir)
    assert struct["exists"] is True
