"""Deterministic tools for AgentForge Designer Agent."""

import json
import os
from typing import Any, Dict, List, Optional
import jsonschema

from backend.tools.file_tools import (
    WORKSPACE_ROOT,
    _resolve_safe_path,
    read_project_document,
    validate_plan_json,
)

DESIGN_SCHEMA_PATH = os.path.join(WORKSPACE_ROOT, "backend", "schemas", "design_schema.json")
PLAN_SCHEMA_PATH = os.path.join(WORKSPACE_ROOT, "backend", "schemas", "plan_schema.json")


def read_schema(schema_type: str = "design") -> Dict[str, Any]:
    """Read and return the specified JSON schema ('design' or 'plan').
    
    Args:
        schema_type: 'design' or 'plan'
        
    Returns:
        JSON schema dict.
    """
    path = DESIGN_SCHEMA_PATH if schema_type.lower() == "design" else PLAN_SCHEMA_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_plan_json(project_path: str = ".") -> Dict[str, Any]:
    """Load and validate plan.json from project_path or backend/docs/plan.json.
    
    Args:
        project_path: Active project path, file path, or workspace relative path.
        
    Returns:
        Dict with keys 'valid' (bool), 'data' (dict or None), and 'errors' (list of strings).
    """
    candidates = []
    if project_path.endswith(".json"):
        candidates.append(project_path)
    else:
        candidates.extend([
            os.path.join(project_path, "docs", "plan.json"),
            os.path.join(project_path, "plan.json"),
            os.path.join(WORKSPACE_ROOT, "backend", "docs", "plan.json"),
            os.path.join(WORKSPACE_ROOT, "docs", "plan.json"),
        ])

    target_file = None
    for cand in candidates:
        abs_cand = os.path.abspath(cand)
        if os.path.isfile(abs_cand):
            target_file = abs_cand
            break

    if not target_file:
        return {
            "valid": False,
            "data": None,
            "errors": [f"plan.json not found in candidate locations for project_path '{project_path}'."],
        }

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            plan_data = json.load(f)
    except Exception as e:
        return {
            "valid": False,
            "data": None,
            "errors": [f"Failed to parse JSON from '{target_file}': {str(e)}"],
        }

    val_res = validate_plan_json(plan_data, PLAN_SCHEMA_PATH)
    if not val_res["valid"]:
        return {
            "valid": False,
            "data": plan_data,
            "errors": [f"Plan file '{target_file}' is invalid: {val_res['errors']}"],
        }

    return {
        "valid": True,
        "data": plan_data,
        "file_path": target_file,
        "errors": [],
    }


def validate_design_json(
    design_data: Dict[str, Any], plan_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Validate design_data against design_schema.json and semantic business rules.
    
    Rules enforced:
    1. Satisfies design_schema.json.
    2. Every agent design has a non-empty system_prompt.
    3. Wiring consistency (all 'from' and 'to' agent IDs refer to valid defined agents).
    4. If plan_data is provided, enforces parity:
       - Exact match of agent count.
       - Exact match of agent IDs.
       - Exact match of communication wiring.
       
    Returns:
        Dict with keys 'valid' (bool) and 'errors' (list of strings).
    """
    errors: List[str] = []

    # 1. JSON Schema validation
    try:
        schema = read_schema("design")
        validator = jsonschema.Draft7Validator(schema)
        schema_errors = list(validator.iter_errors(design_data))
        for err in schema_errors:
            path_str = ".".join(str(p) for p in err.absolute_path)
            errors.append(f"Schema error at '{path_str}': {err.message}")
    except Exception as e:
        errors.append(f"Failed to load or validate design schema: {str(e)}")

    if errors:
        return {"valid": False, "errors": errors}

    # 2. System prompt non-empty check
    agents = design_data.get("agents", [])
    for idx, agent in enumerate(agents):
        prompt = agent.get("system_prompt", "")
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"Agent design error at index {idx} ({agent.get('id')}): system_prompt must be a non-empty string.")

    # 3. Wiring reference check
    agent_ids = {a.get("id") for a in agents if "id" in a}
    wiring = design_data.get("wiring", [])
    for idx, w in enumerate(wiring):
        from_id = w.get("from")
        to_id = w.get("to")
        if from_id not in agent_ids:
            errors.append(f"Design wiring error at index {idx}: 'from' ID '{from_id}' not found in defined agents.")
        if to_id not in agent_ids:
            errors.append(f"Design wiring error at index {idx}: 'to' ID '{to_id}' not found in defined agents.")

    # 4. Parity check with plan_data if provided
    if plan_data:
        plan_agents = plan_data.get("agents", [])
        plan_agent_ids = {a.get("id") for a in plan_agents if "id" in a}
        
        if len(agents) != len(plan_agents):
            errors.append(
                f"Architecture mismatch: plan.json specifies {len(plan_agents)} agents, "
                f"but design.json contains {len(agents)} agents."
            )

        if agent_ids != plan_agent_ids:
            errors.append(
                f"Agent ID mismatch: plan IDs {sorted(list(plan_agent_ids))} "
                f"do not match design IDs {sorted(list(agent_ids))}."
            )

    valid = len(errors) == 0
    return {"valid": valid, "errors": errors}


def write_design_json(
    project_path: str, design_data: Dict[str, Any], plan_data: Optional[Dict[str, Any]] = None
) -> str:
    """Validate design_data and write design.json to project_path/docs/design.json or backend/docs/design.json.
    
    Args:
        project_path: Active project folder path, file path, or 'backend'.
        design_data: Detailed design dictionary.
        plan_data: Optional plan dictionary for parity verification.
        
    Returns:
        Absolute file path where design.json was written.
    """
    val_res = validate_design_json(design_data, plan_data)
    if not val_res["valid"]:
        raise ValueError(f"Cannot write invalid design.json. Errors: {val_res['errors']}")

    if project_path.endswith(".json"):
        if os.path.basename(project_path) == "plan.json":
            target_path = os.path.abspath(os.path.join(os.path.dirname(project_path), "design.json"))
        else:
            target_path = os.path.abspath(project_path)
    elif project_path == "backend" or project_path == "backend/":
        target_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, "backend", "docs", "design.json"))
    else:
        target_path = os.path.abspath(os.path.join(project_path, "docs", "design.json"))


    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(design_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return target_path
