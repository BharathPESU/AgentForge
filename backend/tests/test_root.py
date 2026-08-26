"""Tests for AgentForge Master Root Orchestrator Agent."""

import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from backend.agents.architect_agent import ArchitectAgent
from backend.agents.coder_agent import CoderAgent
from backend.agents.deployer_agent import DeployerAgent
from backend.agents.designer_agent import DesignerAgent
from backend.agents.github_agent import GitHubAgent
from backend.agents.root_agent import RootAgent, run_pipeline
from backend.agents.tester_agent import TesterAgent


@pytest.fixture
def temp_project_dir():
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
            }
        ],
        "wiring": [],
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
                "handoff": {"upstream": [], "downstream": []},
            }
        ],
        "wiring": [],
    }


def test_1_full_pipeline_success(temp_project_dir, sample_plan, sample_design):
    """Test 1 — Master Root Agent executes full 6-agent pipeline successfully."""
    mock_architect = MagicMock(spec=ArchitectAgent)
    mock_architect.generate_plan.return_value = {
        "status": "success",
        "plan": sample_plan,
        "file_path": os.path.join(temp_project_dir, "docs", "plan.json"),
    }

    mock_designer = MagicMock(spec=DesignerAgent)
    mock_designer.generate_design.return_value = {
        "status": "success",
        "design": sample_design,
        "file_path": os.path.join(temp_project_dir, "docs", "design.json"),
    }

    mock_coder = MagicMock(spec=CoderAgent)
    mock_coder.generate_code.return_value = {
        "status": "success",
        "agents_updated": ["agent1"],
        "files_modified": ["agent.py"],
    }

    mock_tester = MagicMock(spec=TesterAgent)
    mock_tester.validate_project.return_value = {
        "status": "passed",
        "summary": {"tests_run": 5, "tests_passed": 5, "tests_failed": 0},
    }

    mock_github = MagicMock(spec=GitHubAgent)
    mock_github.publish_repository.return_value = {
        "status": "success",
        "repository": {"url": "https://github.com/testuser/ai-customer-support"},
    }

    mock_deployer = MagicMock(spec=DeployerAgent)
    mock_deployer.deploy_project.return_value = {
        "status": "success",
        "github": {"repository_url": "https://github.com/testuser/ai-customer-support"},
        "vercel": {"deployment_url": "https://ai-customer-support.vercel.app"},
    }

    root = RootAgent(
        architect_agent=mock_architect,
        designer_agent=mock_designer,
        coder_agent=mock_coder,
        tester_agent=mock_tester,
        github_agent=mock_github,
        deployer_agent=mock_deployer,
    )

    res = root.run_pipeline(
        user_idea="Build an AI customer support bot",
        project_path=temp_project_dir,
        gemini_api_key="mock_gemini_key",
    )

    assert res["status"] == "success"
    assert res["github_url"] == "https://github.com/testuser/ai-customer-support"
    assert res["vercel_url"] == "https://ai-customer-support.vercel.app"
    assert "Agent system deployed successfully" in res["summary"]
    assert len(res["stages_completed"]) == 6


def test_2_architect_failure(temp_project_dir):
    """Test 2 — Pipeline halts if Architect Agent fails."""
    mock_architect = MagicMock(spec=ArchitectAgent)
    mock_architect.generate_plan.return_value = {
        "status": "failed",
        "errors": ["Failed to extract valid JSON plan"],
    }

    root = RootAgent(architect_agent=mock_architect)
    res = root.run_pipeline("broken idea", project_path=temp_project_dir)

    assert res["status"] == "failed"
    assert res["failed_stage"] == "architecture"


def test_3_designer_failure(temp_project_dir, sample_plan):
    """Test 3 — Pipeline halts if Designer Agent fails."""
    mock_architect = MagicMock(spec=ArchitectAgent)
    mock_architect.generate_plan.return_value = {
        "status": "success",
        "plan": sample_plan,
    }

    mock_designer = MagicMock(spec=DesignerAgent)
    mock_designer.generate_design.return_value = {
        "status": "failed",
        "errors": ["Schema validation error in design"],
    }

    root = RootAgent(architect_agent=mock_architect, designer_agent=mock_designer)
    res = root.run_pipeline("test idea", project_path=temp_project_dir)

    assert res["status"] == "failed"
    assert res["failed_stage"] == "design"


def test_4_coder_failure(temp_project_dir, sample_plan, sample_design):
    """Test 4 — Pipeline halts if Coder Agent fails."""
    mock_architect = MagicMock(spec=ArchitectAgent)
    mock_architect.generate_plan.return_value = {"status": "success", "plan": sample_plan}

    mock_designer = MagicMock(spec=DesignerAgent)
    mock_designer.generate_design.return_value = {"status": "success", "design": sample_design}

    mock_coder = MagicMock(spec=CoderAgent)
    mock_coder.generate_code.return_value = {"status": "failed", "errors": ["Template missing"]}

    root = RootAgent(
        architect_agent=mock_architect,
        designer_agent=mock_designer,
        coder_agent=mock_coder,
    )
    res = root.run_pipeline("test idea", project_path=temp_project_dir)

    assert res["status"] == "failed"
    assert res["failed_stage"] == "coding"


def test_5_tester_failure_with_retry(temp_project_dir, sample_plan, sample_design):
    """Test 5 — Tester fails first time, Coder retries code generation, Tester passes on 2nd attempt."""
    mock_architect = MagicMock(spec=ArchitectAgent)
    mock_architect.generate_plan.return_value = {"status": "success", "plan": sample_plan}

    mock_designer = MagicMock(spec=DesignerAgent)
    mock_designer.generate_design.return_value = {"status": "success", "design": sample_design}

    mock_coder = MagicMock(spec=CoderAgent)
    mock_coder.generate_code.return_value = {"status": "success"}

    mock_tester = MagicMock(spec=TesterAgent)
    # First validation returns failed, second returns passed
    mock_tester.validate_project.side_effect = [
        {"status": "failed", "failures": [{"message": "syntax error"}]},
        {"status": "passed", "summary": {"tests_run": 5, "tests_passed": 5, "tests_failed": 0}},
    ]

    mock_github = MagicMock(spec=GitHubAgent)
    mock_github.publish_repository.return_value = {
        "status": "success",
        "repository": {"url": "https://github.com/testuser/ai-customer-support"},
    }

    mock_deployer = MagicMock(spec=DeployerAgent)
    mock_deployer.deploy_project.return_value = {
        "status": "success",
        "github": {"repository_url": "https://github.com/testuser/ai-customer-support"},
        "vercel": {"deployment_url": "https://ai-customer-support.vercel.app"},
    }

    root = RootAgent(
        architect_agent=mock_architect,
        designer_agent=mock_designer,
        coder_agent=mock_coder,
        tester_agent=mock_tester,
        github_agent=mock_github,
        deployer_agent=mock_deployer,
    )

    res = root.run_pipeline("test idea", project_path=temp_project_dir)

    assert res["status"] == "success"
    assert res["retries_performed"] == 1
    assert mock_coder.generate_code.call_count == 2


def test_6_github_failure(temp_project_dir, sample_plan, sample_design):
    """Test 6 — Pipeline halts if GitHub Agent fails."""
    mock_architect = MagicMock(spec=ArchitectAgent)
    mock_architect.generate_plan.return_value = {"status": "success", "plan": sample_plan}

    mock_designer = MagicMock(spec=DesignerAgent)
    mock_designer.generate_design.return_value = {"status": "success", "design": sample_design}

    mock_coder = MagicMock(spec=CoderAgent)
    mock_coder.generate_code.return_value = {"status": "success"}

    mock_tester = MagicMock(spec=TesterAgent)
    mock_tester.validate_project.return_value = {"status": "passed"}

    mock_github = MagicMock(spec=GitHubAgent)
    mock_github.publish_repository.return_value = {"status": "failed", "message": "Auth error"}

    root = RootAgent(
        architect_agent=mock_architect,
        designer_agent=mock_designer,
        coder_agent=mock_coder,
        tester_agent=mock_tester,
        github_agent=mock_github,
    )

    res = root.run_pipeline("test idea", project_path=temp_project_dir)

    assert res["status"] == "failed"
    assert res["failed_stage"] == "github"
