"""Deterministic file and schema tools for AgentForge Architect Agent."""

import json
import os
import re
from typing import Any, Dict, List, Optional
import jsonschema

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SCHEMA_PATH = os.path.join(WORKSPACE_ROOT, "backend", "schemas", "plan_schema.json")


def _resolve_safe_path(base_dir: str, rel_or_abs_path: str) -> str:
    """Resolve and validate path ensuring it stays within base_dir."""
    abs_base = os.path.abspath(base_dir)
    if os.path.isabs(rel_or_abs_path):
        target_path = os.path.abspath(rel_or_abs_path)
    else:
        target_path = os.path.abspath(os.path.join(abs_base, rel_or_abs_path))

    if not target_path.startswith(abs_base):
        raise ValueError(f"Access denied: path '{rel_or_abs_path}' is outside allowed workspace '{base_dir}'.")
    return target_path


def read_project_document(doc_path: str) -> str:
    """Read documentation files from the AgentForge workspace.
    
    Args:
        doc_path: Relative or absolute path to document inside AgentForge (e.g. 'docs/PRD.md').
        
    Returns:
        The content of the document as a string.
    """
    safe_path = _resolve_safe_path(WORKSPACE_ROOT, doc_path)
    if not os.path.isfile(safe_path):
        raise FileNotFoundError(f"Document not found at '{doc_path}' (resolved: '{safe_path}')")

    with open(safe_path, "r", encoding="utf-8") as f:
        return f.read()


def read_schema(schema_path: Optional[str] = None) -> Dict[str, Any]:
    """Read and return the JSON schema for plan.json.
    
    Args:
        schema_path: Optional custom path to plan_schema.json.
        
    Returns:
        JSON schema dict.
    """
    target = schema_path or DEFAULT_SCHEMA_PATH
    safe_path = _resolve_safe_path(WORKSPACE_ROOT, target) if not os.path.isabs(target) else target
    with open(safe_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_plan_json(plan_data: Dict[str, Any], schema_path: Optional[str] = None) -> Dict[str, Any]:
    """Validate plan_data against plan_schema.json and semantic business rules.
    
    Rules enforced:
    1. Satisfies JSON Schema (backend/schemas/plan_schema.json).
    2. Exactly one root agent exists in agents list.
    3. All 'from' and 'to' agent IDs in wiring refer to valid defined agents.
    
    Args:
        plan_data: The architecture plan dictionary.
        schema_path: Optional custom path to plan_schema.json.
        
    Returns:
        Dict with keys 'valid' (bool) and 'errors' (list of strings).
    """
    errors: List[str] = []

    # 1. JSON Schema validation
    try:
        schema = read_schema(schema_path)
        validator = jsonschema.Draft7Validator(schema)
        schema_errors = list(validator.iter_errors(plan_data))
        for err in schema_errors:
            path_str = ".".join(str(p) for p in err.absolute_path)
            errors.append(f"Schema error at '{path_str}': {err.message}")
    except Exception as e:
        errors.append(f"Failed to load or validate JSON schema: {str(e)}")

    if errors:
        return {"valid": False, "errors": errors}

    # 2. Semantic Checks: Root Agent Count
    agents = plan_data.get("agents", [])
    root_agents = [a for a in agents if a.get("is_root") is True]
    if len(root_agents) == 0:
        errors.append("Architecture failure: Exactly one root agent is required, but 0 were found.")
    elif len(root_agents) > 1:
        root_names = [a.get("name", a.get("id", "unknown")) for a in root_agents]
        errors.append(f"Architecture failure: Exactly one root agent is required, but {len(root_agents)} were found ({root_names}).")

    # 3. Semantic Checks: Wiring Consistency
    agent_ids = {a.get("id") for a in agents if "id" in a}
    wiring = plan_data.get("wiring", [])
    for idx, w in enumerate(wiring):
        from_id = w.get("from")
        to_id = w.get("to")
        if from_id not in agent_ids:
            errors.append(f"Wiring error at index {idx}: 'from' agent ID '{from_id}' does not match any defined agent.")
        if to_id not in agent_ids:
            errors.append(f"Wiring error at index {idx}: 'to' agent ID '{to_id}' does not match any defined agent.")

    valid = len(errors) == 0
    return {"valid": valid, "errors": errors}


def write_plan_json(project_path: str, plan_data: Dict[str, Any]) -> str:
    """Write the validated architecture plan to docs/plan.json inside project_path.
    
    Args:
        project_path: Path to the active project folder (e.g. 'generated/project01' or '.')
        plan_data: Architecture plan dictionary.
        
    Returns:
        Absolute file path where plan.json was written.
    """
    if project_path.endswith(".json"):
        if os.path.basename(project_path) == "design.json":
            target_path = os.path.abspath(os.path.join(os.path.dirname(project_path), "plan.json"))
        else:
            target_path = os.path.abspath(project_path)
    else:
        target_path = os.path.abspath(os.path.join(project_path, "docs", "plan.json"))


    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return target_path
