"""Tester Agent implementation for AgentForge using Google ADK."""

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import google.adk as adk

from backend.tools.tester_tools import (
    check_agent_wiring,
    check_import,
    check_independent_execution,
    check_vercel_structure,
    create_test_file,
    execute_command,
    inspect_project,
    list_directory,
    read_file,
    run_agent_interaction_test,
    run_sandboxed_execution_test,
    run_smoke_test,
    run_test,
    run_test_suite,
    scan_for_secrets,
    search_files,
    validate_design,
    validate_plan,
    verify_execution_output,
)

from backend.roundRobin import set_gemini_api_key_env

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


PROMPT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "tester_prompt.md"
)


def load_tester_instruction(prompt_path: Optional[str] = None) -> str:
    """Load the Tester Agent system instruction from markdown file."""
    path = prompt_path or PROMPT_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TesterAgent:
    """Tester Agent responsible for validating generated multi-agent projects
    against plan.json, design.json, coder_result.json, and runtime execution checks.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        prompt_path: Optional[str] = None,
    ):
        self.model_name = model_name or DEFAULT_MODEL
        self.prompt_path = prompt_path
        self.instruction = load_tester_instruction(prompt_path)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        """Instantiate Google ADK Agent with deterministic tools."""
        return adk.Agent(
            name="tester_agent",
            description="AgentForge Tester Agent for automated project verification",
            model=self.model_name,
            instruction=self.instruction,
            tools=[
                read_file,
                list_directory,
                search_files,
                execute_command,
                validate_plan,
                validate_design,
                inspect_project,
                create_test_file,
                run_test,
                run_test_suite,
                check_import,
                check_agent_wiring,
                run_agent_interaction_test,
                run_smoke_test,
                run_sandboxed_execution_test,
                verify_execution_output,
                check_vercel_structure,
                scan_for_secrets,
                check_independent_execution,
            ],
        )

    def validate_project(
        self,
        project_path: str = "generated/project01",
        override_llm_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform comprehensive 15-step validation suite on the target project.
        
        Returns:
            Dict containing test_result.json contract structure.
        """
        set_gemini_api_key_env()
        abs_proj = os.path.abspath(project_path)
        failures: List[Dict[str, Any]] = []

        # Step 1: Read coder_result.json context if available
        coder_res_path = os.path.join(abs_proj, "docs", "coder_result.json")
        coder_ctx = {}
        if os.path.isfile(coder_res_path):
            try:
                with open(coder_res_path, "r", encoding="utf-8") as f:
                    coder_ctx = json.load(f)
            except Exception:
                pass

        # Step 2: Validate plan.json
        plan_val = validate_plan(project_path)
        if not plan_val["valid"]:
            result_payload = self._build_result_payload(
                status="blocked",
                project_path=project_path,
                coder_ctx=coder_ctx,
                checks={
                    "plan": "failed",
                    "design": "blocked",
                    "structure": "blocked",
                    "agents": "blocked",
                    "tools": "blocked",
                    "wiring": "blocked",
                    "communication": "blocked",
                    "tests": "blocked",
                    "smoke_test": "blocked",
                    "vercel_structure": "blocked",
                    "secrets": "blocked",
                    "independent_run": "blocked",
                },
                summary={"tests_run": 0, "tests_passed": 0, "tests_failed": 0},
                failures=[{
                    "test": "plan_validation",
                    "category": "ARCHITECTURE_ERROR",
                    "severity": "critical",
                    "file": "docs/plan.json",
                    "message": f"plan.json validation failed: {plan_val['errors']}",
                    "responsible_agent": "architect_agent",
                    "recommended_action": "Regenerate architecture plan.json matching plan_schema.json",
                }],
                next_agent="architect_agent",
                next_reason="Architecture plan is invalid",
            )
            self._write_test_result(abs_proj, result_payload)
            return result_payload

        # Step 3: Validate design.json
        design_val = validate_design(project_path)
        if not design_val["valid"]:
            result_payload = self._build_result_payload(
                status="blocked",
                project_path=project_path,
                coder_ctx=coder_ctx,
                checks={
                    "plan": "passed",
                    "design": "failed",
                    "structure": "blocked",
                    "agents": "blocked",
                    "tools": "blocked",
                    "wiring": "blocked",
                    "communication": "blocked",
                    "tests": "blocked",
                    "smoke_test": "blocked",
                    "vercel_structure": "blocked",
                    "secrets": "blocked",
                    "independent_run": "blocked",
                },
                summary={"tests_run": 0, "tests_passed": 0, "tests_failed": 0},
                failures=[{
                    "test": "design_validation",
                    "category": "DESIGN_ERROR",
                    "severity": "critical",
                    "file": "docs/design.json",
                    "message": f"design.json validation failed: {design_val['errors']}",
                    "responsible_agent": "designer_agent",
                    "recommended_action": "Regenerate implementation design.json matching design_schema.json",
                }],
                next_agent="designer_agent",
                next_reason="Implementation design is invalid",
            )
            self._write_test_result(abs_proj, result_payload)
            return result_payload

        plan_data = plan_val["data"]
        design_data = design_val["data"]

        # Step 4 & 5: Structure Verification
        struct = inspect_project(project_path)
        required_files = ["agent.py", "fast_api.py", "app.py", "settings.yaml", "requirements.txt"]
        struct_missing = [f for f in required_files if not os.path.isfile(os.path.join(abs_proj, f))]
        
        struct_check_status = "passed"
        if struct_missing:
            struct_check_status = "failed"
            failures.append({
                "test": "project_structure",
                "category": "IMPLEMENTATION_ERROR",
                "severity": "high",
                "file": "root",
                "message": f"Missing required project files: {struct_missing}",
                "responsible_agent": "coder_agent",
                "recommended_action": "Copy missing template files to generated project",
            })

        # Step 6: Agent Files Verification
        expected_agents = [a["id"] for a in design_data.get("agents", [])]
        agent_check_status = "passed"
        for aid in expected_agents:
            agent_dir = os.path.join(abs_proj, "agents", aid)
            for f_name in ["agent.py", "prompt.py", "tools.py"]:
                if not os.path.isfile(os.path.join(agent_dir, f_name)):
                    agent_check_status = "failed"
                    failures.append({
                        "test": f"agent_{aid}_{f_name}",
                        "category": "IMPLEMENTATION_ERROR",
                        "severity": "high",
                        "file": f"agents/{aid}/{f_name}",
                        "message": f"Required agent file missing: agents/{aid}/{f_name}",
                        "responsible_agent": "coder_agent",
                        "recommended_action": f"Generate agents/{aid}/{f_name} for agent {aid}",
                    })

        # Step 7: Tool Validation
        tools_check_status = "passed"
        for agent_spec in design_data.get("agents", []):
            aid = agent_spec["id"]
            tools_file = os.path.join(abs_proj, "agents", aid, "tools.py")
            if os.path.isfile(tools_file):
                with open(tools_file, "r", encoding="utf-8") as f:
                    code = f.read()
                from backend.tools.coder_tools import sanitize_tool_name
                for tool in agent_spec.get("tools", []):
                    traw = tool.get("name")
                    if traw:
                        tname = sanitize_tool_name(traw)
                        if f"def {tname}" not in code and f"def {traw}" not in code:
                            tools_check_status = "failed"
                            failures.append({
                                "test": f"tool_{aid}_{tname}",
                                "category": "IMPLEMENTATION_ERROR",
                                "severity": "medium",
                                "file": f"agents/{aid}/tools.py",
                                "message": f"Assigned tool '{tname}' not defined in agents/{aid}/tools.py",
                                "responsible_agent": "coder_agent",
                                "recommended_action": f"Implement function {tname} in agents/{aid}/tools.py",
                            })

        # Step 8: Wiring Verification
        wiring_res = check_agent_wiring(project_path)
        wiring_check_status = "passed" if wiring_res["valid"] else "failed"
        if not wiring_res["valid"]:
            failures.append({
                "test": "root_agent_wiring",
                "category": "COMMUNICATION_ERROR",
                "severity": "high",
                "file": "agent.py",
                "message": f"Wiring check failed: {wiring_res['errors']}",
                "responsible_agent": "coder_agent",
                "recommended_action": "Import and wire all plan agents in root agent.py",
            })

        # Step 9: Generate project tests
        self._generate_project_tests(abs_proj, expected_agents)

        # Step 10: Execute tests
        test_suite_res = run_test_suite(project_path)
        tests_check_status = "passed" if test_suite_res["tests_failed"] == 0 else "failed"
        if test_suite_res["tests_failed"] > 0:
            failures.append({
                "test": "pytest_suite",
                "category": "TEST_ERROR",
                "severity": "high",
                "file": "tests/",
                "message": f"{test_suite_res['tests_failed']} tests failed during execution.",
                "responsible_agent": "coder_agent",
                "recommended_action": "Fix failing tests in generated project suite",
            })

        # Step 11: Smoke Test
        smoke_res = run_smoke_test(project_path)
        smoke_check_status = smoke_res["status"]
        if smoke_check_status != "passed":
            failures.append({
                "test": "smoke_test",
                "category": "RUNTIME_ERROR",
                "severity": "high",
                "file": "agent.py",
                "message": f"Smoke test failed: {smoke_res.get('error')}",
                "responsible_agent": "coder_agent",
                "recommended_action": "Ensure root agent and fast_api app initialize cleanly",
            })

        # Step 11b: Sandboxed Terminal Execution & Output Verification
        sandbox_prompt = plan_data.get("project", {}).get("description", "Execute system analysis and report metrics.")
        sandbox_res = run_sandboxed_execution_test(project_path, test_prompt=sandbox_prompt)
        val_out = verify_execution_output(sandbox_res.get("output_payload", ""))

        sandbox_check_status = "passed"
        if sandbox_res["status"] != "passed":
            sandbox_check_status = "failed"
            failures.append({
                "test": "sandboxed_execution",
                "category": "RUNTIME_ERROR",
                "severity": "critical",
                "file": "app.py",
                "message": f"Sandboxed execution failed with error: {sandbox_res.get('error_message')}",
                "responsible_agent": "coder_agent",
                "recommended_action": "Ensure app.py and agent.py execute without runtime exceptions",
            })
        elif not val_out["valid"]:
            sandbox_check_status = "failed"
            failures.append({
                "test": "output_verification",
                "category": val_out.get("reason", "MOCK_OUTPUT_DETECTED"),
                "severity": "high",
                "file": "app.py",
                "message": val_out["message"],
                "responsible_agent": "coder_agent",
                "recommended_action": "Fix app.py/agent.py to properly execute live LLM sub-agent logic and remove hardcoded mock template fallbacks.",
            })

        # Step 12: Vercel Structure
        vercel_res = check_vercel_structure(project_path)
        vercel_check_status = "passed" if vercel_res["valid"] else "failed"
        if not vercel_res["valid"]:
            failures.append({
                "test": "vercel_structure",
                "category": "DEPLOYMENT_STRUCTURE_ERROR",
                "severity": "medium",
                "file": "requirements.txt",
                "message": f"Vercel structure check failed: {vercel_res['errors']}",
                "responsible_agent": "coder_agent",
                "recommended_action": "Provide requirements.txt and API entrypoint for Vercel deployment",
            })

        # Step 13: Secret Exposure Scan
        secret_res = scan_for_secrets(project_path)
        secrets_check_status = "passed" if not secret_res["secrets_found"] else "failed"
        if secret_res["secrets_found"]:
            for sec in secret_res["exposed_secrets"]:
                failures.append({
                    "test": "secret_exposure_scan",
                    "category": "SECURITY_ERROR",
                    "severity": "critical",
                    "file": sec["file"],
                    "message": f"Exposed secret detected ({sec['type']}) in {sec['file']}",
                    "responsible_agent": "coder_agent",
                    "recommended_action": f"Remove hard-coded secret from {sec['file']}",
                })

        # Step 14: Independent Execution Check
        indep_res = check_independent_execution(project_path)
        indep_check_status = "passed" if indep_res["is_independent"] else "failed"
        if not indep_res["is_independent"]:
            for v in indep_res["violations"]:
                failures.append({
                    "test": "independent_execution",
                    "category": "IMPLEMENTATION_ERROR",
                    "severity": "high",
                    "file": v["file"],
                    "message": f"Generated file imports AgentForge builder internal package '{v['forbidden_import']}'",
                    "responsible_agent": "coder_agent",
                    "recommended_action": f"Remove import of {v['forbidden_import']} from {v['file']}",
                })

        # Step 15: Determine Overall Status & Build Payload
        overall_status = "passed" if len(failures) == 0 else "failed"
        next_agent = "github_agent" if overall_status == "passed" else failures[0]["responsible_agent"]
        next_reason = "All validation checks passed" if overall_status == "passed" else failures[0]["message"]

        checks = {
            "plan": "passed",
            "design": "passed",
            "structure": struct_check_status,
            "agents": agent_check_status,
            "tools": tools_check_status,
            "wiring": wiring_check_status,
            "communication": "passed",
            "tests": tests_check_status,
            "smoke_test": smoke_check_status,
            "sandboxed_execution": sandbox_check_status,
            "vercel_structure": vercel_check_status,
            "secrets": secrets_check_status,
            "independent_run": indep_check_status,
        }

        summary = {
            "tests_run": test_suite_res.get("tests_run", 0),
            "tests_passed": test_suite_res.get("tests_passed", 0),
            "tests_failed": test_suite_res.get("tests_failed", 0),
        }

        payload = self._build_result_payload(
            status=overall_status,
            project_path=project_path,
            coder_ctx=coder_ctx,
            checks=checks,
            summary=summary,
            failures=failures,
            next_agent=next_agent,
            next_reason=next_reason,
        )

        self._write_test_result(abs_proj, payload)
        return payload

    def _generate_project_tests(self, abs_proj: str, agents: List[str]):
        """Generate test suite files inside generated project tests/ directory."""
        tests_dir = os.path.join(abs_proj, "tests")
        os.makedirs(tests_dir, exist_ok=True)

        # test_structure.py
        struct_test = """import os
import pytest

def test_root_files():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for fname in ['agent.py', 'fast_api.py', 'app.py', 'settings.yaml', 'requirements.txt']:
        assert os.path.isfile(os.path.join(root, fname))
"""
        create_test_file(abs_proj, "test_structure.py", struct_test)

        # test_agents.py
        agent_imports = "\n".join(f"from agents.{aid}.agent import get_agent as get_{aid}" for aid in agents)
        agent_tests = "\n".join(f"def test_agent_{aid}():\n    ag = get_{aid}()\n    assert ag.name is not None" for aid in agents)
        agents_test_code = f"""import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
{agent_imports}

{agent_tests}
"""
        create_test_file(abs_proj, "test_agents.py", agents_test_code)


    def _build_result_payload(
        self,
        status: str,
        project_path: str,
        coder_ctx: Dict[str, Any],
        checks: Dict[str, str],
        summary: Dict[str, int],
        failures: List[Dict[str, Any]],
        next_agent: str,
        next_reason: str,
    ) -> Dict[str, Any]:
        """Build test_result.json output structure."""
        return {
            "status": status,
            "project_path": project_path,
            "input_context": {
                "coding_status": coder_ctx.get("status", "unknown"),
                "agents_claimed_changed": len(coder_ctx.get("agents_updated", [])),
                "files_modified_count": len(coder_ctx.get("files_modified", [])),
            },
            "summary": summary,
            "checks": checks,
            "failures": failures,
            "next_action": {
                "agent": next_agent,
                "reason": next_reason,
            },
        }

    def _write_test_result(self, abs_proj: str, payload: Dict[str, Any]):
        """Write test_result.json to project docs/ directory."""
        docs_dir = os.path.join(abs_proj, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        target_path = os.path.join(docs_dir, "test_result.json")
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
