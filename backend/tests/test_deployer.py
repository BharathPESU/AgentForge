"""Tests for AgentForge Deployer Agent and supporting tools."""

import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from backend.agents.coder_agent import CoderAgent
from backend.agents.deployer_agent import DeployerAgent
from backend.agents.github_agent import GitHubAgent
from backend.agents.tester_agent import TesterAgent
from backend.services.github_service import GitHubService
from backend.services.vercel_service import VercelService
from backend.tools.deployer_tools import format_vercel_slug
from backend.tools.designer_tools import write_design_json
from backend.tools.file_tools import write_plan_json


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


def setup_successful_pipeline(temp_project_dir, sample_plan, sample_design):
    """Helper to set up plan, design, code, test, and github results."""
    write_plan_json(temp_project_dir, sample_plan)
    write_design_json(temp_project_dir, sample_design, sample_plan)

    coder = CoderAgent()
    coder.generate_code(project_path=temp_project_dir)

    tester = TesterAgent()
    tester.validate_project(project_path=temp_project_dir)

    with patch("backend.tools.github_tools.get_github_token", return_value="mock_token_123"), \
         patch("backend.agents.github_agent.get_github_token", return_value="mock_token_123"), \
         patch.object(GitHubService, "create_repository") as mock_create, \
         patch("backend.agents.github_agent.push_repository") as mock_push:
        
        mock_create.return_value = {
            "status": "success",
            "owner": "testuser",
            "name": "ai-customer-support",
            "html_url": "https://github.com/testuser/ai-customer-support",
            "clone_url": "https://github.com/testuser/ai-customer-support.git",
            "private": True,
        }
        mock_push.return_value = {"status": "success", "branch": "main"}

        gh_agent = GitHubAgent()
        gh_agent.publish_repository(project_path=temp_project_dir)


def test_1_requires_github_success(temp_project_dir):
    """Test 1 — Fails/blocks if github_result.json is missing or status != 'success'."""
    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="mock_key")
    assert res["status"] == "blocked"
    assert res["failure"]["category"] == "MISSING_GITHUB_RESULT"
    assert res["next_action"]["agent"] == "github_agent"


def test_2_requires_tests_passed(temp_project_dir):
    """Test 2 — Fails/blocks if test_result.json is missing or status != 'passed'."""
    # Write github_result.json manually without test_result.json
    docs_dir = os.path.join(temp_project_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    with open(os.path.join(docs_dir, "github_result.json"), "w") as f:
        json.dump({"status": "success", "repository": {"url": "https://github.com/test/repo"}}, f)

    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="mock_key")
    assert res["status"] == "blocked"
    assert res["failure"]["category"] == "TESTS_NOT_PASSED"
    assert res["next_action"]["agent"] == "tester_agent"


def test_3_reads_project_metadata(temp_project_dir, sample_plan, sample_design):
    """Test 3 — Extracts project name and description from plan.json and github_result.json."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)
    
    with open(os.path.join(temp_project_dir, "docs", "github_result.json")) as f:
        gh_data = json.load(f)
    assert gh_data["repository"]["name"] == "ai-customer-support"


def test_4_project_name_generation():
    """Test 4 — Converts project name into valid Vercel project slug."""
    assert format_vercel_slug("AI Customer Support") == "ai-customer-support"
    assert format_vercel_slug("my_agent_app_100") == "my-agent-app-100"


@patch("backend.agents.deployer_agent.get_vercel_token", return_value="mock_vtoken")
@patch.object(VercelService, "create_project")
@patch.object(VercelService, "set_environment_variable")
@patch("backend.agents.deployer_agent.deploy_project")
def test_5_existing_project_detection(mock_deploy, mock_set_env, mock_create, mock_token, temp_project_dir, sample_plan, sample_design):
    """Test 5 — Reuses existing Vercel project when detected."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)

    mock_create.return_value = {
        "status": "success",
        "reused": True,
        "project_id": "prj_12345",
        "project_name": "ai-customer-support",
    }
    mock_set_env.return_value = {"status": "success", "variable": "GEMINI_API_KEY"}
    mock_deploy.return_value = {"status": "success", "deployment_id": "dpl_123", "deployment_url": "https://ai-customer-support.vercel.app"}

    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="mock_gemini_key")
    assert res["status"] == "success"
    assert res["vercel"]["project_name"] in ("ai-customer-support", "support")


@patch("backend.agents.deployer_agent.get_vercel_token", return_value="mock_vtoken")
@patch.object(VercelService, "create_project")
@patch.object(VercelService, "set_environment_variable")
@patch("backend.agents.deployer_agent.deploy_project")
def test_6_gemini_environment_variable(mock_deploy, mock_set_env, mock_create, mock_token, temp_project_dir, sample_plan, sample_design):
    """Test 6 — Sets GEMINI_API_KEY in Vercel environment without leaking key."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)

    mock_create.return_value = {"status": "success", "project_id": "prj_123", "project_name": "ai-customer-support"}
    mock_set_env.return_value = {"status": "success", "variable": "GEMINI_API_KEY"}
    mock_deploy.return_value = {"status": "success", "deployment_id": "dpl_123", "deployment_url": "https://ai-customer-support.vercel.app"}

    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="secret_gemini_key_123")
    assert res["environment"]["gemini_api_key_configured"] is True
    # Ensure raw key not in res string
    assert "secret_gemini_key_123" not in json.dumps(res)


@patch("backend.agents.deployer_agent.get_vercel_token", return_value="mock_vtoken")
@patch.object(VercelService, "create_project")
@patch.object(VercelService, "set_environment_variable")
@patch("backend.agents.deployer_agent.deploy_project")
def test_7_deployment(mock_deploy, mock_set_env, mock_create, mock_token, temp_project_dir, sample_plan, sample_design):
    """Test 7 — Deploys generated project to Vercel."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)

    mock_create.return_value = {"status": "success", "project_id": "prj_123", "project_name": "ai-customer-support"}
    mock_set_env.return_value = {"status": "success", "variable": "GEMINI_API_KEY"}
    mock_deploy.return_value = {"status": "success", "deployment_id": "dpl_123", "deployment_url": "https://ai-customer-support.vercel.app"}

    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="mock_key")
    assert res["status"] == "success"
    assert res["vercel"]["deployment_id"] == "dpl_123"


@patch("backend.agents.deployer_agent.get_vercel_token", return_value="mock_vtoken")
@patch.object(VercelService, "create_project")
@patch.object(VercelService, "set_environment_variable")
@patch("backend.agents.deployer_agent.deploy_project")
def test_8_deployment_status(mock_deploy, mock_set_env, mock_create, mock_token, temp_project_dir, sample_plan, sample_design):
    """Test 8 — Verifies deployment status is ready."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)

    mock_create.return_value = {"status": "success", "project_id": "prj_123", "project_name": "ai-customer-support"}
    mock_set_env.return_value = {"status": "success", "variable": "GEMINI_API_KEY"}
    mock_deploy.return_value = {"status": "success", "deployment_id": "dpl_123", "deployment_url": "https://ai-customer-support.vercel.app"}

    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="mock_key")
    assert res["vercel"]["status"] == "ready"


@patch("backend.agents.deployer_agent.get_vercel_token", return_value="mock_vtoken")
@patch.object(VercelService, "create_project")
@patch.object(VercelService, "set_environment_variable")
@patch("backend.agents.deployer_agent.deploy_project")
def test_9_deployment_failure(mock_deploy, mock_set_env, mock_create, mock_token, temp_project_dir, sample_plan, sample_design):
    """Test 9 — Handles build/deployment failure and returns categorized error."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)

    mock_create.return_value = {"status": "success", "project_id": "prj_123", "project_name": "ai-customer-support"}
    mock_set_env.return_value = {"status": "success", "variable": "GEMINI_API_KEY"}
    mock_deploy.return_value = {"status": "error", "message": "Vercel build failed"}

    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="mock_key")
    assert res["status"] == "failed"
    assert res["failure"]["category"] == "VERCEL_BUILD_ERROR"
    assert res["next_action"]["agent"] == "coder_agent"


@patch("backend.agents.deployer_agent.get_vercel_token", return_value="mock_vtoken")
@patch.object(VercelService, "create_project")
@patch.object(VercelService, "set_environment_variable")
@patch("backend.agents.deployer_agent.deploy_project")
def test_10_no_secret_in_result(mock_deploy, mock_set_env, mock_create, mock_token, temp_project_dir, sample_plan, sample_design):
    """Test 10 — Verifies deployment_result.json contains no secret tokens."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)

    mock_create.return_value = {"status": "success", "project_id": "prj_123", "project_name": "ai-customer-support"}
    mock_set_env.return_value = {"status": "success", "variable": "GEMINI_API_KEY"}
    mock_deploy.return_value = {"status": "success", "deployment_id": "dpl_123", "deployment_url": "https://ai-customer-support.vercel.app"}

    secret_key = "MY_SUPER_SECRET_GEMINI_KEY_999"
    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key=secret_key)

    result_file = os.path.join(temp_project_dir, "docs", "deployment_result.json")
    assert os.path.isfile(result_file)
    with open(result_file, "r", encoding="utf-8") as f:
        file_content = f.read()

    assert secret_key not in file_content
    assert "mock_vtoken" not in file_content


@patch("backend.agents.deployer_agent.get_vercel_token", return_value="mock_vtoken")
@patch.object(VercelService, "create_project")
@patch.object(VercelService, "set_environment_variable")
@patch("backend.agents.deployer_agent.deploy_project")
def test_11_github_url_in_result(mock_deploy, mock_set_env, mock_create, mock_token, temp_project_dir, sample_plan, sample_design):
    """Test 11 — Includes GitHub repository URL in output."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)

    mock_create.return_value = {"status": "success", "project_id": "prj_123", "project_name": "ai-customer-support"}
    mock_set_env.return_value = {"status": "success", "variable": "GEMINI_API_KEY"}
    mock_deploy.return_value = {"status": "success", "deployment_id": "dpl_123", "deployment_url": "https://ai-customer-support.vercel.app"}

    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="mock_key")
    assert res["github"]["repository_url"] == "https://github.com/testuser/ai-customer-support"


@patch("backend.agents.deployer_agent.get_vercel_token", return_value="mock_vtoken")
@patch.object(VercelService, "create_project")
@patch.object(VercelService, "set_environment_variable")
@patch("backend.agents.deployer_agent.deploy_project")
def test_12_vercel_url_in_result(mock_deploy, mock_set_env, mock_create, mock_token, temp_project_dir, sample_plan, sample_design):
    """Test 12 — Includes Vercel deployment URL in output."""
    setup_successful_pipeline(temp_project_dir, sample_plan, sample_design)

    mock_create.return_value = {"status": "success", "project_id": "prj_123", "project_name": "ai-customer-support"}
    mock_set_env.return_value = {"status": "success", "variable": "GEMINI_API_KEY"}
    mock_deploy.return_value = {"status": "success", "deployment_id": "dpl_123", "deployment_url": "https://ai-customer-support.vercel.app"}

    agent = DeployerAgent()
    res = agent.deploy_project(project_path=temp_project_dir, gemini_api_key="mock_key")
    assert res["vercel"]["deployment_url"] == "https://ai-customer-support.vercel.app"
