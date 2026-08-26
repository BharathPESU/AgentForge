"""Tests for AgentForge Designer Agent and supporting tools."""

import json
import os
import shutil
import tempfile
import pytest

from backend.agents.designer_agent import DesignerAgent
from backend.tools.designer_tools import (
    read_plan_json,
    read_schema,
    validate_design_json,
    write_design_json,
)
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
def sample_valid_design(sample_plan):
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
                "system_prompt": "You are the Support Orchestrator Agent. Route user queries to knowledge or order agents.",
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
                "system_prompt": "You are the Knowledge Agent. Search company documentation to answer questions.",
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


def test_1_plan_loading(temp_project_dir, sample_plan):
    """Test 1 — Verify the Designer Agent can load an existing valid plan.json."""
    write_plan_json(temp_project_dir, sample_plan)
    plan_res = read_plan_json(temp_project_dir)
    assert plan_res["valid"] is True
    assert plan_res["data"]["project"]["name"] == "ai_customer_support"


def test_2_agent_count_preservation(temp_project_dir, sample_plan, sample_valid_design):
    """Test 2 — Verify design preserves exact agent count from plan.json."""
    write_plan_json(temp_project_dir, sample_plan)
    agent = DesignerAgent()
    mock_llm_output = json.dumps(sample_valid_design)

    result = agent.generate_design(
        project_path=temp_project_dir,
        override_llm_response=mock_llm_output,
    )

    assert result["status"] == "success"
    assert result["agents_designed"] == len(sample_plan["agents"])


def test_3_id_preservation(temp_project_dir, sample_plan, sample_valid_design):
    """Test 3 — Verify every plan agent ID exists in design.json."""
    write_plan_json(temp_project_dir, sample_plan)
    agent = DesignerAgent()
    
    result = agent.generate_design(
        project_path=temp_project_dir,
        override_llm_response=json.dumps(sample_valid_design),
    )

    assert result["status"] == "success"
    plan_ids = [a["id"] for a in sample_plan["agents"]]
    design_ids = [a["id"] for a in result["design"]["agents"]]
    assert sorted(plan_ids) == sorted(design_ids)


def test_4_system_prompts(sample_valid_design):
    """Test 4 — Verify every agent in design.json has a non-empty system prompt."""
    val_res = validate_design_json(sample_valid_design)
    assert val_res["valid"] is True

    # Empty prompt fails
    invalid_design = json.loads(json.dumps(sample_valid_design))
    invalid_design["agents"][0]["system_prompt"] = ""
    val_inv = validate_design_json(invalid_design)
    assert val_inv["valid"] is False
    assert any("system_prompt" in err for err in val_inv["errors"])


def test_5_tool_assignment(sample_valid_design):
    """Test 5 — Verify tool definitions follow the design schema."""
    val_res = validate_design_json(sample_valid_design)
    assert val_res["valid"] is True

    tools = sample_valid_design["agents"][1]["tools"]
    assert len(tools) == 1
    tool = tools[0]
    assert tool["name"] == "document_search"
    assert "when_to_use" in tool
    assert "restrictions" in tool


def test_6_wiring_preservation(temp_project_dir, sample_plan, sample_valid_design):
    """Test 6 — Verify design preserves plan wiring."""
    write_plan_json(temp_project_dir, sample_plan)
    agent = DesignerAgent()

    result = agent.generate_design(
        project_path=temp_project_dir,
        override_llm_response=json.dumps(sample_valid_design),
    )

    assert result["status"] == "success"
    assert result["design"]["wiring"] == sample_plan["wiring"]


def test_7_schema_validation(sample_valid_design, sample_plan):
    """Test 7 — Valid designs pass validate_design_json, invalid designs fail."""
    # Valid design passes
    val_valid = validate_design_json(sample_valid_design, sample_plan)
    assert val_valid["valid"] is True

    # Parity mismatch (missing agent in design)
    invalid_design = json.loads(json.dumps(sample_valid_design))
    invalid_design["agents"].pop()
    val_inv = validate_design_json(invalid_design, sample_plan)
    assert val_inv["valid"] is False
    assert any("Architecture mismatch" in err or "Agent ID mismatch" in err for err in val_inv["errors"])


def test_8_design_file_creation(temp_project_dir, sample_plan, sample_valid_design):
    """Test 8 — Verify docs/design.json is created at target location."""
    write_plan_json(temp_project_dir, sample_plan)
    agent = DesignerAgent()

    result = agent.generate_design(
        project_path=temp_project_dir,
        override_llm_response=json.dumps(sample_valid_design),
    )

    expected_file = os.path.join(temp_project_dir, "docs", "design.json")
    assert os.path.isfile(expected_file)
    assert result["file_path"] == expected_file

    with open(expected_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["project"]["name"] == "ai_customer_support"


def test_9_invalid_plan_handling(temp_project_dir):
    """Test 9 — Provide an invalid plan and verify Designer Agent refuses to proceed."""
    # Write invalid plan (missing project property)
    invalid_plan_file = os.path.join(temp_project_dir, "docs", "plan.json")
    os.makedirs(os.path.dirname(invalid_plan_file), exist_ok=True)
    with open(invalid_plan_file, "w", encoding="utf-8") as f:
        json.dump({"agents": []}, f)

    agent = DesignerAgent()
    result = agent.generate_design(project_path=temp_project_dir)

    assert result["status"] == "failed"
    assert result["stage"] == "design"
    assert result["ready_for_coding"] is False
    assert len(result["errors"]) > 0


def test_10_backend_docs_path_support(temp_project_dir, sample_plan, sample_valid_design):
    """Test 10 — Support reading plan.json and writing design.json under custom backend docs path."""
    backend_docs_dir = os.path.join(temp_project_dir, "backend", "docs")
    plan_file = os.path.join(backend_docs_dir, "plan.json")
    os.makedirs(backend_docs_dir, exist_ok=True)
    
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(sample_plan, f)

    agent = DesignerAgent()
    result = agent.generate_design(
        project_path=plan_file,
        override_llm_response=json.dumps(sample_valid_design),
    )

    assert result["status"] == "success"
    expected_design_file = os.path.join(backend_docs_dir, "design.json")
    assert os.path.isfile(expected_design_file)
