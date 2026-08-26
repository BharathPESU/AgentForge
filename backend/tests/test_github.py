"""Tests for AgentForge GitHub Agent and supporting tools."""

import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from backend.agents.coder_agent import CoderAgent
from backend.agents.github_agent import GitHubAgent, format_repo_name
from backend.agents.tester_agent import TesterAgent
from backend.services.github_service import GitHubService
from backend.tools.coder_tools import write_file
from backend.tools.designer_tools import write_design_json
from backend.tools.file_tools import write_plan_json
from backend.tools.github_tools import (
    add_files,
    check_git_status,
    commit_changes,
    initialize_git,
    scan_project_secrets,
    set_remote,
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


def test_1_requires_passing_test_result(temp_project_dir):
    """Test 1 — Fails/blocks if test_result.json is missing or status != 'passed'."""
    agent = GitHubAgent()
    res = agent.publish_repository(project_path=temp_project_dir)
    assert res["status"] == "blocked"
    assert res["next_action"]["agent"] == "tester_agent"
    assert res["reason"] == "testing_not_passed"


def test_2_repository_name_generation():
    """Test 2 — Converts plan.json project name into valid GitHub repo name."""
    assert format_repo_name("ai_customer_support") == "ai-customer-support"
    assert format_repo_name("My Great Agent App! 100") == "my-great-agent-app-100"
    assert format_repo_name("---test---") == "test"


@patch("backend.tools.github_tools.get_github_token", return_value="mock_token_123")
@patch("backend.agents.github_agent.get_github_token", return_value="mock_token_123")
@patch.object(GitHubService, "create_repository")
def test_3_repository_already_exists(mock_create, mock_ag_token, mock_tool_token, temp_project_dir, sample_plan, sample_design):
    """Test 3 — Blocks/fails if repository already exists on GitHub."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    tester = TesterAgent()
    tester.validate_project(project_path=temp_project_dir)

    mock_create.return_value = {
        "status": "exists",
        "owner": "testuser",
        "name": "ai-customer-support",
        "message": "Repository already exists",
    }

    agent = GitHubAgent()
    res = agent.publish_repository(project_path=temp_project_dir)
    assert res["status"] == "failed"
    assert res["reason"] == "repository_already_exists"


@patch("backend.tools.github_tools.get_github_token", return_value="mock_token_123")
@patch("backend.agents.github_agent.get_github_token", return_value="mock_token_123")
@patch.object(GitHubService, "create_repository")
@patch("backend.tools.github_tools.push_repository")
def test_4_github_repository_creation(mock_push, mock_create, mock_ag_token, mock_tool_token, temp_project_dir, sample_plan, sample_design):
    """Test 4 — Mocks GitHub API call to create repository."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    tester = TesterAgent()
    tester.validate_project(project_path=temp_project_dir)

    mock_create.return_value = {
        "status": "success",
        "owner": "testuser",
        "name": "ai-customer-support",
        "html_url": "https://github.com/testuser/ai-customer-support",
        "clone_url": "https://github.com/testuser/ai-customer-support.git",
        "private": True,
    }
    mock_push.return_value = {"status": "success", "branch": "main"}

    agent = GitHubAgent()
    res = agent.publish_repository(project_path=temp_project_dir)
    assert res["status"] == "success"
    assert res["repository"]["name"] == "ai-customer-support"
    assert res["repository"]["owner"] == "testuser"
    assert res["next_action"]["agent"] == "deployer_agent"


def test_5_git_initialization(temp_project_dir):
    """Test 5 — Initializes local Git repo in project directory."""
    res = initialize_git(temp_project_dir)
    assert res["status"] == "success"
    assert os.path.isdir(os.path.join(temp_project_dir, ".git"))

    # Second run reuses existing
    res2 = initialize_git(temp_project_dir)
    assert res2["reused"] is True


def test_6_commit(temp_project_dir):
    """Test 6 — Stages files and creates clean commit."""
    initialize_git(temp_project_dir)
    sample_file = os.path.join(temp_project_dir, "README.md")
    write_file(sample_file, "# Test Repo\n")
    
    # Add gitignore ignoring .env
    write_file(os.path.join(temp_project_dir, ".gitignore"), ".env\n")

    add_res = add_files(temp_project_dir)
    assert add_res["status"] == "success"

    commit_res = commit_changes(temp_project_dir, message="initial commit")
    assert commit_res["status"] == "success"
    assert commit_res["sha"] != "head"


def test_7_remote_configuration(temp_project_dir):
    """Test 7 — Configures remote origin URL without credentials in stored URL."""
    initialize_git(temp_project_dir)
    res = set_remote(temp_project_dir, "https://github.com/testuser/my-repo.git")
    assert res["status"] == "success"
    assert res["remote_url"] == "https://github.com/testuser/my-repo.git"


def test_8_secret_detection(temp_project_dir):
    """Test 8 — Halts publish if unignored .env or hardcoded secret is detected."""
    # Write .env without .gitignore
    write_file(os.path.join(temp_project_dir, ".env"), "GEMINI_API_KEY=AIzaSy123456789012345678901234567890123\n")

    sec_res = scan_project_secrets(temp_project_dir)
    assert sec_res["safe"] is False
    assert sec_res["reason"] == "unignored_env_file"


@patch("backend.tools.github_tools.get_github_token", return_value="mock_token_123")
@patch("backend.agents.github_agent.get_github_token", return_value="mock_token_123")
def test_9_github_result_generation(mock_ag_token, mock_tool_token, temp_project_dir, sample_plan, sample_design):
    """Test 9 — Writes valid github_result.json handoff payload."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    tester = TesterAgent()
    tester.validate_project(project_path=temp_project_dir)

    with patch.object(GitHubService, "create_repository") as mock_create, patch("backend.tools.github_tools.push_repository") as mock_push:
        mock_create.return_value = {
            "status": "success",
            "owner": "testuser",
            "name": "ai-customer-support",
            "html_url": "https://github.com/testuser/ai-customer-support",
            "clone_url": "https://github.com/testuser/ai-customer-support.git",
            "private": True,
        }
        mock_push.return_value = {"status": "success", "branch": "main"}

        agent = GitHubAgent()
        res = agent.publish_repository(project_path=temp_project_dir)

        result_file = os.path.join(temp_project_dir, "docs", "github_result.json")
        assert os.path.isfile(result_file)
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "success"
        assert data["next_action"]["agent"] == "deployer_agent"


