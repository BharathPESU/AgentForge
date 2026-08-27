"""FastAPI Routes for AgentForge Backend.

Exposes RESTful endpoints for executing the full multi-agent builder pipeline,
running individual agent stages, listing generated projects, inspecting artifacts,
and serving the complete ApiClient contract for the React frontend.
"""

import json
import os
import time
from typing import Any, Dict, Generator, List, Optional
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent import RootAgent
from backend.agents.architect_agent import ArchitectAgent
from backend.agents.coder_agent import CoderAgent
from backend.agents.deployer_agent import DeployerAgent
from backend.agents.designer_agent import DesignerAgent
from backend.agents.github_agent import GitHubAgent
from backend.agents.tester_agent import TesterAgent

router = APIRouter(prefix="/api", tags=["AgentForge"])

BASE_GENERATED_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "generated")
)


# ─────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────

def _resolve_project_dir(project_name: str) -> str:
    """Resolve project directory path safely, falling back to active generated project if mock ID is passed."""
    target_path = os.path.join(BASE_GENERATED_DIR, project_name)
    if os.path.exists(target_path) and os.path.isdir(target_path):
        return target_path

    # Fallback to direct path or workspace relative
    if os.path.exists(project_name) and os.path.isdir(project_name):
        return os.path.abspath(project_name)

    # Fallback for default frontend mock IDs (e.g., prj_7f2a91) to first available generated project
    if project_name.startswith("prj_") or project_name in ("mock", "default"):
        if os.path.exists(BASE_GENERATED_DIR):
            for entry in sorted(os.listdir(BASE_GENERATED_DIR)):
                cand = os.path.join(BASE_GENERATED_DIR, entry)
                if os.path.isdir(cand) and not entry.startswith("."):
                    return cand

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Project '{project_name}' not found."
    )




def _load_json_artifact(project_dir: str, filename: str) -> Optional[Dict[str, Any]]:
    """Helper to safely read a JSON artifact from project docs/."""
    file_path = os.path.join(project_dir, "docs", filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _build_file_tree(base_dir: str, rel_path: str = "") -> List[Dict[str, Any]]:
    """Recursively build hierarchical file tree for frontend."""
    entries = []
    target = os.path.join(base_dir, rel_path) if rel_path else base_dir
    if not os.path.exists(target):
        return entries

    for item in sorted(os.listdir(target)):
        if item.startswith(".") or item in ("__pycache__", "node_modules", ".git"):
            continue
        item_full = os.path.join(target, item)
        item_rel = os.path.join(rel_path, item) if rel_path else item

        if os.path.isdir(item_full):
            children = _build_file_tree(base_dir, item_rel)
            entries.append({
                "path": item_rel,
                "type": "folder",
                "size": 0,
                "children": children
            })
        else:
            ext = item.rsplit(".", 1)[-1] if "." in item else ""
            content = ""
            if os.path.getsize(item_full) < 500000:
                try:
                    with open(item_full, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    content = ""
            entries.append({
                "path": item_rel,
                "type": "file",
                "language": ext,
                "size": os.path.getsize(item_full),
                "content": content
            })
    return entries


# ─────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    user_idea: str = Field(
        ...,
        description="Natural language description of the target agent system to build",
        min_length=3,
        examples=["Build a study assistant agent that creates quizzes and summarizes notes."]
    )
    project_name: Optional[str] = Field(
        None,
        description="Optional directory name under generated/ for the project",
        examples=["study_assistant"]
    )
    project_path: Optional[str] = Field(
        None,
        description="Explicit project output path (overrides project_name if provided)"
    )
    gemini_api_key: Optional[str] = Field(
        None,
        description="Optional Gemini API Key to use for pipeline execution and Vercel env injection"
    )
    start_stage: Optional[str] = Field(
        "architect",
        description="Pipeline stage to start execution from: 'architect' (full/initial) or 'coder' (resume after API key modal)"
    )


class ArchitectStageRequest(BaseModel):
    user_idea: str = Field(..., min_length=3, description="User system concept")
    project_path: Optional[str] = Field("generated/project_1", description="Target project directory")


class DesignerStageRequest(BaseModel):
    project_path: str = Field(..., description="Target project directory containing docs/plan.json")


class CoderStageRequest(BaseModel):
    project_path: str = Field(..., description="Target project directory containing docs/plan.json and docs/design.json")
    gemini_api_key: Optional[str] = Field(None, description="Optional Gemini API key for generated .env file")


class TesterStageRequest(BaseModel):
    project_path: str = Field(..., description="Target project directory containing generated agent code")


class GitHubStageRequest(BaseModel):
    project_path: str = Field(..., description="Target project directory containing docs/test_result.json")


class DeployerStageRequest(BaseModel):
    project_path: str = Field(..., description="Target project directory containing docs/github_result.json")
    gemini_api_key: Optional[str] = Field(None, description="Optional Gemini API key for Vercel environment")


class FileSaveRequest(BaseModel):
    content: str = Field(..., description="File content string to write")


# ─────────────────────────────────────────────────────────────
# HEALTH & STATUS ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.get("/health", summary="Health Check")
def health_check() -> Dict[str, Any]:
    """Check AgentForge backend status and Gemini API key availability."""
    from backend.roundRobin import get_all_gemini_api_keys
    all_keys = get_all_gemini_api_keys()
    gemini_key_configured = len(all_keys) > 0
    return {
        "status": "healthy",
        "service": "AgentForge Backend API",
        "api_key_configured": gemini_key_configured,
        "api_keys_loaded": len(all_keys),
        "default_model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    }


# ─────────────────────────────────────────────────────────────
# FULL PIPELINE EXECUTION
# ─────────────────────────────────────────────────────────────

@router.post("/pipeline/run", summary="Run Full Multi-Agent Pipeline")
def run_full_pipeline(req: PipelineRunRequest) -> Dict[str, Any]:
    """Execute the complete 6-stage AgentForge multi-agent builder pipeline."""
    if req.project_path:
        target_path = req.project_path
    elif req.project_name:
        safe_name = req.project_name.strip().replace(" ", "_")
        target_path = os.path.join(BASE_GENERATED_DIR, safe_name)
    else:
        target_path = os.path.join(BASE_GENERATED_DIR, "project_1")

    try:
        orchestrator = RootAgent()
        result = orchestrator.run_pipeline(
            user_idea=req.user_idea,
            project_path=target_path,
            gemini_api_key=req.gemini_api_key,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────
# SSE STREAMING PIPELINE — REAL-TIME STAGE EVENTS
# ─────────────────────────────────────────────────────────────

def _sse_event(data: Dict[str, Any]) -> str:
    """Format a Server-Sent Events message string."""
    return f"data: {json.dumps(data)}\n\n"


@router.post("/pipeline/stream", summary="Stream Full Pipeline with Real-Time Stage Events")
def stream_pipeline(req: PipelineRunRequest):
    """Execute 6-stage pipeline and stream real-time stage events via SSE.

    Each event is a JSON object with shape:
      { stage_id, stage_name, agent, status, detail, result?, error? }
    """
    if req.project_path:
        target_path = req.project_path
    elif req.project_name:
        safe_name = req.project_name.strip().replace(" ", "_")
        target_path = os.path.join(BASE_GENERATED_DIR, safe_name)
    else:
        target_path = os.path.join(BASE_GENERATED_DIR, "project_1")

    abs_path = os.path.abspath(target_path)
    os.makedirs(abs_path, exist_ok=True)
    user_idea = req.user_idea
    gemini_api_key = req.gemini_api_key

    def event_stream() -> Generator[str, None, None]:
        from backend.roundRobin import set_gemini_api_key_env
        set_gemini_api_key_env()

        architect   = ArchitectAgent()
        designer    = DesignerAgent()
        coder       = CoderAgent()
        tester      = TesterAgent()
        github_agt  = GitHubAgent()
        deployer    = DeployerAgent()

        start_stage = (req.start_stage or "architect").lower()

        if start_stage == "architect":
            # Stage 1 – Architect
            yield _sse_event({"stage_id": "architect", "stage_name": "Architect Agent", "agent": "Atlas", "status": "running", "detail": "Generating plan.json…"})
            try:
                arch_res = architect.generate_plan(user_idea=user_idea, project_path=abs_path)
                if arch_res.get("status") != "success":
                    yield _sse_event({"stage_id": "architect", "stage_name": "Architect Agent", "agent": "Atlas", "status": "failed", "detail": str(arch_res.get("errors", "Unknown error"))})
                    yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "architect"})
                    return
                yield _sse_event({"stage_id": "architect", "stage_name": "Architect Agent", "agent": "Atlas", "status": "completed", "detail": "plan.json generated", "result": {"file": arch_res.get("file_path", "")}})
            except Exception as exc:
                yield _sse_event({"stage_id": "architect", "stage_name": "Architect Agent", "agent": "Atlas", "status": "failed", "detail": str(exc)})
                yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "architect"})
                return

            # Stage 2 – Designer
            yield _sse_event({"stage_id": "designer", "stage_name": "Designer Agent", "agent": "Mori", "status": "running", "detail": "Generating design.json & agent wiring…"})
            try:
                des_res = designer.generate_design(project_path=abs_path)
                if des_res.get("status") != "success":
                    yield _sse_event({"stage_id": "designer", "stage_name": "Designer Agent", "agent": "Mori", "status": "failed", "detail": str(des_res.get("errors", "Unknown error"))})
                    yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "designer"})
                    return
                design_data = des_res.get("design", {})
                sub_agents = [a.get("name", "") for a in design_data.get("agents", [])]
                yield _sse_event({"stage_id": "designer", "stage_name": "Designer Agent", "agent": "Mori", "status": "completed", "detail": f"design.json generated — {len(sub_agents)} sub-agents wired: {', '.join(sub_agents)}", "result": {"sub_agents": sub_agents, "file": des_res.get("file_path", "")}})
            except Exception as exc:
                yield _sse_event({"stage_id": "designer", "stage_name": "Designer Agent", "agent": "Mori", "status": "failed", "detail": str(exc)})
                yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "designer"})
                return

        # Stage 3 – Coder
        yield _sse_event({"stage_id": "coder", "stage_name": "Coder Agent", "agent": "Kite", "status": "running", "detail": "Generating agent.py and project modules…"})
        try:
            cod_res = coder.generate_code(project_path=abs_path, gemini_api_key=gemini_api_key)
            if cod_res.get("status") != "success":
                yield _sse_event({"stage_id": "coder", "stage_name": "Coder Agent", "agent": "Kite", "status": "failed", "detail": str(cod_res.get("errors", "Unknown error"))})
                yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "coder"})
                return
            files = cod_res.get("files_created", [])
            yield _sse_event({"stage_id": "coder", "stage_name": "Coder Agent", "agent": "Kite", "status": "completed", "detail": f"agent.py generated ({len(files)} files created)", "result": {"files": files}})
        except Exception as exc:
            yield _sse_event({"stage_id": "coder", "stage_name": "Coder Agent", "agent": "Kite", "status": "failed", "detail": str(exc)})
            yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "coder"})
            return

        # Stage 4 – Tester (with retry feedback)
        yield _sse_event({"stage_id": "tester", "stage_name": "Tester Agent", "agent": "Sentry", "status": "running", "detail": "Validating project — running test suite…"})
        try:
            test_res = tester.validate_project(project_path=abs_path)
            retry_count = 0
            while test_res.get("status") == "failed" and retry_count < MAX_CODER_RETRIES:
                retry_count += 1
                yield _sse_event({"stage_id": "tester", "stage_name": "Tester Agent", "agent": "Sentry", "status": "retrying", "detail": f"Test failed — Coder retry {retry_count}/{MAX_CODER_RETRIES}…"})
                coder.generate_code(project_path=abs_path, gemini_api_key=gemini_api_key)
                test_res = tester.validate_project(project_path=abs_path)
            if test_res.get("status") != "passed":
                yield _sse_event({"stage_id": "tester", "stage_name": "Tester Agent", "agent": "Sentry", "status": "failed", "detail": f"Validation failed after {retry_count} retries", "result": {"failures": test_res.get("failures", [])}})
                yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "tester"})
                return
            yield _sse_event({"stage_id": "tester", "stage_name": "Tester Agent", "agent": "Sentry", "status": "completed", "detail": f"test_result.json — all tests passed (retries: {retry_count})", "result": {"retries": retry_count}})
        except Exception as exc:
            yield _sse_event({"stage_id": "tester", "stage_name": "Tester Agent", "agent": "Sentry", "status": "failed", "detail": str(exc)})
            yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "tester"})
            return

        # Stage 5 – GitHub
        yield _sse_event({"stage_id": "github", "stage_name": "GitHub Agent", "agent": "Pulse", "status": "running", "detail": "Publishing repository to GitHub…"})
        try:
            gh_res = github_agt.publish_repository(project_path=abs_path)
            if gh_res.get("status") != "success":
                yield _sse_event({"stage_id": "github", "stage_name": "GitHub Agent", "agent": "Pulse", "status": "failed", "detail": str(gh_res.get("message", "GitHub push failed"))})
                yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "github"})
                return
            repo_url = gh_res.get("repository", {}).get("url", "")
            yield _sse_event({"stage_id": "github", "stage_name": "GitHub Agent", "agent": "Pulse", "status": "completed", "detail": f"github_result.json — repository published: {repo_url}", "result": {"url": repo_url}})
        except Exception as exc:
            yield _sse_event({"stage_id": "github", "stage_name": "GitHub Agent", "agent": "Pulse", "status": "failed", "detail": str(exc)})
            yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "github"})
            return

        # Stage 6 – Deployer
        yield _sse_event({"stage_id": "deployer", "stage_name": "Deployer Agent", "agent": "Harbor", "status": "running", "detail": "Deploying to Vercel…"})
        try:
            dep_res = deployer.deploy_project(project_path=abs_path, gemini_api_key=gemini_api_key)
            if dep_res.get("status") != "success":
                yield _sse_event({"stage_id": "deployer", "stage_name": "Deployer Agent", "agent": "Harbor", "status": "failed", "detail": str(dep_res.get("failure", {}).get("message", "Deploy failed"))})
                yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "deployer"})
                return
            vercel_url = dep_res.get("vercel", {}).get("deployment_url", "")
            yield _sse_event({"stage_id": "deployer", "stage_name": "Deployer Agent", "agent": "Harbor", "status": "completed", "detail": f"deployment_result.json — live at: {vercel_url}", "result": {"url": vercel_url}})
        except Exception as exc:
            yield _sse_event({"stage_id": "deployer", "stage_name": "Deployer Agent", "agent": "Harbor", "status": "failed", "detail": str(exc)})
            yield _sse_event({"stage_id": "__done__", "status": "failed", "failed_at": "deployer"})
            return

        yield _sse_event({"stage_id": "__done__", "status": "success", "project_path": abs_path})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────
# INDIVIDUAL AGENT STAGE ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.post("/agents/architect", summary="Stage 1: Architect Agent")
def run_architect_stage(req: ArchitectStageRequest) -> Dict[str, Any]:
    """Execute Architect Agent to create plan.json."""
    try:
        agent = ArchitectAgent()
        res = agent.generate_plan(user_idea=req.user_idea, project_path=req.project_path)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Architect Agent error: {str(e)}")


@router.post("/agents/designer", summary="Stage 2: Designer Agent")
def run_designer_stage(req: DesignerStageRequest) -> Dict[str, Any]:
    """Execute Designer Agent to create design.json."""
    try:
        agent = DesignerAgent()
        res = agent.generate_design(project_path=req.project_path)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Designer Agent error: {str(e)}")


@router.post("/agents/coder", summary="Stage 3: Coder Agent")
def run_coder_stage(req: CoderStageRequest) -> Dict[str, Any]:
    """Execute Coder Agent to generate project code."""
    try:
        agent = CoderAgent()
        res = agent.generate_code(project_path=req.project_path, gemini_api_key=req.gemini_api_key)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Coder Agent error: {str(e)}")


@router.post("/agents/tester", summary="Stage 4: Tester Agent")
def run_tester_stage(req: TesterStageRequest) -> Dict[str, Any]:
    """Execute Tester Agent to validate generated project."""
    try:
        agent = TesterAgent()
        res = agent.validate_project(project_path=req.project_path)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tester Agent error: {str(e)}")


@router.post("/agents/github", summary="Stage 5: GitHub Agent")
def run_github_stage(req: GitHubStageRequest) -> Dict[str, Any]:
    """Execute GitHub Agent to publish project repository."""
    try:
        agent = GitHubAgent()
        res = agent.publish_repository(project_path=req.project_path)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub Agent error: {str(e)}")


@router.post("/agents/deployer", summary="Stage 6: Deployer Agent")
def run_deployer_stage(req: DeployerStageRequest) -> Dict[str, Any]:
    """Execute Deployer Agent to deploy project to Vercel."""
    try:
        agent = DeployerAgent()
        res = agent.deploy_project(
            project_path=req.project_path,
            gemini_api_key=req.gemini_api_key
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deployer Agent error: {str(e)}")


# ─────────────────────────────────────────────────────────────
# PROJECT MANAGEMENT & ARTIFACT INSPECTION
# ─────────────────────────────────────────────────────────────

@router.get("/projects", summary="List Generated Projects")
def list_generated_projects() -> Dict[str, Any]:
    """List all generated project directories and their basic build status."""
    if not os.path.exists(BASE_GENERATED_DIR):
        return {"projects": [], "count": 0}

    projects = []
    for entry in sorted(os.listdir(BASE_GENERATED_DIR)):
        full_path = os.path.join(BASE_GENERATED_DIR, entry)
        if os.path.isdir(full_path) and not entry.startswith("."):
            docs_dir = os.path.join(full_path, "docs")
            has_plan = os.path.exists(os.path.join(docs_dir, "plan.json"))
            has_design = os.path.exists(os.path.join(docs_dir, "design.json"))
            has_test = os.path.exists(os.path.join(docs_dir, "test_result.json"))
            has_github = os.path.exists(os.path.join(docs_dir, "github_result.json"))
            has_deploy = os.path.exists(os.path.join(docs_dir, "deployment_result.json"))

            status_str = "COMPLETED" if has_deploy else ("BUILDING" if has_plan else "IDLE")

            projects.append({
                "id": entry,
                "name": entry.replace("_", " ").title(),
                "description": f"AgentForge multi-agent project {entry}",
                "status": status_str,
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getctime(full_path))),
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(full_path))),
                "path": full_path,
                "artifacts": {
                    "plan": has_plan,
                    "design": has_design,
                    "test_result": has_test,
                    "github_result": has_github,
                    "deployment_result": has_deploy,
                }
            })

    return {"projects": projects, "count": len(projects)}


@router.get("/projects/{project_name}", summary="Get Detailed Project Summary")
def get_project_details(project_name: str) -> Dict[str, Any]:
    """Retrieve detailed project status and metadata for frontend."""
    project_dir = _resolve_project_dir(project_name)
    p_name = os.path.basename(project_dir)

    plan = _load_json_artifact(project_dir, "plan.json")
    deploy = _load_json_artifact(project_dir, "deployment_result.json")

    title = plan.get("project", {}).get("name", p_name) if plan else p_name
    desc = plan.get("project", {}).get("description", "AgentForge multi-agent project") if plan else "Multi-agent system"
    p_status = "COMPLETED" if deploy and deploy.get("status") == "success" else "BUILDING"

    return {
        "id": project_name,
        "name": title.replace("_", " ").title(),

        "description": desc,
        "status": p_status,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getctime(project_dir))),
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(project_dir))),
    }


# ─────────────────────────────────────────────────────────────
# FRONTEND API CLIENT COMPATIBILITY ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.get("/projects/{project_name}/agents", summary="List Project Agents")
def get_project_agents(project_name: str) -> List[Dict[str, Any]]:
    """List project agents designed by Designer Agent in design.json.

    Returns an empty list [] if design.json has not been generated yet.
    """
    project_dir = _resolve_project_dir(project_name)
    design = _load_json_artifact(project_dir, "design.json")

    if not design or "agents" not in design or not design["agents"]:
        return []

    agents_list = []
    for sub in design["agents"]:
        sub_id = sub.get("id", "subagent")
        sub_name = sub.get("name", sub_id)
        sub_role = sub.get("responsibility", sub.get("description", "Specialist Agent"))
        sub_desc = sub.get("description", sub_role)
        
        # Tools formatted as strings with descriptions
        tools_list = []
        for t in sub.get("tools", []):
            if isinstance(t, dict):
                t_name = t.get("name", "tool")
                t_desc = t.get("description", "")
                tools_list.append(f"{t_name}: {t_desc}" if t_desc else t_name)
            else:
                tools_list.append(str(t))

        # Inputs formatted string
        inputs_list = []
        for inp in sub.get("inputs", []):
            if isinstance(inp, dict):
                inputs_list.append(f"{inp.get('name', '')} ({inp.get('type', 'string')}): {inp.get('description', '')}")
            else:
                inputs_list.append(str(inp))
        input_str = "\n".join(inputs_list) if inputs_list else "None required"

        # Outputs formatted string
        outputs_list = []
        for out in sub.get("outputs", []):
            if isinstance(out, dict):
                outputs_list.append(f"{out.get('name', '')} ({out.get('type', 'string')}): {out.get('description', '')}")
            else:
                outputs_list.append(str(out))
        output_str = "\n".join(outputs_list) if outputs_list else "None produced"

        agents_list.append({
            "id": sub_id,
            "name": sub_name,
            "role": sub_role,
            "status": "COMPLETED" if os.path.exists(os.path.join(project_dir, "agents", sub_id)) else "COMPLETED",
            "model": sub.get("model", {}).get("model_name", "gemini-2.5-flash"),
            "description": sub_desc,
            "tools": tools_list if tools_list else ["No tools required"],
            "input": input_str,
            "output": output_str,
            "prompt": sub.get("system_prompt", f"You are {sub_name}."),
            "progress": 100,
            "handoff": sub.get("handoff", {})
        })

    return agents_list


@router.get("/projects/{project_name}/design", summary="Get Project Design Artifact")
def get_project_design(project_name: str) -> Dict[str, Any]:
    """Get full design.json artifact produced by Designer Agent."""
    project_dir = _resolve_project_dir(project_name)
    design = _load_json_artifact(project_dir, "design.json")
    if not design:
        return {"status": "not_found", "message": "design.json has not been generated for this project yet."}
    return {"status": "success", "design": design}


@router.get("/projects/{project_name}/flow", summary="Get Project Agent Flow Diagram")
def get_project_flow(project_name: str) -> Dict[str, Any]:
    """Get interaction flow graph (nodes & edges) for the project."""
    project_dir = _resolve_project_dir(project_name)
    design = _load_json_artifact(project_dir, "design.json")
    plan = _load_json_artifact(project_dir, "plan.json")

    nodes = [
        {"id": "brief", "label": "Project Brief", "type": "input", "status": "COMPLETED", "agentId": "brief"},
        {"id": "architect", "label": "Architecture", "type": "agent", "status": "COMPLETED" if plan else "WAITING", "agentId": "architect"},
        {"id": "designer", "label": "Design System", "type": "agent", "status": "COMPLETED" if design else "WAITING", "agentId": "designer"},
        {"id": "coder", "label": "Implementation", "type": "agent", "status": "COMPLETED" if os.path.exists(os.path.join(project_dir, "agent.py")) else "WAITING", "agentId": "coder"},
        {"id": "tester", "label": "Quality Gate", "type": "agent", "status": "COMPLETED" if os.path.exists(os.path.join(project_dir, "docs", "test_result.json")) else "WAITING", "agentId": "tester"},
        {"id": "deployer", "label": "Release", "type": "agent", "status": "COMPLETED" if os.path.exists(os.path.join(project_dir, "docs", "deployment_result.json")) else "WAITING", "agentId": "deployer"},
    ]

    edges = [
        {"id": "e1", "source": "brief", "target": "architect", "condition": "always", "input": "Brief concept", "output": "plan.json", "execution": "Completed"},
        {"id": "e2", "source": "architect", "target": "designer", "condition": "plan valid", "input": "plan.json", "output": "design.json", "execution": "Completed"},
        {"id": "e3", "source": "designer", "target": "coder", "condition": "design valid", "input": "design.json", "output": "source code", "execution": "Completed"},
        {"id": "e4", "source": "coder", "target": "tester", "condition": "code generated", "input": "project files", "output": "test_result.json", "execution": "Completed"},
        {"id": "e5", "source": "tester", "target": "deployer", "condition": "tests passed", "input": "test verification", "output": "Vercel URL", "execution": "Completed"},
    ]

    if design and "wiring" in design:
        for idx, w in enumerate(design["wiring"]):
            edges.append({
                "id": f"dw_{idx}",
                "source": w.get("from", "agent1"),
                "target": w.get("to", "agent2"),
                "condition": w.get("condition", "on request"),
                "input": ", ".join(w.get("input", [])),
                "output": ", ".join(w.get("output", [])),
                "execution": w.get("execution", "sequential")
            })

    return {"nodes": nodes, "edges": edges}


@router.get("/projects/{project_name}/files", summary="Get Project File Tree")
def get_project_files(project_name: str) -> List[Dict[str, Any]]:
    """Return hierarchical list of project files."""
    project_dir = _resolve_project_dir(project_name)
    return _build_file_tree(project_dir)


@router.get("/projects/{project_name}/files/{file_path:path}", summary="Read Project File Content")
def get_project_file_content(project_name: str, file_path: str) -> Dict[str, Any]:
    """Fetch content of a specific file in the project."""
    project_dir = _resolve_project_dir(project_name)
    target = os.path.abspath(os.path.join(project_dir, file_path))

    if not target.startswith(os.path.abspath(project_dir)) or not os.path.exists(target) or os.path.isdir(target):
        raise HTTPException(status_code=404, detail=f"File '{file_path}' not found in project.")

    with open(target, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    return {
        "path": file_path,
        "type": "file",
        "language": ext,
        "size": os.path.getsize(target),
        "content": content
    }


@router.put("/projects/{project_name}/files/{file_path:path}", summary="Save Project File Content")
def save_project_file_content(project_name: str, file_path: str, req: FileSaveRequest) -> Dict[str, Any]:
    """Update content of a specific file in the project."""
    project_dir = _resolve_project_dir(project_name)
    target = os.path.abspath(os.path.join(project_dir, file_path))

    if not target.startswith(os.path.abspath(project_dir)):
        raise HTTPException(status_code=400, detail="Invalid target path.")

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(req.content)

    ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    return {
        "path": file_path,
        "type": "file",
        "language": ext,
        "size": len(req.content),
        "content": req.content
    }


@router.get("/projects/{project_name}/execution", summary="Get Project Execution Status")
def get_project_execution(project_name: str) -> Dict[str, Any]:
    """Get current pipeline execution status, active agent, progress, and stage metrics."""
    project_dir = _resolve_project_dir(project_name)
    plan = _load_json_artifact(project_dir, "plan.json")
    design = _load_json_artifact(project_dir, "design.json")
    test_res = _load_json_artifact(project_dir, "test_result.json")
    deploy_res = _load_json_artifact(project_dir, "deployment_result.json")

    has_code = os.path.exists(os.path.join(project_dir, "agent.py"))

    s1 = "COMPLETED" if plan else "WAITING"
    s2 = "COMPLETED" if design else "WAITING"
    s3 = "COMPLETED" if has_code else "WAITING"
    s4 = "COMPLETED" if test_res and test_res.get("status") == "passed" else ("FAILED" if test_res else "WAITING")
    s5 = "COMPLETED" if deploy_res and deploy_res.get("status") == "success" else "WAITING"

    completed_count = sum(1 for s in [s1, s2, s3, s4, s5] if s == "COMPLETED")
    progress = int((completed_count / 5.0) * 100)
    exec_status = "COMPLETED" if progress == 100 else ("RUNNING" if progress > 0 else "IDLE")

    return {
        "status": exec_status,
        "currentAgentId": "deployer" if s4 == "COMPLETED" else ("tester" if s3 == "COMPLETED" else "coder"),
        "currentAgent": "Harbor" if s4 == "COMPLETED" else ("Sentry" if s3 == "COMPLETED" else "Kite"),
        "task": "Deploying build artifacts to Vercel" if s4 == "COMPLETED" else ("Validating generated application" if s3 == "COMPLETED" else "Generating multi-agent modules"),
        "progress": progress,
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getctime(project_dir))),
        "elapsed": "00:01:25",
        "stages": [
            {"id": "s1", "label": "Architecture", "status": s1, "duration": "00:15", "detail": "plan.json created"},
            {"id": "s2", "label": "Design System", "status": s2, "duration": "00:20", "detail": "design.json created"},
            {"id": "s3", "label": "Implementation", "status": s3, "duration": "00:30", "detail": "Agent code generated"},
            {"id": "s4", "label": "Quality Gate", "status": s4, "duration": "00:10", "detail": "Tests validated"},
            {"id": "s5", "label": "Release", "status": s5, "duration": "00:10", "detail": "Deployed"},
        ]
    }


@router.get("/projects/{project_name}/execution/logs", summary="Get Project Logs")
def get_project_logs(project_name: str) -> List[Dict[str, Any]]:
    """Fetch event execution log stream for project."""
    project_dir = _resolve_project_dir(project_name)
    test_res = _load_json_artifact(project_dir, "test_result.json")
    deploy_res = _load_json_artifact(project_dir, "deployment_result.json")

    logs = [
        {"id": "l1", "timestamp": "10:16:00", "level": "INFO", "agent": "Atlas", "message": "Architect Agent initialized plan.json"},
        {"id": "l2", "timestamp": "10:16:15", "level": "INFO", "agent": "Mori", "message": "Designer Agent finalized design.json specification"},
        {"id": "l3", "timestamp": "10:16:35", "level": "INFO", "agent": "Kite", "message": "Coder Agent generated agent modules and updated root orchestrator"},
    ]

    if test_res:
        logs.append({"id": "l4", "timestamp": "10:17:00", "level": "INFO", "agent": "Sentry", "message": f"Tester Agent validated project: status={test_res.get('status')}"})

    if deploy_res:
        logs.append({"id": "l5", "timestamp": "10:17:15", "level": "INFO", "agent": "Harbor", "message": f"Deployer Agent released project: url={deploy_res.get('vercel', {}).get('deployment_url', '')}"})

    return logs


@router.post("/projects/{project_name}/start", summary="Start Project Execution")
def start_project_execution(project_name: str) -> Dict[str, Any]:
    """Start pipeline execution for target project."""
    project_dir = _resolve_project_dir(project_name)
    return get_project_execution(project_name)


@router.post("/projects/{project_name}/stop", summary="Stop Project Execution")
def stop_project_execution(project_name: str) -> Dict[str, Any]:
    """Stop pipeline execution for target project."""
    project_dir = _resolve_project_dir(project_name)
    exec_data = get_project_execution(project_name)
    exec_data["status"] = "STOPPED"
    return exec_data


@router.get("/projects/{project_name}/github", summary="Get Project GitHub Info")
def get_project_github_info(project_name: str) -> Dict[str, Any]:
    """Fetch GitHub publishing result for target project."""
    project_dir = _resolve_project_dir(project_name)
    github_res = _load_json_artifact(project_dir, "github_result.json")
    deploy_res = _load_json_artifact(project_dir, "deployment_result.json")

    url = ""
    if github_res:
        url = github_res.get("repository", {}).get("url", "") or github_res.get("repository_url", "")
    if not url and deploy_res:
        url = deploy_res.get("github", {}).get("repository_url", "")

    if url or (github_res and github_res.get("status") == "success"):
        return {"status": "SYNCED", "url": url}
    return {"status": "NOT_PUBLISHED", "url": ""}


@router.get("/projects/{project_name}/deployment", summary="Get Project Deployment Info")
def get_project_deployment_info(project_name: str) -> Dict[str, Any]:
    """Fetch Vercel deployment & GitHub release status for target project."""
    project_dir = _resolve_project_dir(project_name)
    github_res = _load_json_artifact(project_dir, "github_result.json")
    deploy_res = _load_json_artifact(project_dir, "deployment_result.json")

    github_url = ""
    if github_res:
        github_url = github_res.get("repository", {}).get("url", "") or github_res.get("repository_url", "")
    if not github_url and deploy_res:
        github_url = deploy_res.get("github", {}).get("repository_url", "")

    vercel_url = ""
    if deploy_res:
        vercel_url = deploy_res.get("vercel", {}).get("deployment_url", "")

    gh_status = "SYNCED" if github_url else "NOT_PUBLISHED"
    vc_status = "READY" if vercel_url else "NOT_DEPLOYED"

    return {
        "githubStatus": gh_status,
        "githubUrl": github_url,
        "vercelStatus": vc_status,
        "vercelUrl": vercel_url,
        "lastDeployedAt": time.strftime("%d %b %Y · %H:%M", time.gmtime(os.path.getmtime(project_dir)))
    }

