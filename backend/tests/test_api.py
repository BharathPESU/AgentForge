"""Unit tests for AgentForge FastAPI Backend API routes and endpoints."""

import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test GET / returns API metadata and online status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "AgentForge Backend API"
    assert "documentation" in data
    assert "health_check" in data


def test_health_endpoint():
    """Test GET /api/health returns healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "AgentForge Backend API"
    assert "api_key_configured" in data


def test_cors_middleware():
    """Test CORS headers are returned for cross-origin request from React frontend."""
    headers = {"Origin": "http://localhost:5173"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ["*", "http://localhost:5173"]


def test_list_projects_endpoint():
    """Test GET /api/projects lists generated projects."""
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert "projects" in data
    assert "count" in data
    assert isinstance(data["projects"], list)


def test_get_project_details_not_found():
    """Test GET /api/projects/{invalid_name} returns 404."""
    response = client.get("/api/projects/non_existent_project_99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_project_details_existing():
    """Test GET /api/projects/study_assistant returns project details."""
    response = client.get("/api/projects/study_assistant")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "study_assistant"
    assert "status" in data


def test_get_project_agents():
    """Test GET /api/projects/study_assistant/agents returns agent list."""
    response = client.get("/api/projects/study_assistant/agents")
    assert response.status_code == 200
    agents = response.json()
    assert isinstance(agents, list)
    assert len(agents) >= 1


def test_get_project_flow():
    """Test GET /api/projects/study_assistant/flow returns nodes and edges."""
    response = client.get("/api/projects/study_assistant/flow")
    assert response.status_code == 200
    flow = response.json()
    assert "nodes" in flow
    assert "edges" in flow


def test_get_project_files():
    """Test GET /api/projects/study_assistant/files returns file tree."""
    response = client.get("/api/projects/study_assistant/files")
    assert response.status_code == 200
    files = response.json()
    assert isinstance(files, list)


def test_get_project_execution():
    """Test GET /api/projects/study_assistant/execution returns execution state."""
    response = client.get("/api/projects/study_assistant/execution")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "stages" in data


def test_get_project_logs():
    """Test GET /api/projects/study_assistant/execution/logs returns log entries."""
    response = client.get("/api/projects/study_assistant/execution/logs")
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)


def test_get_project_github_and_deployment():
    """Test GET /api/projects/study_assistant/github and deployment endpoints."""
    res_gh = client.get("/api/projects/study_assistant/github")
    assert res_gh.status_code == 200
    assert "status" in res_gh.json()

    res_dep = client.get("/api/projects/study_assistant/deployment")
    assert res_dep.status_code == 200
    assert "vercelStatus" in res_dep.json()


def test_pipeline_run_validation_error():
    """Test POST /api/pipeline/run returns 422 if user_idea is too short."""
    payload = {"user_idea": "hi"}
    response = client.post("/api/pipeline/run", json=payload)
    assert response.status_code == 422


@patch("backend.api.routes.RootAgent")
def test_pipeline_run_success(mock_root_cls):
    """Test POST /api/pipeline/run invokes RootAgent.run_pipeline."""
    mock_instance = MagicMock()
    mock_instance.run_pipeline.return_value = {
        "status": "success",
        "github_url": "https://github.com/test/repo",
        "vercel_url": "https://test.vercel.app",
        "summary": "Agent deployed successfully.",
        "duration_seconds": 12.5,
        "stages_completed": ["architecture", "design", "coding", "testing", "github", "deployment"],
    }
    mock_root_cls.return_value = mock_instance

    payload = {
        "user_idea": "Build a weather forecast agent with search capabilities.",
        "project_name": "weather_agent"
    }
    response = client.post("/api/pipeline/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["github_url"] == "https://github.com/test/repo"
    assert data["vercel_url"] == "https://test.vercel.app"


@patch("backend.api.routes.ArchitectAgent")
def test_architect_stage_endpoint(mock_architect_cls):
    """Test POST /api/agents/architect triggers ArchitectAgent."""
    mock_instance = MagicMock()
    mock_instance.generate_plan.return_value = {"status": "success", "plan": {"title": "Test Plan"}}
    mock_architect_cls.return_value = mock_instance

    payload = {"user_idea": "Build a doc summarizer", "project_path": "generated/test_doc"}
    response = client.post("/api/agents/architect", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("backend.api.routes.DesignerAgent")
def test_designer_stage_endpoint(mock_designer_cls):
    """Test POST /api/agents/designer triggers DesignerAgent."""
    mock_instance = MagicMock()
    mock_instance.generate_design.return_value = {"status": "success", "design": {"title": "Test Design"}}
    mock_designer_cls.return_value = mock_instance

    payload = {"project_path": "generated/test_doc"}
    response = client.post("/api/agents/designer", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("backend.api.routes.CoderAgent")
def test_coder_stage_endpoint(mock_coder_cls):
    """Test POST /api/agents/coder triggers CoderAgent."""
    mock_instance = MagicMock()
    mock_instance.generate_code.return_value = {"status": "success", "files_generated": 5}
    mock_coder_cls.return_value = mock_instance

    payload = {"project_path": "generated/test_doc"}
    response = client.post("/api/agents/coder", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("backend.api.routes.TesterAgent")
def test_tester_stage_endpoint(mock_tester_cls):
    """Test POST /api/agents/tester triggers TesterAgent."""
    mock_instance = MagicMock()
    mock_instance.validate_project.return_value = {"status": "passed", "checks": []}
    mock_tester_cls.return_value = mock_instance

    payload = {"project_path": "generated/test_doc"}
    response = client.post("/api/agents/tester", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "passed"


@patch("backend.api.routes.GitHubAgent")
def test_github_stage_endpoint(mock_github_cls):
    """Test POST /api/agents/github triggers GitHubAgent."""
    mock_instance = MagicMock()
    mock_instance.publish_repository.return_value = {"status": "success", "repository_url": "https://github.com/user/repo"}
    mock_github_cls.return_value = mock_instance

    payload = {"project_path": "generated/test_doc"}
    response = client.post("/api/agents/github", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("backend.api.routes.DeployerAgent")
def test_deployer_stage_endpoint(mock_deployer_cls):
    """Test POST /api/agents/deployer triggers DeployerAgent."""
    mock_instance = MagicMock()
    mock_instance.deploy_project.return_value = {"status": "success", "deployment_url": "https://test.vercel.app"}
    mock_deployer_cls.return_value = mock_instance

    payload = {"project_path": "generated/test_doc", "gemini_api_key": "test-key"}
    response = client.post("/api/agents/deployer", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
