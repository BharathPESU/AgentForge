"""Master Root Orchestrator Agent for AgentForge using Google ADK."""

import json
import os
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import google.adk as adk

from backend.agents.architect_agent import ArchitectAgent
from backend.agents.coder_agent import CoderAgent
from backend.agents.deployer_agent import DeployerAgent
from backend.agents.designer_agent import DesignerAgent
from backend.agents.github_agent import GitHubAgent
from backend.agents.tester_agent import TesterAgent

from backend.roundRobin import set_gemini_api_key_env

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

MAX_CODER_RETRIES = 3


class RootAgent:
    """Master Orchestrator Agent that wires and manages the complete 6-stage
    AgentForge builder pipeline:
    
    1. Architect Agent -> plan.json
    2. Designer Agent -> design.json
    3. Coder Agent -> generated project
    4. Tester Agent -> test_result.json (with retry loop back to Coder)
    5. GitHub Agent -> github_result.json
    6. Deployer Agent -> deployment_result.json
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        architect_agent: Optional[ArchitectAgent] = None,
        designer_agent: Optional[DesignerAgent] = None,
        coder_agent: Optional[CoderAgent] = None,
        tester_agent: Optional[TesterAgent] = None,
        github_agent: Optional[GitHubAgent] = None,
        deployer_agent: Optional[DeployerAgent] = None,
    ):
        self.model_name = model_name or DEFAULT_MODEL
        self.architect = architect_agent or ArchitectAgent(model_name=self.model_name)
        self.designer = designer_agent or DesignerAgent(model_name=self.model_name)
        self.coder = coder_agent or CoderAgent(model_name=self.model_name)
        self.tester = tester_agent or TesterAgent(model_name=self.model_name)
        self.github = github_agent or GitHubAgent(model_name=self.model_name)
        self.deployer = deployer_agent or DeployerAgent(model_name=self.model_name)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        """Instantiate Google ADK Master Agent."""
        return adk.Agent(
            name="root_agent",
            description="AgentForge Master Orchestrator Agent for end-to-end multi-agent system building",
            model=self.model_name,
            instruction="You are the Master Orchestrator Agent of AgentForge. You coordinate the 6-agent builder pipeline.",
        )

    def run_pipeline(
        self,
        user_idea: str,
        project_path: str = "generated/project_1",
        gemini_api_key: Optional[str] = None,
        override_architect_plan: Optional[Dict[str, Any]] = None,
        override_designer_design: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute end-to-end multi-agent builder pipeline.
        
        Args:
            user_idea: Natural language description of target agent system.
            project_path: Output directory for generated project.
            gemini_api_key: Optional Gemini API key for Vercel deployment env var.
            override_architect_plan: Optional mock plan dict for testing.
            override_designer_design: Optional mock design dict for testing.
            
        Returns:
            Dict containing full pipeline execution metrics, github/vercel URLs, and status.
        """
        start_time = time.time()
        set_gemini_api_key_env()
        abs_project_path = os.path.abspath(project_path)
        project_name = os.path.basename(abs_project_path.rstrip("/\\"))

        os.makedirs(abs_project_path, exist_ok=True)

        # Initialize shared run context
        from backend.services.context_service import ContextService
        ContextService.create_run_context(project_name=project_name, user_idea=user_idea)

        pipeline_log: List[Dict[str, Any]] = []

        # ─────────────────────────────────────────────────────────
        # STAGE 1: ARCHITECT AGENT
        # ─────────────────────────────────────────────────────────
        ContextService.set_current_stage(project_name, "architect")
        if override_architect_plan is not None:
            architect_res = {
                "status": "success",
                "plan": override_architect_plan,
                "file_path": os.path.join(abs_project_path, "docs", "plan.json"),
            }
        else:
            architect_res = self.architect.generate_plan(
                user_idea=user_idea, project_path=abs_project_path
            )

        pipeline_log.append({"stage": "architecture", "result": architect_res})
        if architect_res.get("status") != "success":
            ContextService.record_stage_status(project_name, "architect", "failed")
            return self._build_pipeline_failure(
                failed_stage="architecture",
                message=f"Architect Agent failed: {architect_res.get('errors')}",
                pipeline_log=pipeline_log,
                duration=time.time() - start_time,
            )

        plan_file = architect_res.get("file_path") or os.path.join(abs_project_path, "docs", "plan.json")
        ContextService.record_stage_status(project_name, "architect", "completed")
        ContextService.record_artifact(
            project_name=project_name,
            artifact_type="plan",
            file_path=plan_file,
            stage="architect",
            status="completed",
            summary="Architect Agent created system plan.",
        )

        # ─────────────────────────────────────────────────────────
        # STAGE 2: DESIGNER AGENT
        # ─────────────────────────────────────────────────────────
        ContextService.set_current_stage(project_name, "designer")
        if override_designer_design is not None:
            designer_res = {
                "status": "success",
                "design": override_designer_design,
                "file_path": os.path.join(abs_project_path, "docs", "design.json"),
            }
        else:
            designer_res = self.designer.generate_design(project_path=abs_project_path)

        pipeline_log.append({"stage": "design", "result": designer_res})
        if designer_res.get("status") != "success":
            ContextService.record_stage_status(project_name, "designer", "failed")
            return self._build_pipeline_failure(
                failed_stage="design",
                message=f"Designer Agent failed: {designer_res.get('errors')}",
                pipeline_log=pipeline_log,
                duration=time.time() - start_time,
            )

        design_file = designer_res.get("file_path") or os.path.join(abs_project_path, "docs", "design.json")
        ContextService.record_stage_status(project_name, "designer", "completed")
        ContextService.record_artifact(
            project_name=project_name,
            artifact_type="design",
            file_path=design_file,
            stage="designer",
            status="completed",
            summary="Designer Agent generated system design.",
        )

        # ─────────────────────────────────────────────────────────
        # STAGE 3: CODER AGENT
        # ─────────────────────────────────────────────────────────
        ContextService.set_current_stage(project_name, "coder")
        coder_res = self.coder.generate_code(project_path=abs_project_path)
        pipeline_log.append({"stage": "coding", "result": coder_res})
        if coder_res.get("status") != "success":
            ContextService.record_stage_status(project_name, "coder", "failed")
            return self._build_pipeline_failure(
                failed_stage="coding",
                message=f"Coder Agent failed: {coder_res.get('errors')}",
                pipeline_log=pipeline_log,
                duration=time.time() - start_time,
            )

        coder_file = os.path.join(abs_project_path, "docs", "coder_result.json")
        ContextService.record_stage_status(project_name, "coder", "completed")
        ContextService.record_artifact(
            project_name=project_name,
            artifact_type="coder_result",
            file_path=coder_file,
            stage="coder",
            status="completed",
            summary="Coder Agent generated Google ADK Python application code.",
        )

        # ─────────────────────────────────────────────────────────
        # STAGE 4: TESTER AGENT (WITH RETRY FEEDBACK LOOP TO CODER)
        # ─────────────────────────────────────────────────────────
        ContextService.set_current_stage(project_name, "tester")
        tester_res = self.tester.validate_project(project_path=abs_project_path)
        retry_count = 0

        while (
            tester_res.get("status") == "failed"
            and retry_count < MAX_CODER_RETRIES
        ):
            retry_count += 1
            ContextService.append_event(
                project_name=project_name,
                stage="tester",
                status="retrying",
                summary=f"Validation failed. Retrying Coder stage (attempt {retry_count + 1})",
                attempt=retry_count + 1,
            )
            # Feedback loop: Coder Agent re-executes code generation
            coder_retry_res = self.coder.generate_code(project_path=abs_project_path)
            tester_res = self.tester.validate_project(project_path=abs_project_path)
            pipeline_log.append({
                "stage": f"testing_retry_{retry_count}",
                "coder_result": coder_retry_res,
                "tester_result": tester_res,
            })

        pipeline_log.append({"stage": "testing", "result": tester_res, "retries": retry_count})
        if tester_res.get("status") != "passed":
            ContextService.record_stage_status(project_name, "tester", "failed")
            next_agent = tester_res.get("next_action", {}).get("agent", "coder_agent")
            return self._build_pipeline_failure(
                failed_stage="testing",
                message=f"Tester Agent validation failed after {retry_count} retries.",
                failures=tester_res.get("failures", []),
                next_action_agent=next_agent,
                pipeline_log=pipeline_log,
                duration=time.time() - start_time,
            )

        test_file = os.path.join(abs_project_path, "docs", "test_result.json")
        ContextService.record_stage_status(project_name, "tester", "completed")
        ContextService.record_artifact(
            project_name=project_name,
            artifact_type="test_result",
            file_path=test_file,
            stage="tester",
            status="completed",
            summary="Tester Agent passed 15-step validation suite.",
        )

        # ─────────────────────────────────────────────────────────
        # STAGE 5: GITHUB AGENT
        # ─────────────────────────────────────────────────────────
        ContextService.set_current_stage(project_name, "github")
        github_res = self.github.publish_repository(project_path=abs_project_path)
        pipeline_log.append({"stage": "github", "result": github_res})
        if github_res.get("status") != "success":
            ContextService.record_stage_status(project_name, "github", "failed")
            return self._build_pipeline_failure(
                failed_stage="github",
                message=f"GitHub Agent failed: {github_res.get('message')}",
                pipeline_log=pipeline_log,
                duration=time.time() - start_time,
            )

        gh_file = os.path.join(abs_project_path, "docs", "github_result.json")
        ContextService.record_stage_status(project_name, "github", "completed")
        ContextService.record_artifact(
            project_name=project_name,
            artifact_type="github_result",
            file_path=gh_file,
            stage="github",
            status="completed",
            summary="GitHub Agent created remote repository and pushed codebase.",
        )

        # ─────────────────────────────────────────────────────────
        # STAGE 6: DEPLOYER AGENT
        # ─────────────────────────────────────────────────────────
        ContextService.set_current_stage(project_name, "deployer")
        deployer_res = self.deployer.deploy_project(
            project_path=abs_project_path, gemini_api_key=gemini_api_key
        )
        pipeline_log.append({"stage": "deployment", "result": deployer_res})
        if deployer_res.get("status") != "success":
            ContextService.record_stage_status(project_name, "deployer", "failed")
            return self._build_pipeline_failure(
                failed_stage="deployment",
                message=f"Deployer Agent failed: {deployer_res.get('failure', {}).get('message')}",
                pipeline_log=pipeline_log,
                duration=time.time() - start_time,
            )

        dep_file = os.path.join(abs_project_path, "docs", "deployment_result.json")
        ContextService.record_stage_status(project_name, "deployer", "completed")
        ContextService.record_artifact(
            project_name=project_name,
            artifact_type="deployment_result",
            file_path=dep_file,
            stage="deployer",
            status="completed",
            summary="Deployer Agent deployed project to Vercel.",
        )
        ContextService.set_current_stage(project_name, "completed")

        # ─────────────────────────────────────────────────────────
        # FINAL SUCCESS PAYLOAD
        # ─────────────────────────────────────────────────────────
        github_url = deployer_res.get("github", {}).get("repository_url", "")
        vercel_url = deployer_res.get("vercel", {}).get("deployment_url", "")
        duration = round(time.time() - start_time, 2)

        summary_text = (
            f"Agent system deployed successfully.\n\n"
            f"GitHub:\n{github_url}\n\n"
            f"Vercel:\n{vercel_url}"
        )

        return {
            "status": "success",
            "project_path": project_path,
            "github_url": github_url,
            "vercel_url": vercel_url,
            "summary": summary_text,
            "duration_seconds": duration,
            "retries_performed": retry_count,
            "stages_completed": ["architecture", "design", "coding", "testing", "github", "deployment"],
            "pipeline_log": pipeline_log,
        }

    def _build_pipeline_failure(
        self,
        failed_stage: str,
        message: str,
        pipeline_log: List[Dict[str, Any]],
        duration: float,
        failures: Optional[List[Dict[str, Any]]] = None,
        next_action_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format standard pipeline failure output."""
        return {
            "status": "failed",
            "failed_stage": failed_stage,
            "message": message,
            "failures": failures or [],
            "next_action": {
                "agent": next_action_agent or f"{failed_stage}_agent",
                "reason": message,
            },
            "duration_seconds": round(duration, 2),
            "pipeline_log": pipeline_log,
        }


def run_pipeline(
    user_idea: str,
    project_path: str = "generated/project_1",
    gemini_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper function to run the AgentForge master root pipeline."""
    orchestrator = RootAgent()
    return orchestrator.run_pipeline(
        user_idea=user_idea,
        project_path=project_path,
        gemini_api_key=gemini_api_key,
    )
