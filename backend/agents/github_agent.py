"""GitHub Agent implementation for AgentForge using Google ADK."""

import json
import os
import re
import hashlib
import time
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

from backend.roundRobin import set_gemini_api_key_env

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


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


def _slug(text: str, max_len: int = 20) -> str:
    """Sanitise arbitrary text into a valid GitHub slug truncated to max_len."""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:max_len].rstrip("-")


def ai_generate_repo_name(
    project_name: str,
    description: str,
    max_len: int = 20,
) -> str:
    """Ask Gemini to generate a creative, memorable GitHub repository slug.

    The model is instructed to return ONLY the slug (lowercase, hyphens,
    max max_len chars) and nothing else.  Falls back to a formatted version
    of project_name if the API call fails or produces an invalid slug.

    Args:
        project_name: Raw project name from plan.json.
        description: Project description from plan.json.
        max_len: Hard maximum character limit (default 20).

    Returns:
        A valid, AI-generated GitHub repo slug <= max_len characters.
    """
    try:
        from backend.roundRobin import set_gemini_api_key_env
        from google import genai as _genai

        set_gemini_api_key_env()
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("No Gemini API key available")

        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        client = _genai.Client(api_key=api_key)

        prompt = (
            f"Generate a creative, memorable GitHub repository slug for a project called "
            f"'{project_name}' described as: '{description}'.\n\n"
            f"Rules:\n"
            f"- Output ONLY the slug — nothing else, no explanation, no quotes\n"
            f"- Lowercase letters, digits, and hyphens only\n"
            f"- Maximum {max_len} characters\n"
            f"- Must be concise and meaningful\n"
            f"- No leading or trailing hyphens\n"
            f"Examples of good slugs: 'pdf-brain', 'bench-scout', 'ra-core', 'insight-mesh'\n"
        )

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=_genai.types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=32,
            ),
        )
        raw = response.text.strip().split("\n")[0].strip()
        slug = _slug(raw, max_len)
        if slug and len(slug) >= 3:
            return slug
    except Exception:
        pass  # fall through to deterministic fallback

    # Deterministic fallback: shorten the plan name
    return _slug(format_repo_name(project_name), max_len)


def ensure_unique_repo_name(
    gh_service: Any,
    owner: str,
    base_name: str,
    max_attempts: int = 8,
) -> str:
    """Return a repo name that does not yet exist on GitHub.

    If *base_name* is already taken, appends a short 4-hex-char suffix derived
    from the current timestamp.  Tries up to *max_attempts* variants before
    giving up and returning the last candidate (creation may still fail).

    Args:
        gh_service: An authenticated GitHubService instance.
        owner: GitHub username / org.
        base_name: Preferred slug (already validated, ≤ 20 chars).
        max_attempts: How many unique suffixes to try.

    Returns:
        A repo name that was verified as available (or the last attempted name).
    """
    candidate = base_name
    for attempt in range(max_attempts):
        check = gh_service.check_repository_exists(owner, candidate)
        if not check.get("exists"):
            return candidate
        # Generate a short unique suffix from epoch + attempt
        suffix_src = f"{time.time():.0f}{attempt}"
        suffix = hashlib.md5(suffix_src.encode()).hexdigest()[:4]
        # Trim base to leave room for suffix with hyphen
        trimmed = base_name[:19].rstrip("-")
        candidate = f"{trimmed}-{suffix}"
    return candidate



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

        # Step 3b: Use AI to generate a creative, unique ≤20-char repo slug
        ai_name = ai_generate_repo_name(raw_name, description, max_len=20)

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
            initialize_git(project_path)
            add_files(project_path)
            commit_res = commit_changes(project_path, message="feat: publish generated agent system")
            sha = commit_res.get("sha", "head")
            local_repo_name = _slug(format_repo_name(raw_name), 20)
            html_url = f"https://github.com/AgentForge/{local_repo_name}"

            result_payload = {
                "status": "success",
                "project_path": project_path,
                "repository": {
                    "owner": "AgentForge",
                    "name": local_repo_name,
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

        gh_service = GitHubService(token=token)

        # Resolve the authenticated user so we can check for name conflicts
        user_res = gh_service.get_authenticated_user()
        owner_login = user_res.get("login", "") if user_res.get("status") == "success" else ""

        # Auto-resolve naming conflicts: append a short suffix if needed
        repo_name = ensure_unique_repo_name(gh_service, owner_login, ai_name)

        repo_res = gh_service.create_repository(name=repo_name, description=description, private=is_private)

        if repo_res.get("status") not in ("success",):
            return self._build_failure_payload(
                status="failed",
                project_path=project_path,
                reason="repo_creation_failed",
                error_category="API_ERROR",
                message=repo_res.get("message", "GitHub repository creation failed"),
                next_agent="github_agent",
                next_reason="GitHub API repository creation request failed.",
            )

        html_url = repo_res.get("html_url", f"https://github.com/AgentForge/{repo_name}")
        clone_url = repo_res.get("clone_url", "")
        owner = repo_res.get("owner", owner_login or "AgentForge")

        # Step 7: Initialize Git
        init_res = initialize_git(project_path)

        # Step 8: Add files
        add_res = add_files(project_path)

        # Step 9: Commit changes
        commit_res = commit_changes(project_path, message="feat: publish generated agent system")
        sha = commit_res.get("sha", "head")

        # Step 10: Set Remote
        if clone_url:
            set_remote(project_path, clone_url)
            # Step 11: Push repository
            push_res = push_repository(project_path, branch="main")

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
