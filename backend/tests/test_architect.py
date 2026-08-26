"""Tests for AgentForge Architect Agent and supporting tools."""

import json
import os
import shutil
import tempfile
import pytest

from backend.agents.architect_agent import ArchitectAgent, extract_json_from_text
from backend.tools.file_tools import (
    read_project_document,
    read_schema,
    validate_plan_json,
    write_plan_json,
)


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for project tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_valid_plan():
    return {
        "project": {
            "name": "ai_research_assistant",
            "description": "Multi-agent research assistant",
            "goal": "Search, summarize, compare, and report on research papers",
        },
        "assumptions": [
            "Paper search is performed through external paper search capability."
        ],
        "agents": [
            {
                "id": "agent1",
                "name": "research_orchestrator",
                "description": "Coordinates the research workflow.",
                "responsibility": "Receive research request and delegate work.",
                "input": ["research_question"],
                "output": ["final_report"],
                "is_root": True,
                "tools_required": [],
            },
            {
                "id": "agent2",
                "name": "paper_search_agent",
                "description": "Finds relevant academic papers.",
                "responsibility": "Search for papers relevant to research question.",
                "input": ["research_question"],
                "output": ["paper_list"],
                "is_root": False,
                "tools_required": ["paper_search"],
            },
            {
                "id": "agent3",
                "name": "paper_analysis_agent",
                "description": "Summarizes and extracts findings.",
                "responsibility": "Analyze retrieved papers.",
                "input": ["paper_list"],
                "output": ["paper_summaries"],
                "is_root": False,
                "tools_required": ["document_reader"],
            },
        ],
        "wiring": [
            {
                "from": "agent1",
                "to": "agent2",
                "condition": "always",
                "input": ["research_question"],
                "output": ["paper_list"],
                "execution": "sequential",
            },
            {
                "from": "agent2",
                "to": "agent3",
                "condition": "papers_found",
                "input": ["paper_list"],
                "output": ["paper_summaries"],
                "execution": "parallel",
            },
        ],
    }


def test_1_basic_architecture_generation(temp_project_dir, sample_valid_plan):
    """Test 1 — Basic architecture generation produces a plan with root agent and wiring."""
    agent = ArchitectAgent()
    mock_llm_output = json.dumps(sample_valid_plan)
    
    result = agent.generate_plan(
        user_idea="Build an AI customer support system.",
        project_path=temp_project_dir,
        override_llm_response=mock_llm_output,
    )

    assert result["status"] == "success"
    plan = result["plan"]
    assert "project" in plan
    assert len(plan["agents"]) >= 1
    
    # Verify root agent
    root_agents = [a for a in plan["agents"] if a.get("is_root") is True]
    assert len(root_agents) == 1
    
    # Verify wiring exists
    assert "wiring" in plan
    assert len(plan["wiring"]) > 0


def test_2_multi_agent_architecture(temp_project_dir, sample_valid_plan):
    """Test 2 — Verify multi-agent decomposition into multiple distinct agents."""
    agent = ArchitectAgent()
    mock_llm_output = json.dumps(sample_valid_plan)
    
    result = agent.generate_plan(
        user_idea="Build a multi-agent research assistant that searches, analyzes, and compares papers.",
        project_path=temp_project_dir,
        override_llm_response=mock_llm_output,
    )

    assert result["status"] == "success"
    agents = result["plan"]["agents"]
    assert len(agents) == 3
    agent_ids = {a["id"] for a in agents}
    assert agent_ids == {"agent1", "agent2", "agent3"}


def test_3_schema_validation(sample_valid_plan):
    """Test 3 — Schema validation passes for valid output and fails for invalid output."""
    # Valid plan passes
    val_valid = validate_plan_json(sample_valid_plan)
    assert val_valid["valid"] is True
    assert len(val_valid["errors"]) == 0

    # Missing required field 'project'
    invalid_plan_1 = sample_valid_plan.copy()
    del invalid_plan_1["project"]
    val_inv_1 = validate_plan_json(invalid_plan_1)
    assert val_inv_1["valid"] is False
    assert any("project" in err for err in val_inv_1["errors"])

    # Invalid agent ID pattern
    invalid_plan_2 = json.loads(json.dumps(sample_valid_plan))
    invalid_plan_2["agents"][0]["id"] = "bad-agent-id!!!"
    val_inv_2 = validate_plan_json(invalid_plan_2)
    assert val_inv_2["valid"] is False
    assert any("pattern" in err.lower() or "id" in err.lower() for err in val_inv_2["errors"])


def test_4_file_creation(temp_project_dir, sample_valid_plan):
    """Test 4 — Verify docs/plan.json is created at target location with valid content."""
    agent = ArchitectAgent()
    mock_llm_output = json.dumps(sample_valid_plan)
    
    result = agent.generate_plan(
        user_idea="Build an AI assistant",
        project_path=temp_project_dir,
        override_llm_response=mock_llm_output,
    )

    expected_file = os.path.join(temp_project_dir, "docs", "plan.json")
    assert os.path.isfile(expected_file)
    assert result["file_path"] == expected_file

    with open(expected_file, "r", encoding="utf-8") as f:
        file_content = json.load(f)

    assert file_content["project"]["name"] == "ai_research_assistant"


def test_5_wiring_consistency(sample_valid_plan):
    """Test 5 — Verify every 'from' and 'to' reference points to a defined agent ID."""
    # Valid wiring passes
    val_res = validate_plan_json(sample_valid_plan)
    assert val_res["valid"] is True

    # Invalid 'to' reference
    invalid_wiring_plan = json.loads(json.dumps(sample_valid_plan))
    invalid_wiring_plan["wiring"][0]["to"] = "non_existent_agent"
    val_inv = validate_plan_json(invalid_wiring_plan)
    assert val_inv["valid"] is False
    assert any("non_existent_agent" in err for err in val_inv["errors"])


def test_6_exactly_one_root_agent(sample_valid_plan):
    """Test 6 — Verify architecture fails validation unless exactly one root agent exists."""
    # 0 root agents
    no_root_plan = json.loads(json.dumps(sample_valid_plan))
    for a in no_root_plan["agents"]:
        a["is_root"] = False
    val_0 = validate_plan_json(no_root_plan)
    assert val_0["valid"] is False
    assert any("Exactly one root agent" in err for err in val_0["errors"])

    # 2 root agents
    two_root_plan = json.loads(json.dumps(sample_valid_plan))
    two_root_plan["agents"][1]["is_root"] = True
    val_2 = validate_plan_json(two_root_plan)
    assert val_2["valid"] is False
    assert any("Exactly one root agent" in err for err in val_2["errors"])


def test_7_no_unnecessary_agents(temp_project_dir):
    """Test 7 — Simple idea yields a reasonably small architecture."""
    simple_plan = {
        "project": {
            "name": "simple_translator",
            "description": "Text translation agent",
            "goal": "Translate user text into targeted language",
        },
        "assumptions": [],
        "agents": [
            {
                "id": "agent1",
                "name": "translator_agent",
                "description": "Translates input text",
                "responsibility": "Receive text and target language and return translation",
                "input": ["text", "target_language"],
                "output": ["translated_text"],
                "is_root": True,
                "tools_required": [],
            }
        ],
        "wiring": [],
    }

    agent = ArchitectAgent()
    result = agent.generate_plan(
        user_idea="Translate text to French",
        project_path=temp_project_dir,
        override_llm_response=json.dumps(simple_plan),
    )

    assert result["status"] == "success"
    agents = result["plan"]["agents"]
    assert len(agents) <= 3


def test_file_tools_security_and_reading():
    """Test security restrictions and helper functions in file_tools."""
    # Test read_schema
    schema = read_schema()
    assert schema["title"] == "AgentForgeArchitecturePlan"

    # Test read_project_document
    doc = read_project_document("README.md")
    assert isinstance(doc, str)

    # Test directory traversal prevention
    with pytest.raises(ValueError, match="Access denied"):
        read_project_document("../../etc/passwd")


def test_extract_json_from_text():
    """Test parsing JSON from various LLM response formats."""
    raw = '{"key": "value"}'
    assert extract_json_from_text(raw) == {"key": "value"}

    markdown = 'Here is your plan:\n```json\n{"key": "value"}\n```\nHope this helps!'
    assert extract_json_from_text(markdown) == {"key": "value"}

    messy = 'Random prefix text {"key": "value"} random suffix text'
    assert extract_json_from_text(messy) == {"key": "value"}
