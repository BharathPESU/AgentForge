"""GitHub REST API Service for AgentForge GitHub Agent."""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


def get_github_token() -> Optional[str]:
    """Retrieve GitHub token from environment without echoing or storing it."""
    return (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("github_token")
        or os.getenv("GH_TOKEN")
    )


class GitHubService:
    """Service wrapper for interacting with GitHub REST API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or get_github_token()
        self.base_url = "https://api.github.com"

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise ValueError("GitHub API token is missing in environment (GITHUB_TOKEN/github_token).")
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AgentForge-GitHubAgent",
            "Content-Type": "application/json",
        }

    def get_authenticated_user(self) -> Dict[str, Any]:
        """Fetch details of authenticated user.
        
        Returns:
            Dict containing user login, id, etc.
        """
        url = f"{self.base_url}/user"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"status": "success", "login": data.get("login"), "data": data}
        except urllib.error.HTTPError as e:
            return {"status": "error", "code": e.code, "message": f"HTTP Error {e.code}: {e.reason}"}
        except Exception as e:
            return {"status": "error", "code": 500, "message": str(e)}

    def check_repository_exists(self, owner: str, name: str) -> Dict[str, Any]:
        """Check if a repository already exists for the owner.
        
        Args:
            owner: GitHub username or organization name.
            name: Repository name.
            
        Returns:
            Dict with 'exists' (bool) and details.
        """
        url = f"{self.base_url}/repos/{owner}/{name}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"exists": True, "data": data}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"exists": False}
            return {"exists": False, "error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def create_repository(
        self, name: str, description: str = "", private: bool = True
    ) -> Dict[str, Any]:
        """Create a new GitHub repository for the authenticated user.
        
        Args:
            name: Repository name (e.g. 'ai-customer-support').
            description: Concise project description.
            private: True for private repository, False for public.
            
        Returns:
            Dict with 'status', 'url', 'owner', 'name', etc.
        """
        user_res = self.get_authenticated_user()
        if user_res.get("status") != "success":
            return {
                "status": "error",
                "code": user_res.get("code", 401),
                "message": f"Authentication failed: {user_res.get('message')}",
            }

        owner = user_res["login"]

        # Check existence before creating
        exists_check = self.check_repository_exists(owner, name)
        if exists_check.get("exists"):
            return {
                "status": "exists",
                "code": 409,
                "message": f"Repository '{owner}/{name}' already exists on GitHub.",
                "owner": owner,
                "name": name,
                "html_url": f"https://github.com/{owner}/{name}",
            }

        url = f"{self.base_url}/user/repos"
        payload = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": False,
        }

        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "success",
                    "owner": owner,
                    "name": data.get("name"),
                    "full_name": data.get("full_name"),
                    "html_url": data.get("html_url"),
                    "clone_url": data.get("clone_url"),
                    "ssh_url": data.get("ssh_url"),
                    "private": data.get("private"),
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if hasattr(e, "read") else ""
            return {
                "status": "error",
                "code": e.code,
                "message": f"GitHub API error {e.code}: {e.reason}. Detail: {err_body}",
            }
        except Exception as e:
            return {"status": "error", "code": 500, "message": str(e)}
