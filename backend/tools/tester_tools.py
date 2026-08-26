"""Deterministic tools for AgentForge Tester Agent."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.tools.coder_tools import _assert_in_workspace, WORKSPACE_ROOT
from backend.tools.designer_tools import read_plan_json, validate_design_json
from backend.tools.file_tools import validate_plan_json


def read_file(file_path: str) -> str:
    """Read a text file from within the AgentForge workspace."""
    safe = _assert_in_workspace(file_path)
    with open(safe, "r", encoding="utf-8") as f:
        return f.read()


def list_directory(dir_path: str) -> List[str]:
    """List relative file paths in dir_path."""
    safe = _assert_in_workspace(dir_path)
    entries = []
    if not os.path.exists(safe):
        return []
    for root, dirs, files in os.walk(safe):
        for name in dirs + files:
            full = os.path.join(root, name)
            entries.append(os.path.relpath(full, safe))
    return sorted(entries)


def search_files(dir_path: str, pattern: str) -> List[str]:
    """Search files by pattern (glob) within dir_path."""
    safe = _assert_in_workspace(dir_path)
    if not os.path.exists(safe):
        return []
    return [str(p) for p in Path(safe).rglob(pattern)]


def execute_command(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Execute restricted shell command within workspace."""
    work_dir = cwd or WORKSPACE_ROOT
    safe_cwd = _assert_in_workspace(work_dir)
    
    # Allowed command prefixes
    allowed = {"pytest", "python", "python3", "ls", "cat", "find", "grep"}
    cmd_name = command.strip().split()[0] if command.strip() else ""
    if cmd_name not in allowed:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command '{cmd_name}' not allowed for tester.",
        }

    try:
        res = subprocess.run(
            command,
            shell=True,
            cwd=safe_cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }


def validate_plan(project_path: str) -> Dict[str, Any]:
    """Load and validate plan.json."""
    return read_plan_json(project_path)


def validate_design(project_path: str) -> Dict[str, Any]:
    """Load and validate design.json."""
    plan_res = read_plan_json(project_path)
    plan_data = plan_res.get("data")
    
    candidates = [
        os.path.join(project_path, "docs", "design.json"),
        os.path.join(project_path, "design.json"),
        os.path.join(WORKSPACE_ROOT, "backend", "docs", "design.json"),
    ]
    if project_path.endswith(".json"):
        candidates.insert(0, project_path)

    target_file = None
    for cand in candidates:
        if os.path.isfile(os.path.abspath(cand)):
            target_file = os.path.abspath(cand)
            break

    if not target_file:
        return {"valid": False, "data": None, "errors": [f"design.json not found in {project_path}"]}

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            design_data = json.load(f)
    except Exception as e:
        return {"valid": False, "data": None, "errors": [str(e)]}

    val_res = validate_design_json(design_data, plan_data)
    val_res["data"] = design_data
    val_res["file_path"] = target_file
    return val_res


def inspect_project(project_path: str) -> Dict[str, Any]:
    """Inspect structure of project directory."""
    safe = _assert_in_workspace(project_path)
    if not os.path.exists(safe):
        return {"exists": False, "files": [], "agent_dirs": []}
    files = list_directory(safe)
    agents_dir = os.path.join(safe, "agents")
    agent_dirs = []
    if os.path.isdir(agents_dir):
        agent_dirs = [d for d in os.listdir(agents_dir) if os.path.isdir(os.path.join(agents_dir, d))]
    return {
        "exists": True,
        "root": safe,
        "files": files,
        "agent_dirs": sorted(agent_dirs),
    }


def create_test_file(project_path: str, test_filename: str, content: str) -> str:
    """Create test file inside generated project tests/ directory."""
    safe_proj = _assert_in_workspace(project_path)
    tests_dir = os.path.join(safe_proj, "tests")
    os.makedirs(tests_dir, exist_ok=True)
    target_file = os.path.join(tests_dir, test_filename)
    safe_file = _assert_in_workspace(target_file)
    with open(safe_file, "w", encoding="utf-8") as f:
        f.write(content)
    return safe_file


def run_test(project_path: str, test_filename: str) -> Dict[str, Any]:
    """Run specific test file with pytest."""
    safe_proj = _assert_in_workspace(project_path)
    test_path = os.path.join(safe_proj, "tests", test_filename)
    if not os.path.exists(test_path):
        return {"status": "error", "message": f"Test file {test_filename} does not exist."}
    
    cmd = f"python3 -m pytest {test_path} -v"
    return execute_command(cmd, cwd=safe_proj)


def run_test_suite(project_path: str) -> Dict[str, Any]:
    """Run full test suite in project tests/ directory."""
    safe_proj = _assert_in_workspace(project_path)
    tests_dir = os.path.join(safe_proj, "tests")
    if not os.path.exists(tests_dir):
        return {
            "returncode": -1,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "stdout": "",
            "stderr": "tests/ directory does not exist",
        }

    res = execute_command("python3 -m pytest tests/ -q", cwd=safe_proj)
    stdout = res.get("stdout", "")
    
    # Parse pytest summary output
    passed = 0
    failed = 0
    match_p = re.search(r"(\d+)\s+passed", stdout)
    match_f = re.search(r"(\d+)\s+failed", stdout)
    if match_p:
        passed = int(match_p.group(1))
    if match_f:
        failed = int(match_f.group(1))

    total = passed + failed
    return {
        "returncode": res.get("returncode", -1),
        "tests_run": total,
        "tests_passed": passed,
        "tests_failed": failed,
        "stdout": stdout,
        "stderr": res.get("stderr", ""),
    }


def check_import(project_path: str, module_name: str) -> Dict[str, Any]:
    """Check if python module in project imports without error."""
    safe_proj = _assert_in_workspace(project_path)
    cmd = f"python3 -c \"import sys; sys.path.insert(0, '.'); import {module_name}\""
    res = execute_command(cmd, cwd=safe_proj)
    return {
        "module": module_name,
        "success": res.get("returncode") == 0,
        "stderr": res.get("stderr", ""),
    }


def check_agent_wiring(project_path: str) -> Dict[str, Any]:
    """Check if root agent.py properly imports and wires sub-agents matching plan.json."""
    safe_proj = _assert_in_workspace(project_path)
    agent_py = os.path.join(safe_proj, "agent.py")
    if not os.path.isfile(agent_py):
        return {"valid": False, "errors": ["agent.py missing"]}

    with open(agent_py, "r", encoding="utf-8") as f:
        code = f.read()

    plan_res = read_plan_json(project_path)
    if not plan_res.get("valid"):
        return {"valid": False, "errors": ["Plan invalid for wiring check"]}

    plan_data = plan_res.get("data", {})
    plan_agents = [a.get("id") for a in plan_data.get("agents", [])]

    missing_imports = []
    for aid in plan_agents:
        pattern = f"from agents.{aid}.agent import"
        if pattern not in code:
            missing_imports.append(aid)

    if missing_imports:
        return {
            "valid": False,
            "errors": [f"Root agent.py missing imports for agents: {missing_imports}"],
        }

    return {"valid": True, "errors": []}


def run_agent_interaction_test(project_path: str) -> Dict[str, Any]:
    """Test interaction with root agent."""
    safe_proj = _assert_in_workspace(project_path)
    script = """import sys
sys.path.insert(0, '.')
from agent import get_root_agent
root = get_root_agent()
agents = root.list_agents()
print(f'Active agents count: {len(agents)}')
"""
    cmd = f"python3 -c \"{script}\""
    res = execute_command(cmd, cwd=safe_proj)
    return {
        "success": res.get("returncode") == 0,
        "stdout": res.get("stdout", ""),
        "stderr": res.get("stderr", ""),
    }


def run_smoke_test(project_path: str) -> Dict[str, Any]:
    """Perform smoke test on project (load root agent and check fast_api app)."""
    safe_proj = _assert_in_workspace(project_path)
    script = """import sys
sys.path.insert(0, '.')
from agent import get_root_agent
from fast_api import app
root = get_root_agent()
print('SMOKE_TEST_PASS')
"""
    cmd = f"python3 -c \"{script}\""
    res = execute_command(cmd, cwd=safe_proj)
    success = "SMOKE_TEST_PASS" in res.get("stdout", "")
    return {
        "status": "passed" if success else "failed",
        "error": res.get("stderr", "") if not success else "",
    }


def check_vercel_structure(project_path: str) -> Dict[str, Any]:
    """Verify project has required Vercel deployment structure."""
    safe_proj = _assert_in_workspace(project_path)
    req_txt = os.path.join(safe_proj, "requirements.txt")
    fast_api = os.path.join(safe_proj, "fast_api.py")
    api_dir = os.path.join(safe_proj, "api")
    api_index = os.path.join(safe_proj, "api", "index.py")

    has_reqs = os.path.isfile(req_txt)
    has_fast_api = os.path.isfile(fast_api)
    has_api_entry = os.path.isfile(api_index) or has_fast_api

    valid = has_reqs and has_api_entry
    errors = []
    if not has_reqs:
        errors.append("requirements.txt missing for Vercel deployment")
    if not has_api_entry:
        errors.append("Neither api/index.py nor fast_api.py entry point found")

    return {
        "valid": valid,
        "has_requirements": has_reqs,
        "has_api_entrypoint": has_api_entry,
        "errors": errors,
    }


def scan_for_secrets(project_path: str) -> Dict[str, Any]:
    """Scan project files for hard-coded secrets or API keys."""
    safe_proj = _assert_in_workspace(project_path)
    
    # Secret regex patterns
    secret_patterns = [
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
        (r"AIzaSy[a-zA-Z0-9_-]{33}", "Google Gemini API Key"),
        (r"sk-[a-zA-Z0-9]{48}", "OpenAI API Key"),
    ]

    exposed = []
    files = list_directory(safe_proj)
    for rel_path in files:
        if rel_path.startswith(".git") or rel_path.endswith(".pyc"):
            continue
        full_path = os.path.join(safe_proj, rel_path)
        if not os.path.isfile(full_path):
            continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            for pattern, sec_type in secret_patterns:
                if re.search(pattern, content):
                    # Exclude .env.example placeholder strings
                    if "YOUR_GEMINI_API_KEY_HERE" in content or "YOUR_KEY" in content:
                        continue
                    exposed.append({
                        "file": rel_path,
                        "type": sec_type,
                    })
        except Exception:
            pass

    return {
        "secrets_found": len(exposed) > 0,
        "exposed_secrets": exposed,
    }


def check_independent_execution(project_path: str) -> Dict[str, Any]:
    """Verify generated project does not import AgentForge internal packages."""
    safe_proj = _assert_in_workspace(project_path)
    forbidden_imports = ["backend.agents", "backend.tools", "backend.services"]
    
    violations = []
    files = search_files(safe_proj, "*.py")
    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()
            for forbidden in forbidden_imports:
                if forbidden in code:
                    rel = os.path.relpath(filepath, safe_proj)
                    violations.append({"file": rel, "forbidden_import": forbidden})
        except Exception:
            pass

    return {
        "is_independent": len(violations) == 0,
        "violations": violations,
    }
