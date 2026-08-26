"""Deterministic tools for AgentForge Coder Agent.

All file operations are restricted to the AgentForge workspace.
No shell access outside the workspace is permitted.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


from backend.tools.designer_tools import read_plan_json, validate_design_json, read_schema
from backend.tools.file_tools import validate_plan_json, WORKSPACE_ROOT

TEMPLATE_PATH = os.path.join(WORKSPACE_ROOT, "backend", "template")
GENERATED_ROOT = os.path.join(WORKSPACE_ROOT, "generated")

# Allowed commands for terminal_execute
ALLOWED_COMMANDS = {"cp", "mkdir", "ls", "find", "grep", "python", "python3", "pytest", "cat", "echo"}
BLOCKED_ARGS = {"sudo", "shutdown", "reboot", "rm -rf /", "mkfs", "> /dev/"}


def _assert_in_workspace(path: str) -> str:
    """Resolve path and assert it stays within the workspace root or temp directory."""
    abs_path = os.path.abspath(path)
    temp_dir = os.path.abspath(tempfile.gettempdir())
    if not (abs_path.startswith(WORKSPACE_ROOT) or abs_path.startswith(temp_dir)):
        raise ValueError(f"Access denied: '{path}' is outside AgentForge workspace.")
    return abs_path



# ─────────────────────────────────────────────
# Filesystem Tools
# ─────────────────────────────────────────────

def read_file(file_path: str) -> str:
    """Read a text file from within the AgentForge workspace.
    
    Args:
        file_path: Absolute or relative path to the file.
        
    Returns:
        File content as string.
    """
    safe = _assert_in_workspace(file_path)
    with open(safe, "r", encoding="utf-8") as f:
        return f.read()


def write_file(file_path: str, content: str) -> str:
    """Write content to a file within the AgentForge workspace. Creates parent directories.
    
    Args:
        file_path: Absolute or relative path to write.
        content: Content string to write.
        
    Returns:
        Absolute path of written file.
    """
    safe = _assert_in_workspace(file_path)
    os.makedirs(os.path.dirname(safe), exist_ok=True)
    with open(safe, "w", encoding="utf-8") as f:
        f.write(content)
    return safe


def edit_file(file_path: str, old_text: str, new_text: str) -> str:
    """Perform a targeted text replacement within an existing file.
    
    Args:
        file_path: Path to file to edit.
        old_text: Exact text to find and replace.
        new_text: Replacement text.
        
    Returns:
        'replaced' if successful, 'not_found' if old_text was not found.
    """
    safe = _assert_in_workspace(file_path)
    content = read_file(safe)
    if old_text not in content:
        return "not_found"
    new_content = content.replace(old_text, new_text, 1)
    write_file(safe, new_content)
    return "replaced"


def list_directory(dir_path: str) -> List[str]:
    """List all files and directories under dir_path.
    
    Args:
        dir_path: Path to directory.
        
    Returns:
        List of relative paths from dir_path.
    """
    safe = _assert_in_workspace(dir_path)
    entries = []
    for root, dirs, files in os.walk(safe):
        for name in dirs + files:
            full = os.path.join(root, name)
            entries.append(os.path.relpath(full, safe))
    return sorted(entries)


def search_files(dir_path: str, pattern: str) -> List[str]:
    """Search files by filename pattern (glob) within the AgentForge workspace.
    
    Args:
        dir_path: Directory to search.
        pattern: Glob pattern (e.g. '*.py', 'agent*.py').
        
    Returns:
        List of matching absolute file paths.
    """
    safe = _assert_in_workspace(dir_path)
    return [str(p) for p in Path(safe).rglob(pattern)]


def copy_template(destination_path: str, overwrite: bool = False) -> Dict[str, Any]:
    """Copy the AgentForge backend template to the destination project path.
    
    Copies template baseline files into destination directory.
    
    Args:
        destination_path: Absolute or relative path to create the project.
        overwrite: If True, replaces existing files in destination. Default False.
        
    Returns:
        Dict with 'status', 'template_path', 'destination', and 'existed' keys.
    """
    if not os.path.isdir(TEMPLATE_PATH):
        return {
            "status": "error",
            "error": f"Template directory not found at: {TEMPLATE_PATH}",
            "template_path": TEMPLATE_PATH,
        }

    safe_dest = _assert_in_workspace(destination_path)
    existed = os.path.isdir(safe_dest)

    shutil.copytree(TEMPLATE_PATH, safe_dest, dirs_exist_ok=True)
    return {
        "status": "success",
        "template_path": TEMPLATE_PATH,
        "destination": safe_dest,
        "existed": existed,
    }



# ─────────────────────────────────────────────
# Execution Tool
# ─────────────────────────────────────────────

def terminal_execute(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Execute a restricted shell command within the AgentForge workspace.
    
    Only allows safe development commands. Blocks dangerous operations.
    
    Args:
        command: Shell command string to execute.
        cwd: Working directory (must be within workspace, defaults to workspace root).
        
    Returns:
        Dict with 'returncode', 'stdout', 'stderr' keys.
    """
    # Validate working directory
    work_dir = cwd or WORKSPACE_ROOT
    safe_cwd = _assert_in_workspace(work_dir)

    # Validate command starts with an allowed prefix
    cmd_name = command.strip().split()[0] if command.strip() else ""
    if cmd_name not in ALLOWED_COMMANDS:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command '{cmd_name}' is not in the allowed command list: {sorted(ALLOWED_COMMANDS)}",
        }

    # Block dangerous patterns
    for blocked in BLOCKED_ARGS:
        if blocked in command:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command contains blocked pattern: '{blocked}'",
            }

    result = subprocess.run(
        command,
        shell=True,
        cwd=safe_cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ─────────────────────────────────────────────
# Validation Helpers
# ─────────────────────────────────────────────

def validate_plan(project_path: str) -> Dict[str, Any]:
    """Load and validate plan.json from the given project path.
    
    Args:
        project_path: Path containing docs/plan.json.
        
    Returns:
        Dict with 'valid', 'data', and 'errors' keys.
    """
    return read_plan_json(project_path)


def validate_design(project_path: str) -> Dict[str, Any]:
    """Load and validate design.json from the given project path.
    
    Args:
        project_path: Path containing docs/design.json.
        
    Returns:
        Dict with 'valid', 'data', 'errors' keys.
    """
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
        return {
            "valid": False,
            "data": None,
            "errors": [f"design.json not found for project_path '{project_path}'."],
        }

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            design_data = json.load(f)
    except Exception as e:
        return {
            "valid": False,
            "data": None,
            "errors": [f"Failed to parse design.json from '{target_file}': {str(e)}"],
        }

    val_res = validate_design_json(design_data)
    if not val_res["valid"]:
        return {
            "valid": False,
            "data": design_data,
            "errors": val_res["errors"],
        }

    return {"valid": True, "data": design_data, "file_path": target_file, "errors": []}


def inspect_generated_structure(project_path: str) -> Dict[str, Any]:
    """Inspect the current file structure of a generated project directory.
    
    Args:
        project_path: Path to the generated project root.
        
    Returns:
        Dict with 'exists', 'files' (list), and 'agent_dirs' (list of agent subdirs).
    """
    safe = os.path.abspath(project_path)
    exists = os.path.isdir(safe)
    if not exists:
        return {"exists": False, "files": [], "agent_dirs": []}

    all_files = list_directory(safe)
    agents_dir = os.path.join(safe, "agents")
    agent_dirs: List[str] = []
    if os.path.isdir(agents_dir):
        agent_dirs = [
            d for d in os.listdir(agents_dir)
            if os.path.isdir(os.path.join(agents_dir, d))
        ]

    return {
        "exists": True,
        "root": safe,
        "files": all_files,
        "agent_dirs": sorted(agent_dirs),
    }
