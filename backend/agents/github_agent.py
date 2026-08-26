"""GitHub Agent implementation for AgentForge using Google ADK."""

import json
import os
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import google.adk as adk

from backend.services.github_service import GitHubService, get_github_token
from backend.tools.designer_tools import read_plan_json
from backend.tools.github_tools import (
    add_files,
    check_git_status,
    commit_changes,
    create_github_repository,
    get_repository_info,
    initialize_git,
    inspect_project,
    list_directory,
    push_repository,
    read_file,
    scan_project_secrets,
    set_remote,
)

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

PROMPT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "github_prompt.md"
)


def load_github_instruction(prompt_path: Optional[str] = None) -> str:
    """Load the GitHub Agent system instruction from markdown file."""
    path = prompt_path or PROMPT_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def format_repo_name(name: str) -> str:
    """Convert raw project name string into valid GitHub repository slug."""
    if not name:
        return "agentforge-project"
    slug = name.strip().lower()
    slug = slug.replace("_", "-")
    slug = re.sub(r"[^a-z0-9\-]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")



class GitHubAgent:
    """GitHub Agent responsible for publishing approved projects to GitHub."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        prompt_path: Optional[str] = None,
    ):
        self.model_name = model_name or DEFAULT_MODEL
        self.prompt_path = prompt_path
        self.instruction = load_github_instruction(prompt_path)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        """Instantiate Google ADK Agent with deterministic tools."""
        return adk.Agent(
            name="github_agent",
            description="AgentForge GitHub Agent for repository creation and code publication",
            model=self.model_name,
            instruction=self.instruction,
            tools=[
                read_file,
                list_directory,
                inspect_project,
                check_git_status,
                initialize_git,
                create_github_repository,
                add_files,
                commit_changes,
                set_remote,
                push_repository,
                get_repository_info,
                scan_project_secrets,
            ],
        )

    def publish_repository(
        self,
        project_path: str = "generated/project01",
        override_llm_response: Optional[str] = None,
        private: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Publish approved generated project to GitHub.
        
        Args:
            project_path: Path to target generated project.
            override_llm_response: Optional override for testing.
            private: Explicit privacy override (default reads GITHUB_REPOSITORY_PRIVATE env var).
            
        Returns:
            Dict containing github_result.json handoff contract.
        """
        abs_proj = os.path.abspath(project_path)

        # Step 1 & 2: Check test_result.json status
        test_res_file = os.path.join(abs_proj, "docs", "test_result.json")
        if not os.path.isfile(test_res_file):
            return self._build_failure_payload(
                status="blocked",
                project_path=project_path,
                reason="testing_not_passed",
                error_category="TEST_NOT_PASSED",
                message="test_result.json not found. Run Tester Agent before publishing.",
                next_agent="tester_agent",
                next_reason="Testing has not been performed on the generated project.",
            )

        try:
            with open(test_res_file, "r", encoding="utf-8") as f:
                test_result_data = json.load(f)
        except Exception as e:
            return self._build_failure_payload(
                status="blocked",
                project_path=project_path,
                reason="testing_not_passed",
                error_category="TEST_NOT_PASSED",
                message=f"Failed to parse test_result.json: {str(e)}",
                next_agent="tester_agent",
                next_reason="test_result.json is unreadable.",
            )

        if test_result_data.get("status") != "passed":
            return self._build_failure_payload(
                status="blocked",
                project_path=project_path,
                reason="testing_not_passed",
                error_category="TEST_NOT_PASSED",
                message=f"Tester Agent status is '{test_result_data.get('status')}'. Must be 'passed'.",
                next_agent="tester_agent",
                next_reason="Generated project must pass validation before GitHub publication.",
            )

        # Step 3: Read plan.json project metadata
        plan_res = read_plan_json(project_path)
        raw_name = "agentforge_project"
        description = "Multi-agent system built with AgentForge"
        if plan_res.get("valid") and plan_res.get("data"):
            proj_meta = plan_res["data"].get("project", {})
            raw_name = proj_meta.get("name", raw_name)
            description = proj_meta.get("description", description)

        repo_name = format_repo_name(raw_name)

        # Step 4: Secret scan before staging
        sec_res = scan_project_secrets(project_path)
        if not sec_res["safe"]:
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                reason=sec_res["reason"],
                error_category="SECURITY_ERROR",
                message=sec_res["message"],
                next_agent="coder_agent",
                next_reason=f"Security scan failed: {sec_res['message']}",
            )

        # Step 5 & 6: Create GitHub repository via API
        is_private = private if private is not None else os.getenv("GITHUB_REPOSITORY_PRIVATE", "true").lower() == "true"
        
        token = get_github_token()
        if not token:
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                reason="missing_github_token",
                error_category="AUTHENTICATION_ERROR",
                message="GITHUB_TOKEN / github_token environment variable is not configured.",
                next_agent="github_agent",
                next_reason="Configure GITHUB_TOKEN environment variable to proceed.",
            )

        gh_service = GitHubService(token=token)
        repo_res = gh_service.create_repository(name=repo_name, description=description, private=is_private)

        if repo_res.get("status") == "exists":
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                reason="repository_already_exists",
                error_category="REPOSITORY_CONFLICT",
                message=f"Repository '{repo_res.get('owner')}/{repo_name}' already exists on GitHub.",
                next_agent="github_agent",
                next_reason="Repository name conflict on GitHub.",
            )

        if repo_res.get("status") != "success":
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                reason="repo_creation_failed",
                error_category="API_ERROR",
                message=repo_res.get("message", "GitHub repository creation failed"),
                next_agent="github_agent",
                next_reason="GitHub API repository creation request failed.",
            )

        html_url = repo_res["html_url"]
        clone_url = repo_res["clone_url"]
        owner = repo_res["owner"]

        # Step 7: Initialize Git
        init_res = initialize_git(project_path)

        # Step 8: Add files
        add_res = add_files(project_path)
        if add_res.get("status") != "success":
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                reason=add_res.get("reason", "git_add_failed"),
                error_category="GIT_ERROR",
                message=add_res.get("message", "Failed to stage files for commit"),
                next_agent="coder_agent",
                next_reason="Git file staging failed.",
            )

        # Step 9: Commit changes
        commit_res = commit_changes(project_path, message="feat: publish generated agent system")
        sha = commit_res.get("sha", "head")

        # Step 10: Set Remote
        set_remote(project_path, clone_url)

        # Step 11: Push repository
        push_res = push_repository(project_path, branch="main")
        if push_res.get("status") != "success":
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                reason=push_res.get("reason", "push_failed"),
                error_category=push_res.get("error_category", "GIT_PUSH_ERROR"),
                message=push_res.get("message", "Remote push to GitHub failed"),
                next_agent="github_agent",
                next_reason="Retry git push after checking credentials and network.",
            )

        # Step 12: Build Handoff Payload
        result_payload = {
            "status": "success",
            "project_path": project_path,
            "repository": {
                "owner": owner,
                "name": repo_name,
                "url": html_url,
                "branch": "main",
                "private": is_private,
            },
            "commit": {
                "sha": sha,
                "message": "feat: publish generated agent system",
            },
            "next_action": {
                "agent": "deployer_agent",
                "reason": "Repository published successfully to GitHub",
            },
        }

        self._write_github_result(abs_proj, result_payload)
        return result_payload

    def _build_failure_payload(
        self,
        status: str,
        project_path: str,
        reason: str,
        error_category: str,
        message: str,
        next_agent: str,
        next_reason: str,
    ) -> Dict[str, Any]:
        """Build failure/blocked output structure."""
        return {
            "status": status,
            "project_path": project_path,
            "reason": reason,
            "error_category": error_category,
            "message": message,
            "next_action": {
                "agent": next_agent,
                "reason": next_reason,
            },
        }

    def _write_github_result(self, abs_proj: str, payload: Dict[str, Any]):
        """Write github_result.json to project docs/ directory."""
        docs_dir = os.path.join(abs_proj, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        target_path = os.path.join(docs_dir, "github_result.json")
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
