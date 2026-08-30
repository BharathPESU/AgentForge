"""Vercel REST API Service for AgentForge Deployer Agent."""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


def get_vercel_token() -> Optional[str]:
    """Retrieve Vercel API token from environment without echoing or storing it."""
    return os.getenv("VERCEL_TOKEN") or os.getenv("vercel_token")


class VercelService:
    """Service wrapper for interacting with Vercel REST API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or get_vercel_token()
        self.base_url = "https://api.vercel.com"

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise ValueError("Vercel API token is missing in environment (VERCEL_TOKEN/vercel_token).")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "AgentForge-DeployerAgent",
        }

    def check_project_exists(self, project_name: str) -> Dict[str, Any]:
        """Check if a Vercel project with the given name exists.
        
        Args:
            project_name: Normalized Vercel project name slug.
            
        Returns:
            Dict containing 'exists' (bool), 'project_id', 'name', etc.
        """
        url = f"{self.base_url}/v9/projects/{project_name}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "exists": True,
                    "project_id": data.get("id"),
                    "name": data.get("name"),
                    "data": data,
                }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"exists": False}
            return {"exists": False, "error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def create_project(
        self, project_name: str, framework: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new Vercel project or return existing if already present.
        
        Args:
            project_name: Normalized project slug name.
            framework: Optional framework preset (e.g. 'fastapi' or None).
            
        Returns:
            Dict containing status, project_id, project_name, etc.
        """
        # First check existence
        chk = self.check_project_exists(project_name)
        if chk.get("exists"):
            return {
                "status": "success",
                "reused": True,
                "project_id": chk["project_id"],
                "project_name": chk["name"],
            }

        url = f"{self.base_url}/v9/projects"
        payload: Dict[str, Any] = {
            "name": project_name,
            "ssoProtection": None,
            "passcodeProtection": None,
        }
        if framework:
            payload["framework"] = framework

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "success",
                    "reused": False,
                    "project_id": data.get("id"),
                    "project_name": data.get("name"),
                    "data": data,
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if hasattr(e, "read") else ""
            return {
                "status": "error",
                "code": e.code,
                "message": f"Vercel project creation HTTP {e.code}: {e.reason}. {err_body}",
            }
        except Exception as e:
            return {"status": "error", "code": 500, "message": str(e)}

    def disable_deployment_protection(self, project_name: str) -> Dict[str, Any]:
        """Disable Vercel SSO/Authentication deployment protection for public access.
        
        Args:
            project_name: Name of the Vercel project.
            
        Returns:
            Dict containing status and Vercel API response.
        """
        url = f"{self.base_url}/v9/projects/{project_name}"
        payload = {
            "ssoProtection": None,
            "passcodeProtection": None,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="PATCH")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"status": "success", "data": data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def set_environment_variable(
        self,
        project_id: str,
        variable_name: str,
        value: str,
        target: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Configure an environment variable on a Vercel project.
        
        Args:
            project_id: Vercel project ID or project name.
            variable_name: Environment variable name (e.g. 'GEMINI_API_KEY').
            value: Secret value.
            target: List of target environments (['production', 'preview']).
            
        Returns:
            Dict with status, variable_name, environment, and NO secret value.
        """
        targets = target or ["production", "preview"]
        url = f"{self.base_url}/v10/projects/{project_id}/env"

        payload = {
            "key": variable_name,
            "value": value,
            "type": "encrypted",
            "target": targets,
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "success",
                    "variable": variable_name,
                    "environment": ", ".join(targets),
                    "id": data.get("id"),
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if hasattr(e, "read") else ""
            return {
                "status": "error",
                "code": e.code,
                "variable": variable_name,
                "message": f"Vercel env set HTTP {e.code}: {e.reason}. {err_body}",
            }
        except Exception as e:
            return {"status": "error", "code": 500, "variable": variable_name, "message": str(e)}

    def create_deployment(
        self,
        project_name: str,
        files: List[Dict[str, str]],
        target: str = "production",
    ) -> Dict[str, Any]:
        """Create a new deployment on Vercel for the specified project.
        
        Args:
            project_name: Name of the Vercel project.
            files: List of dicts `{"file": rel_path, "data": file_content_str}`.
            target: Deployment target ('production' or 'preview').
            
        Returns:
            Dict containing status, deployment_id, deployment_url, status.
        """
        url = f"{self.base_url}/v13/deployments"
        payload = {
            "name": project_name,
            "target": target,
            "files": files,
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                url_host = data.get("url", "")
                if url_host and not url_host.startswith("http"):
                    url_host = f"https://{url_host}"

                return {
                    "status": "success",
                    "deployment_id": data.get("id"),
                    "deployment_url": url_host,
                    "readyState": data.get("readyState", "READY"),
                    "data": data,
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if hasattr(e, "read") else ""
            return {
                "status": "error",
                "code": e.code,
                "message": f"Vercel deployment HTTP {e.code}: {e.reason}. {err_body}",
            }
        except Exception as e:
            return {"status": "error", "code": 500, "message": str(e)}

    def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """Get status of a specific Vercel deployment by ID.
        
        Args:
            deployment_id: Vercel deployment ID.
            
        Returns:
            Dict containing status, readyState, url.
        """
        url = f"{self.base_url}/v13/deployments/{deployment_id}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                url_host = data.get("url", "")
                if url_host and not url_host.startswith("http"):
                    url_host = f"https://{url_host}"
                return {
                    "status": "success",
                    "deployment_id": data.get("id"),
                    "readyState": data.get("readyState", "READY"),
                    "url": url_host,
                }
        except urllib.error.HTTPError as e:
            return {"status": "error", "code": e.code, "message": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"status": "error", "code": 500, "message": str(e)}
