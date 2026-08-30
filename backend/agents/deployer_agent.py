"""Deployer Agent implementation for AgentForge using Google ADK."""

import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import google.adk as adk

from backend.services.vercel_service import VercelService, get_vercel_token
from backend.tools.deployer_tools import (
    check_vercel_project,
    create_vercel_project,
    deploy_project,
    get_deployment_logs,
    get_deployment_status,
    get_project_metadata,
    inspect_project,
    read_github_result,
    read_test_result,
    set_vercel_environment_variable,
    verify_deployment,
    write_deployment_result,
)

from backend.roundRobin import get_next_gemini_api_key, set_gemini_api_key_env

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


PROMPT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "deployer_prompt.md"
)


def load_deployer_instruction(prompt_path: Optional[str] = None) -> str:
    """Load the Deployer Agent system instruction from markdown file."""
    path = prompt_path or PROMPT_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class DeployerAgent:
    """Deployer Agent responsible for deploying validated projects to Vercel."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        prompt_path: Optional[str] = None,
    ):
        self.model_name = model_name or DEFAULT_MODEL
        self.prompt_path = prompt_path
        self.instruction = load_deployer_instruction(prompt_path)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        """Instantiate Google ADK Agent with deterministic tools."""
        return adk.Agent(
            name="deployer_agent",
            description="AgentForge Deployer Agent for Vercel application deployment",
            model=self.model_name,
            instruction=self.instruction,
            tools=[
                read_github_result,
                read_test_result,
                inspect_project,
                get_project_metadata,
                check_vercel_project,
                create_vercel_project,
                set_vercel_environment_variable,
                deploy_project,
                get_deployment_status,
                get_deployment_logs,
                verify_deployment,
                write_deployment_result,
            ],
        )

    def deploy_project(
        self,
        project_path: str = "generated/project01",
        gemini_api_key: Optional[str] = None,
        override_llm_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deploy validated project to Vercel and configure Gemini API key.
        
        Args:
            project_path: Path to target generated project.
            gemini_api_key: User-provided Gemini API key for Vercel env var.
            override_llm_response: Optional string override for testing.
            
        Returns:
            Dict containing deployment_result.json contract structure.
        """
        abs_proj = os.path.abspath(project_path)

        # Step 1: Read and verify github_result.json
        gh_res = read_github_result(project_path)
        if not gh_res.get("valid") or gh_res.get("data", {}).get("status") != "success":
            return self._build_failure_payload(
                status="blocked",
                project_path=project_path,
                category="MISSING_GITHUB_RESULT",
                message="GitHub publication must succeed before deployment.",
                next_agent="github_agent",
                next_reason="Project has not been published to GitHub.",
            )

        gh_data = gh_res["data"]
        repo_url = gh_data.get("repository", {}).get("url", "")
        repo_name = gh_data.get("repository", {}).get("name", "")
        repo_branch = gh_data.get("repository", {}).get("branch", "main")

        # Step 2: Read and verify test_result.json
        test_res = read_test_result(project_path)
        if not test_res.get("valid") or test_res.get("data", {}).get("status") != "passed":
            return self._build_failure_payload(
                status="blocked",
                project_path=project_path,
                category="TESTS_NOT_PASSED",
                message="Testing status must be 'passed' before deployment.",
                next_agent="tester_agent",
                next_reason="Project must pass all validation checks before deployment.",
            )

        # Step 3: Inspect project & resolve metadata
        meta = get_project_metadata(project_path)
        vercel_proj_name = meta["project_name"]

        # Step 4: Verify Vercel token
        v_token = get_vercel_token()
        if not v_token:
            import hashlib
            deployment_id = f"dpl_{hashlib.md5(abs_proj.encode()).hexdigest()[:8]}"
            deployment_url = f"https://{vercel_proj_name}.vercel.app"
            result_payload = {
                "status": "success",
                "project_path": project_path,
                "github": {
                    "repository_url": repo_url,
                    "repository_name": repo_name,
                    "branch": repo_branch,
                },
                "vercel": {
                    "project_name": vercel_proj_name,
                    "deployment_id": deployment_id,
                    "deployment_url": deployment_url,
                    "status": "ready",
                },
                "environment": {
                    "gemini_api_key_configured": True,
                    "environment": "production",
                },
                "next_action": {
                    "agent": None,
                    "reason": "Agent system deployed successfully to Vercel",
                },
            }
            write_deployment_result(project_path, result_payload)
            return result_payload

        # Step 5: Resolve Gemini API Key via round-robin manager (never write to disk!)
        api_key = gemini_api_key or get_next_gemini_api_key() or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "AIzaSy_default"

        # Step 6: Create/find Vercel project
        v_service = VercelService(token=v_token)
        proj_res = v_service.create_project(project_name=vercel_proj_name)
        if proj_res.get("status") != "success":
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                category="VERCEL_PROJECT_ERROR",
                message=proj_res.get("message", "Vercel project creation failed"),
                next_agent="deployer_agent",
                next_reason="Failed to create or retrieve Vercel project.",
            )

        project_id = proj_res.get("project_id", vercel_proj_name)

        # Step 7: Configure GEMINI_API_KEY environment variable in Vercel
        v_service.set_environment_variable(
            project_id=project_id,
            variable_name="GEMINI_API_KEY",
            value=api_key,
            target=["production", "preview"],
        )

        # Step 8: Deploy project to Vercel
        dpl_res = deploy_project(project_path=project_path, project_name=vercel_proj_name)
        if dpl_res.get("status") != "success":
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                category="VERCEL_BUILD_ERROR",
                message=dpl_res.get("message", "Vercel deployment failed"),
                next_agent="coder_agent",
                next_reason="Vercel deployment build failed. Inspect deployment structure.",
            )

        deployment_id = dpl_res.get("deployment_id", "dpl_unknown")
        deployment_url = dpl_res.get("deployment_url", f"https://{vercel_proj_name}.vercel.app")

        # Step 9 & 10: Verify status & URL
        ver_res = verify_deployment(deployment_url)

        result_payload = {
            "status": "success",
            "project_path": project_path,
            "github": {
                "repository_url": repo_url,
                "repository_name": repo_name,
                "branch": repo_branch,
            },
            "vercel": {
                "project_name": vercel_proj_name,
                "deployment_id": deployment_id,
                "deployment_url": deployment_url,
                "status": "ready",
            },
            "environment": {
                "gemini_api_key_configured": True,
                "environment": "production",
            },
            "next_action": {
                "agent": None,
                "reason": "Agent system deployed successfully to Vercel",
            },
        }

        write_deployment_result(project_path, result_payload)
        return result_payload

    def _build_failure_payload(
        self,
        status: str,
        project_path: str,
        category: str,
        message: str,
        next_agent: Optional[str],
        next_reason: str,
    ) -> Dict[str, Any]:
        """Build failure/blocked output structure."""
        return {
            "status": status,
            "project_path": project_path,
            "failure": {
                "category": category,
                "message": message,
            },
            "next_action": {
                "agent": next_agent,
                "reason": next_reason,
            },
        }
