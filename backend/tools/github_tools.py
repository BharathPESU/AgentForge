"""Deterministic tools for AgentForge GitHub Agent."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.services.github_service import GitHubService, get_github_token
from backend.tools.coder_tools import _assert_in_workspace, WORKSPACE_ROOT


def read_file(file_path: str) -> str:
    """Read text file from within workspace."""
    safe = _assert_in_workspace(file_path)
    with open(safe, "r", encoding="utf-8") as f:
        return f.read()


def list_directory(dir_path: str) -> List[str]:
    """List relative files under dir_path."""
    safe = _assert_in_workspace(dir_path)
    entries = []
    if not os.path.exists(safe):
        return []
    for root, dirs, files in os.walk(safe):
        for name in dirs + files:
            full = os.path.join(root, name)
            entries.append(os.path.relpath(full, safe))
    return sorted(entries)


def inspect_project(project_path: str) -> Dict[str, Any]:
    """Inspect generated project directory structure without sensitive contents."""
    safe = _assert_in_workspace(project_path)
    if not os.path.exists(safe):
        return {"valid": False, "file_count": 0, "project_path": project_path}

    files = list_directory(safe)
    return {
        "valid": True,
        "file_count": len(files),
        "project_path": safe,
        "has_gitignore": os.path.isfile(os.path.join(safe, ".gitignore")),
        "has_dotenv": os.path.isfile(os.path.join(safe, ".env")),
    }


def _run_git(command: str, cwd: str) -> Dict[str, Any]:
    """Safely execute git subcommands inside target project directory."""
    safe_cwd = _assert_in_workspace(cwd)
    cmd_full = f"git {command}"
    
    # Token sanitization helper
    token = get_github_token()
    
    try:
        res = subprocess.run(
            cmd_full,
            shell=True,
            cwd=safe_cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        stdout = res.stdout
        stderr = res.stderr
        if token:
            stdout = stdout.replace(token, "[REDACTED]")
            stderr = stderr.replace(token, "[REDACTED]")

        return {
            "returncode": res.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as e:
        err_msg = str(e)
        if token:
            err_msg = err_msg.replace(token, "[REDACTED]")
        return {"returncode": -1, "stdout": "", "stderr": err_msg}


def check_git_status(project_path: str) -> Dict[str, Any]:
    """Check git status of the target project directory."""
    safe_proj = _assert_in_workspace(project_path)
    git_dir = os.path.join(safe_proj, ".git")
    is_init = os.path.isdir(git_dir)

    if not is_init:
        return {
            "git_initialized": False,
            "current_branch": None,
            "has_commits": False,
        }

    res_b = _run_git("rev-parse --abbrev-ref HEAD", cwd=safe_proj)
    branch = res_b.get("stdout", "").strip() or "main"

    res_s = _run_git("status --porcelain", cwd=safe_proj)
    status_lines = [l for l in res_s.get("stdout", "").splitlines() if l.strip()]

    return {
        "git_initialized": True,
        "current_branch": branch,
        "uncommitted_changes": len(status_lines) > 0,
        "status_summary": status_lines[:10],
    }


def scan_project_secrets(project_path: str) -> Dict[str, Any]:
    """Lightweight secret check before git staging/commit."""
    safe_proj = _assert_in_workspace(project_path)
    
    # Check .gitignore safety
    gitignore_file = os.path.join(safe_proj, ".gitignore")
    dotenv_file = os.path.join(safe_proj, ".env")
    
    if os.path.isfile(dotenv_file):
        gitignore_content = ""
        if os.path.isfile(gitignore_file):
            with open(gitignore_file, "r", encoding="utf-8") as f:
                gitignore_content = f.read()
        
        if ".env" not in gitignore_content:
            return {
                "safe": False,
                "reason": "unignored_env_file",
                "file": ".env",
                "message": ".env file exists but is not listed in .gitignore",
            }

    # Scan project source files for hardcoded secrets
    secret_patterns = [
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
        (r"AIzaSy[a-zA-Z0-9_-]{33}", "Google Gemini API Key"),
        (r"AGENTFORGE_TEST_SECRET_[a-zA-Z0-9_-]{20,}", "Test Secret Token"),
    ]

    for root, dirs, files in os.walk(safe_proj):
        # Skip git dir
        if ".git" in root:
            continue
        for fname in files:
            if fname in [".env.example", "README.md", "fast_api.py"]:
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for pattern, sec_type in secret_patterns:
                    if re.search(pattern, content):
                        if "YOUR_GEMINI_API_KEY_HERE" in content or "YOUR_KEY" in content:
                            continue
                        rel_path = os.path.relpath(fpath, safe_proj)
                        return {
                            "safe": False,
                            "reason": "possible_secret_detected",
                            "file": rel_path,
                            "message": f"Possible {sec_type} detected in {rel_path}",
                        }
            except Exception:
                pass

    return {"safe": True}


def initialize_git(project_path: str) -> Dict[str, Any]:
    """Initialize a local git repository in project directory if not already present."""
    safe_proj = _assert_in_workspace(project_path)
    git_dir = os.path.join(safe_proj, ".git")

    if os.path.isdir(git_dir):
        return {"status": "success", "message": "Git repository already initialized.", "reused": True}

    res = _run_git("init -b main", cwd=safe_proj)
    if res["returncode"] != 0:
        # Fallback for older git versions without -b flag
        res = _run_git("init", cwd=safe_proj)
        _run_git("checkout -b main", cwd=safe_proj)

    return {
        "status": "success" if res["returncode"] == 0 else "error",
        "message": res.get("stdout", "") or res.get("stderr", ""),
        "reused": False,
    }


def create_github_repository(
    repo_name: str, description: str = "", private: bool = True
) -> Dict[str, Any]:
    """Create a remote repository on GitHub via API.
    
    Args:
        repo_name: Desired GitHub repository name.
        description: Repository description.
        private: True for private, False for public.
        
    Returns:
        Dict with repository details or error.
    """
    token = get_github_token()
    if not token:
        return {
            "status": "error",
            "reason": "missing_github_token",
            "message": "GITHUB_TOKEN / github_token environment variable is not configured.",
        }

    gh_service = GitHubService(token=token)
    return gh_service.create_repository(name=repo_name, description=description, private=private)


def add_files(project_path: str) -> Dict[str, Any]:
    """Stage project files for git commit, verifying secret safety first."""
    safe_proj = _assert_in_workspace(project_path)
    
    # Secret check before adding
    sec_res = scan_project_secrets(project_path)
    if not sec_res["safe"]:
        return {
            "status": "failed",
            "reason": sec_res["reason"],
            "file": sec_res["file"],
            "message": sec_res["message"],
        }

    res = _run_git("add .", cwd=safe_proj)
    return {
        "status": "success" if res["returncode"] == 0 else "error",
        "stderr": res.get("stderr", ""),
    }


def commit_changes(project_path: str, message: str = "feat: publish generated agent system") -> Dict[str, Any]:
    """Create a git commit with the staged project files."""
    safe_proj = _assert_in_workspace(project_path)
    
    # Check if anything is staged or changed
    status_res = check_git_status(project_path)
    
    # Configure local git user if not set
    _run_git('config user.name "AgentForge Builder"', cwd=safe_proj)
    _run_git('config user.email "agentforge@builder.internal"', cwd=safe_proj)

    res = _run_git(f'commit -m "{message}"', cwd=safe_proj)
    
    # Get commit SHA
    sha_res = _run_git("rev-parse HEAD", cwd=safe_proj)
    sha = sha_res.get("stdout", "").strip() or "head"

    return {
        "status": "success" if (res["returncode"] == 0 or "nothing to commit" in res.get("stdout", "")) else "error",
        "sha": sha,
        "message": message,
        "stdout": res.get("stdout", ""),
        "stderr": res.get("stderr", ""),
    }


def set_remote(project_path: str, remote_url: str) -> Dict[str, Any]:
    """Set remote origin URL for the project repository."""
    safe_proj = _assert_in_workspace(project_path)
    
    # Never embed token in stored remote URL
    token = get_github_token()
    clean_url = remote_url
    if token:
        clean_url = clean_url.replace(f"{token}@", "")

    _run_git("remote remove origin", cwd=safe_proj)
    res = _run_git(f"remote add origin {clean_url}", cwd=safe_proj)

    return {
        "status": "success" if res["returncode"] == 0 else "error",
        "remote_url": clean_url,
        "stderr": res.get("stderr", ""),
    }


def push_repository(project_path: str, branch: str = "main") -> Dict[str, Any]:
    """Push local main branch to remote origin using authenticated URL in memory."""
    safe_proj = _assert_in_workspace(project_path)
    token = get_github_token()

    if not token:
        return {
            "status": "failed",
            "reason": "missing_github_token",
            "message": "Cannot push without GITHUB_TOKEN environment variable.",
        }

    # Get clean remote origin URL
    rem_res = _run_git("remote get-url origin", cwd=safe_proj)
    origin_url = rem_res.get("stdout", "").strip()

    if not origin_url:
        return {
            "status": "failed",
            "reason": "missing_remote_origin",
            "message": "Remote origin URL is not configured.",
        }

    # Construct authenticated URL for push operation ONLY (do not save token to git config)
    # e.g. https://x-access-token:TOKEN@github.com/owner/repo.git
    auth_url = origin_url
    if origin_url.startswith("https://"):
        auth_url = origin_url.replace("https://", f"https://x-access-token:{token}@")

    push_cmd = f"push -u {auth_url} {branch} --force"
    res = _run_git(push_cmd, cwd=safe_proj)

    if res["returncode"] == 0:
        return {
            "status": "success",
            "branch": branch,
            "remote_url": origin_url,
        }
    else:
        return {
            "status": "failed",
            "reason": "push_failed",
            "error_category": "GIT_PUSH_ERROR",
            "message": f"Git push failed: {res.get('stderr', '')}",
        }


def get_repository_info(project_path: str) -> Dict[str, Any]:
    """Retrieve full git repository information for project."""
    safe_proj = _assert_in_workspace(project_path)
    status_res = check_git_status(project_path)
    
    rem_res = _run_git("remote get-url origin", cwd=safe_proj)
    url = rem_res.get("stdout", "").strip()

    sha_res = _run_git("rev-parse HEAD", cwd=safe_proj)
    sha = sha_res.get("stdout", "").strip()

    return {
        "initialized": status_res.get("git_initialized", False),
        "branch": status_res.get("current_branch", "main"),
        "remote_url": url,
        "commit_sha": sha,
    }
