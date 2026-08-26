"""Tests for AgentForge Tester Agent and supporting tools."""

import json
import os
import shutil
import tempfile
import pytest

from backend.agents.coder_agent import CoderAgent
from backend.agents.tester_agent import TesterAgent
from backend.tools.coder_tools import copy_template, read_file, write_file
from backend.tools.designer_tools import write_design_json
from backend.tools.file_tools import write_plan_json
from backend.tools.tester_tools import (
    check_agent_wiring,
    check_independent_execution,
    check_vercel_structure,
    scan_for_secrets,
)


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory."""
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
                "description": "Coordinates support workflow",
                "responsibility": "Routes requests to specialized agents",
                "input": ["user_query"],
                "output": ["final_response"],
                "is_root": True,
                "tools_required": [],
            },
            {
                "id": "agent2",
                "name": "knowledge_agent",
                "description": "Searches company docs",
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
                "inputs": [{"name": "user_query", "type": "string", "description": "User question", "required": True}],
                "outputs": [{"name": "final_response", "type": "string", "description": "Response to user"}],
                "tools": [],
                "constraints": ["Do not answer out-of-scope questions"],
                "error_handling": ["Fallback to human escalation"],
                "handoff": {"upstream": [], "downstream": ["agent2"]},
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
                "inputs": [{"name": "user_query", "type": "string", "description": "User question", "required": True}],
                "outputs": [{"name": "knowledge_context", "type": "string", "description": "Retrieved documentation context"}],
                "tools": [
                    {
                        "name": "document_search",
                        "description": "Searches internal documentation",
                        "purpose": "Find documentation relevant to user_query",
                        "inputs": [{"name": "query", "type": "string", "description": "Search term"}],
                        "outputs": [{"name": "results", "type": "string", "description": "Search snippets"}],
                        "when_to_use": "When question requires company docs",
                        "restrictions": ["Read only access"],
                    }
                ],
                "constraints": ["Only cite verified documentation"],
                "error_handling": ["Return empty result if docs not found"],
                "handoff": {"upstream": ["agent1"], "downstream": []},
            },
        ],
        "wiring": sample_plan["wiring"],
    }


def test_1_blocked_on_invalid_plan(temp_project_dir):
    """Test 1 — Returns status blocked and responsible_agent architect_agent if plan.json is missing or invalid."""
    tester = TesterAgent()
    res = tester.validate_project(project_path=temp_project_dir)
    assert res["status"] == "blocked"
    assert res["next_action"]["agent"] == "architect_agent"
    assert res["checks"]["plan"] == "failed"


def test_2_blocked_on_invalid_design(temp_project_dir, sample_plan):
    """Test 2 — Returns status blocked and responsible_agent designer_agent if design.json is missing or invalid."""
    write_plan_json(temp_project_dir, sample_plan)
    tester = TesterAgent()
    res = tester.validate_project(project_path=temp_project_dir)
    assert res["status"] == "blocked"
    assert res["next_action"]["agent"] == "designer_agent"
    assert res["checks"]["plan"] == "passed"
    assert res["checks"]["design"] == "failed"


def test_3_structure_and_agent_verification(temp_project_dir, sample_plan, sample_design):
    """Test 3 — Full pipeline validation passes when Coder Agent generates full application."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    tester = TesterAgent()
    res = tester.validate_project(project_path=temp_project_dir)
    assert res["status"] == "passed"
    assert res["checks"]["structure"] == "passed"
    assert res["checks"]["agents"] == "passed"


def test_4_tool_verification(temp_project_dir, sample_plan, sample_design):
    """Test 4 — Identifies missing tool definitions in tools.py."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    # Break agent2 tools.py
    tools_py = os.path.join(temp_project_dir, "agents", "agent2", "tools.py")
    write_file(tools_py, "TOOLS_LIST = []\n")

    tester = TesterAgent()
    res = tester.validate_project(project_path=temp_project_dir)
    assert res["status"] == "failed"
    assert res["checks"]["tools"] == "failed"


def test_5_wiring_verification(temp_project_dir, sample_plan, sample_design):
    """Test 5 — Identifies unhandled imports or missing agents in root agent.py."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    # Break root agent.py wiring import
    root_agent_py = os.path.join(temp_project_dir, "agent.py")
    content = read_file(root_agent_py)
    broken_content = content.replace("from agents.agent2.agent import", "# broken import")
    write_file(root_agent_py, broken_content)

    wiring_res = check_agent_wiring(temp_project_dir)
    assert wiring_res["valid"] is False

    tester = TesterAgent()
    res = tester.validate_project(project_path=temp_project_dir)
    assert res["status"] == "failed"
    assert res["checks"]["wiring"] == "failed"


def test_6_test_suite_execution(temp_project_dir, sample_plan, sample_design):
    """Test 6 — Executes project unit tests and collects tests_run, tests_passed, tests_failed."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    tester = TesterAgent()
    res = tester.validate_project(project_path=temp_project_dir)
    assert res["summary"]["tests_run"] > 0
    assert res["summary"]["tests_passed"] > 0
    assert res["summary"]["tests_failed"] == 0


def test_7_smoke_test(temp_project_dir, sample_plan, sample_design):
    """Test 7 — Smoke test verifies root agent and fast_api app initialization."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    tester = TesterAgent()
    res = tester.validate_project(project_path=temp_project_dir)
    assert res["checks"]["smoke_test"] == "passed"


def test_8_secret_scanning(temp_project_dir):
    """Test 8 — Detects exposed secrets and returns SECURITY_ERROR."""
    secret_file = os.path.join(temp_project_dir, "config.py")
    write_file(secret_file, "AGENTFORGE_TEST_SECRET_12345678901234567890")

    scan_res = scan_for_secrets(temp_project_dir)
    assert scan_res["secrets_found"] is True
    assert len(scan_res["exposed_secrets"]) > 0


def test_9_independent_execution(temp_project_dir):
    """Test 9 — Detects internal AgentForge package imports in generated code."""
    bad_file = os.path.join(temp_project_dir, "bad_agent.py")
    write_file(bad_file, "from backend.agents.coder_agent import CoderAgent\n")

    indep_res = check_independent_execution(temp_project_dir)
    assert indep_res["is_independent"] is False
    assert len(indep_res["violations"]) == 1


def test_10_test_result_json_output(temp_project_dir, sample_plan, sample_design):
    """Test 10 — Writes test_result.json conforming to handoff contract."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    tester = TesterAgent()
    res = tester.validate_project(project_path=temp_project_dir)

    test_result_file = os.path.join(temp_project_dir, "docs", "test_result.json")
    assert os.path.isfile(test_result_file)
    with open(test_result_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["status"] == res["status"]
    assert "checks" in loaded
    assert "next_action" in loaded
