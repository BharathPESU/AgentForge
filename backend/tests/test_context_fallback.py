"""Fallback integration tests for AgentForge when AGENT_CONTEXT_ENABLED=false."""

import os
import pytest
from backend.agents.root_agent import RootAgent
from backend.services.context_service import is_context_enabled


def test_context_disabled_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_CONTEXT_ENABLED", "false")
    assert is_context_enabled() is False

    project_dir = os.path.join(tmp_path, "fallback_proj")
    os.makedirs(project_dir, exist_ok=True)

    mock_plan = {
        "project": {"name": "fallback_proj", "description": "Fallback test project", "goal": "Testing fallback"},
        "assumptions": ["Context is disabled"],
        "agents": [
            {
                "id": "agent1",
                "name": "mock_agent",
                "description": "Mock agent for testing",
                "responsibility": "Handle tasks",
                "input": "input",
                "output": "output",
                "is_root": True,
                "tools_required": [],
            }
        ],
        "wiring": [],
    }

    mock_design = {
        "project": {"name": "fallback_proj", "description": "Fallback test project"},
        "agents": [
            {
                "id": "agent1",
                "name": "mock_agent",
                "description": "Mock agent for testing",
                "responsibility": "Handle tasks",
                "model": {"provider": "google", "model_name": "gemini-3.5-flash", "temperature": 0.2},
                "system_prompt": "Prompt",
                "inputs": [],
                "outputs": [],
                "tools": [],
                "constraints": [],
                "error_handling": [],
                "handoff": {"upstream": [], "downstream": []},
            }
        ],
        "wiring": [],
    }

    orchestrator = RootAgent()
    # Mock lower stages to avoid external API calls
    monkeypatch.setattr(orchestrator.coder, "generate_code", lambda project_path, **kwargs: {"status": "success"})
    monkeypatch.setattr(orchestrator.tester, "validate_project", lambda project_path, **kwargs: {"status": "passed"})
    monkeypatch.setattr(orchestrator.github, "publish_repository", lambda project_path, **kwargs: {"status": "success", "repository_url": "https://github.com/mock/repo"})
    monkeypatch.setattr(orchestrator.deployer, "deploy_project", lambda project_path, **kwargs: {
        "status": "success",
        "github": {"repository_url": "https://github.com/mock/repo"},
        "vercel": {"deployment_url": "https://mock.vercel.app"},
    })

    res = orchestrator.run_pipeline(
        user_idea="Test context fallback mode",
        project_path=project_dir,
        override_architect_plan=mock_plan,
        override_designer_design=mock_design,
    )

    assert res["status"] == "success"
    assert res["vercel_url"] == "https://mock.vercel.app"
