"""Master Root Orchestrator Agent for AgentForge — Whiteboard + Supervisor."""

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
from backend.agents.supervisor_agent import SupervisorAgent, MAX_SUPERVISOR_STEPS, MAX_AGENT_RETRIES
from backend.context.manager import WhiteboardManager
from backend.context.selector import WhiteboardContextSelector
from backend.context.models import ArtifactReference
from backend.context import events
from backend.roundRobin import set_gemini_api_key_env

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Keep for backward compat with old tests that check constant
MAX_CODER_RETRIES = MAX_AGENT_RETRIES


class RootAgent:
    """Master Orchestrator using Shared Whiteboard + Supervisor routing.

    Pipeline: USER -> SUPERVISOR -> WHITEBOARD -> SPECIALIST -> WHITEBOARD -> SUPERVISOR ...

    Each specialist does:
        READ WHITEBOARD -> PERFORM TASK -> WRITE RESULT TO WHITEBOARD -> RETURN TO SUPERVISOR
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
        supervisor_agent: Optional[SupervisorAgent] = None,
    ):
        self.model_name = model_name or DEFAULT_MODEL
        self.architect = architect_agent or ArchitectAgent(model_name=self.model_name)
        self.designer = designer_agent or DesignerAgent(model_name=self.model_name)
        self.coder = coder_agent or CoderAgent(model_name=self.model_name)
        self.tester = tester_agent or TesterAgent(model_name=self.model_name)
        self.github = github_agent or GitHubAgent(model_name=self.model_name)
        self.deployer = deployer_agent or DeployerAgent(model_name=self.model_name)
        self.supervisor = supervisor_agent or SupervisorAgent(model_name=self.model_name)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        return adk.Agent(
            name="root_agent",
            description="AgentForge Master Orchestrator Agent for end-to-end multi-agent system building",
            model=self.model_name,
            instruction="You are the Master Orchestrator Agent of AgentForge. You coordinate the 6-agent builder pipeline via the shared Whiteboard and Supervisor.",
        )

    def run_pipeline(
        self,
        user_idea: str,
        project_path: str = "generated/project_1",
        gemini_api_key: Optional[str] = None,
        override_architect_plan: Optional[Dict[str, Any]] = None,
        override_designer_design: Optional[Dict[str, Any]] = None,
        cancel_event: Optional[Any] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_time = time.time()
        set_gemini_api_key_env()
        abs_project_path = os.path.abspath(project_path)
        project_name = os.path.basename(abs_project_path.rstrip("/\\"))
        os.makedirs(abs_project_path, exist_ok=True)

        # Backward compatible: also keep ContextService for observability if needed
        try:
            from backend.services.context_service import ContextService
            ContextService.create_run_context(project_name=project_name, user_idea=user_idea)
        except Exception:
            pass

        # Create shared whiteboard run (use provided run_id for API cancel correlation)
        board = WhiteboardManager.create_run(
            project_id=project_name,
            project_path=abs_project_path,
            user_idea=user_idea,
            run_id=run_id,
        )
        run_id = board.read().run_id
        pipeline_log: List[Dict[str, Any]] = []
        supervisor_steps = 0
        last_tester_retries = 0

        STAGE_ORDER = ["architect", "designer", "coder", "tester", "github", "deployer"]
        STAGE_TO_AGENT_MAP = {"architect": "architect_agent", "designer": "designer_agent", "coder": "coder_agent", "tester": "tester_agent", "github": "github_agent", "deployer": "deployer_agent"}
        AGENT_TO_STAGE_MAP = {v: k for k, v in STAGE_TO_AGENT_MAP.items()}
        LEGACY_STAGE = {"architect": "architecture", "designer": "design", "coder": "coding", "tester": "testing", "github": "github", "deployer": "deployment"}

        def _map_failed_stage(stage: str) -> str:
            return LEGACY_STAGE.get(stage, stage)

        def _is_cancelled() -> bool:
            return bool(cancel_event and cancel_event.is_set())

        # Helper to record decision + retry count handling
        def _increment_retry(agent: str):
            def _up(state):
                cnt = state.retry_counts.get(agent, 0) + 1
                state.retry_counts[agent] = cnt
                return state
            board.update(_up)

        def _reset_downstream_after_retry(retried_agent: str):
            """After retrying an earlier stage due to downstream failure, reset downstream stages to waiting."""
            retried_stage = AGENT_TO_STAGE_MAP.get(retried_agent)
            if not retried_stage:
                return
            try:
                idx = STAGE_ORDER.index(retried_stage)
            except ValueError:
                return
            # Reset stages after retried_stage
            def _reset(state):
                for downstream in STAGE_ORDER[idx + 1:]:
                    # Only reset if not already completed successfully beyond retry point
                    # For tester-induced coder retry, we want tester/github/deployer -> waiting
                    state.stage_states[downstream] = "waiting"
                    # Also clear their outputs so supervisor doesn't see stale failure
                    if STAGE_TO_AGENT_MAP.get(downstream) in state.agent_outputs:
                        # Keep history in execution_history, but clear current output so routing not stale
                        # Instead of deleting, mark as needing re-run by removing; supervisor will see missing => route to that agent
                        state.agent_outputs.pop(STAGE_TO_AGENT_MAP[downstream], None)
                return state
            board.update(_reset)

        # Helper to dispatch specialist
        def _dispatch(agent_name: str) -> Dict[str, Any]:
            state_snapshot = board.read()
            selector_ctx = WhiteboardContextSelector.for_agent(state_snapshot, agent_name)
            # start marker
            WhiteboardManager.start_agent(board, agent_name)
            # also update ContextService current_stage for backward compat
            try:
                from backend.services.context_service import ContextService
                from backend.context.models import AGENT_TO_STAGE
                ContextService.set_current_stage(project_name, AGENT_TO_STAGE.get(agent_name, agent_name))
            except Exception:
                pass

            # call specialist with whiteboard context
            # handle overrides for architect/designer at first run
            if agent_name == "architect_agent":
                if override_architect_plan is not None and state_snapshot.stage_states.get("architect") == "waiting":
                    # mock plan for testing
                    res = {
                        "status": "success",
                        "plan": override_architect_plan,
                        "file_path": os.path.join(abs_project_path, "docs", "plan.json"),
                    }
                    # also write optional plan.json artifact for compatibility
                    try:
                        from backend.tools.file_tools import write_plan_json
                        write_plan_json(abs_project_path, override_architect_plan)
                    except Exception:
                        pass
                else:
                    res = self.architect.generate_plan(
                        user_idea=user_idea,
                        project_path=abs_project_path,
                        whiteboard=board,
                        board_context=selector_ctx,
                    )
            elif agent_name == "designer_agent":
                if override_designer_design is not None and state_snapshot.stage_states.get("designer") == "waiting":
                    res = {
                        "status": "success",
                        "design": override_designer_design,
                        "file_path": os.path.join(abs_project_path, "docs", "design.json"),
                    }
                    try:
                        from backend.tools.designer_tools import write_design_json
                        # need plan_data for parity; use override plan if available else board arch
                        plan_for_write = override_architect_plan or board.read().agent_context.get("architecture")
                        if plan_for_write:
                            write_design_json(abs_project_path, override_designer_design, plan_for_write)
                    except Exception:
                        pass
                else:
                    res = self.designer.generate_design(
                        project_path=abs_project_path,
                        whiteboard=board,
                        board_context=selector_ctx,
                    )
            elif agent_name == "coder_agent":
                res = self.coder.generate_code(
                    project_path=abs_project_path,
                    gemini_api_key=gemini_api_key,
                    whiteboard=board,
                    board_context=selector_ctx,
                )
            elif agent_name == "tester_agent":
                res = self.tester.validate_project(
                    project_path=abs_project_path,
                    whiteboard=board,
                    board_context=selector_ctx,
                )
            elif agent_name == "github_agent":
                res = self.github.publish_repository(
                    project_path=abs_project_path,
                    whiteboard=board,
                    board_context=selector_ctx,
                )
            elif agent_name == "deployer_agent":
                res = self.deployer.deploy_project(
                    project_path=abs_project_path,
                    gemini_api_key=gemini_api_key,
                    whiteboard=board,
                    board_context=selector_ctx,
                )
            else:
                res = {"status": "failed", "errors": [f"Unknown agent {agent_name}"]}

            # Determine success threshold
            status_val = res.get("status", "failed")
            is_success = status_val in ("success", "passed", "completed")
            # record on whiteboard
            artifact_refs: List[ArtifactReference] = []
            if is_success:
                # create artifact reference for primary output
                try:
                    if agent_name == "architect_agent":
                        artifact_refs.append(ArtifactReference(artifact_type="architecture", path=os.path.join(abs_project_path, "docs", "plan.json"), producer=agent_name, status="completed", summary=res.get("plan", {}).get("project", {}).get("description", "")[:200]))
                    elif agent_name == "designer_agent":
                        artifact_refs.append(ArtifactReference(artifact_type="design", path=os.path.join(abs_project_path, "docs", "design.json"), producer=agent_name, status="completed", summary="design generated"))
                    elif agent_name == "coder_agent":
                        artifact_refs.append(ArtifactReference(artifact_type="generated_project", path=abs_project_path, producer=agent_name, status="completed", summary="code generated"))
                    elif agent_name == "tester_agent":
                        artifact_refs.append(ArtifactReference(artifact_type="test_result", path=os.path.join(abs_project_path, "docs", "test_result.json"), producer=agent_name, status="completed", summary="tests passed" if is_success else "tests failed"))
                    elif agent_name == "github_agent":
                        artifact_refs.append(ArtifactReference(artifact_type="github_result", path=os.path.join(abs_project_path, "docs", "github_result.json"), producer=agent_name, status="completed", summary="github published"))
                    elif agent_name == "deployer_agent":
                        artifact_refs.append(ArtifactReference(artifact_type="deployment_result", path=os.path.join(abs_project_path, "docs", "deployment_result.json"), producer=agent_name, status="completed", summary="deployed"))
                except Exception:
                    pass
                WhiteboardManager.complete_agent(board, agent_name, res, artifact_refs=artifact_refs if artifact_refs else None)
                try:
                    from backend.services.context_service import ContextService
                    from backend.context.models import AGENT_TO_STAGE
                    stage = AGENT_TO_STAGE.get(agent_name, agent_name)
                    ContextService.record_stage_status(project_name, stage, "completed")
                    # record artifact in old context too for compat
                    if artifact_refs:
                        ContextService.record_artifact(project_name, artifact_type=artifact_refs[0].artifact_type, file_path=artifact_refs[0].path, stage=stage, status="completed", summary=artifact_refs[0].summary)
                except Exception:
                    pass
            else:
                WhiteboardManager.fail_agent(board, agent_name, res)
                try:
                    from backend.services.context_service import ContextService
                    from backend.context.models import AGENT_TO_STAGE
                    stage = AGENT_TO_STAGE.get(agent_name, agent_name)
                    ContextService.record_stage_status(project_name, stage, "failed")
                except Exception:
                    pass
            WhiteboardManager.persist(board)
            return res

        # ── Main Supervisor loop ──────────────────────────────────────────
        while supervisor_steps < MAX_SUPERVISOR_STEPS:
            if _is_cancelled():
                def _cancelled(s):
                    s.status = "blocked"
                    s.errors.append({"reason": "terminated_by_user", "stage": s.current_stage})
                    return s
                board.update(_cancelled)
                WhiteboardManager.append_event(board, event_type=events.RUN_FAILED, status="cancelled", summary="Pipeline terminated by user", agent="system")
                WhiteboardManager.persist(board)
                return {
                    "status": "cancelled",
                    "project_path": project_path,
                    "run_id": run_id,
                    "message": "Pipeline terminated by user",
                    "pipeline_log": pipeline_log,
                    "whiteboard": {"run_id": run_id, "status": "cancelled"},
                }
            state = board.read()
            # If already completed/failed, break
            if state.status in ("completed", "failed", "blocked"):
                break
            decision = self.supervisor.route(state, supervisor_step=supervisor_steps)
            # record decision on whiteboard
            def _record_decision(s):
                s.decisions.append(decision.model_dump(mode="json"))
                return s
            board.update(_record_decision)

            # also append event for routing decision
            WhiteboardManager.append_event(
                board,
                event_type="supervisor_routing",
                status=decision.action,
                summary=f"Supervisor routed to {decision.next_agent} ({decision.action}): {decision.reason}",
                stage=state.current_stage,
                agent="supervisor_agent",
            )

            if decision.action == "finish":
                # finalize run as completed
                def _finish(s):
                    s.status = "completed"
                    s.progress = 100
                    return s
                board.update(_finish)
                WhiteboardManager.append_event(board, event_type=events.RUN_COMPLETED, status="completed", summary="All stages completed successfully")
                WhiteboardManager.persist(board)
                try:
                    from backend.services.context_service import ContextService
                    ContextService.set_current_stage(project_name, "completed")
                except Exception:
                    pass
                break

            if decision.action == "blocked":
                def _block(s):
                    s.status = "blocked"
                    return s
                board.update(_block)
                WhiteboardManager.append_event(board, event_type=events.RUN_FAILED, status="blocked", summary=decision.reason)
                WhiteboardManager.persist(board)
                pipeline_log.append({"stage": "blocked", "result": decision.model_dump(mode="json")})
                return self._build_pipeline_failure(
                    failed_stage=_map_failed_stage(state.current_stage),
                    message=decision.reason,
                    pipeline_log=pipeline_log,
                    duration=time.time() - start_time,
                    failures=state.errors,
                    next_action_agent=decision.next_agent,
                )

            next_agent = decision.next_agent
            if not next_agent:
                # no agent but not finish/blocked — treat as failure
                return self._build_pipeline_failure(
                    failed_stage=_map_failed_stage(state.current_stage),
                    message=f"Supervisor returned no next_agent with action {decision.action}: {decision.reason}",
                    pipeline_log=pipeline_log,
                    duration=time.time() - start_time,
                )

            # Check retry budget: increment if this is a retry
            if decision.action == "retry":
                #Increment retry count for the target agent
                _increment_retry(next_agent)
                # Reset downstream stages so stale downstream failures don't cause infinite retry loop
                _reset_downstream_after_retry(next_agent)
                # Check if exceeded after increment (supervisor already checks, but double guard)
                if board.read().retry_counts.get(next_agent, 0) > MAX_AGENT_RETRIES:
                    def _fail_max(s):
                        s.status = "failed"
                        return s
                    board.update(_fail_max)
                    return self._build_pipeline_failure(
                        failed_stage=_map_failed_stage(state.current_stage),
                        message=f"Max retries exceeded for {next_agent}",
                        pipeline_log=pipeline_log,
                        duration=time.time() - start_time,
                    )
                WhiteboardManager.append_event(board, event_type=events.RETRY, status="retrying", summary=f"Retrying {next_agent}: {decision.reason}", agent=next_agent)

            # Dispatch specialist READ->PERFORM->WRITE cycle
            res = _dispatch(next_agent)
            pipeline_log.append({"stage": next_agent.replace("_agent",""), "result": res, "decision": decision.model_dump(mode="json")})

            # Track tester retries for legacy return payload
            if next_agent == "tester_agent":
                # count how many times tester has failed previously; pipeline_log can infer
                pass

            supervisor_steps += 1

            # Quick failure detection: if any stage failed and no retry possible, next loop will produce blocked
            # Continue loop to let supervisor decide next step

        # Check loop limit exceeded
        final_state = board.read()
        if supervisor_steps >= MAX_SUPERVISOR_STEPS and final_state.status not in ("completed", "failed", "blocked"):
            def _max_steps(s):
                s.status = "failed"
                s.errors.append({"reason": "max_steps_exceeded", "steps": supervisor_steps})
                return s
            board.update(_max_steps)
            WhiteboardManager.persist(board)
            return self._build_pipeline_failure(
                failed_stage=_map_failed_stage(final_state.current_stage),
                message=f"max_steps_exceeded: {MAX_SUPERVISOR_STEPS} supervisor steps reached",
                pipeline_log=pipeline_log,
                duration=time.time() - start_time,
            )

        # If loop exited without completing, check status
        if final_state.status != "completed":
            # Determine last failure details
            failed_stage = _map_failed_stage(final_state.current_stage)
            # find last failed agent output
            last_failed_agent = None
            for agent_name, output in final_state.agent_outputs.items():
                if output.status in ("failed", "blocked"):
                    last_failed_agent = agent_name
            return self._build_pipeline_failure(
                failed_stage=failed_stage,
                message=f"Pipeline ended with status {final_state.status}",
                pipeline_log=pipeline_log,
                duration=time.time() - start_time,
            )

        # ── SUCCESS PAYLOAD ───────────────────────────────────────────────
        # Retrieve deployment/github outputs from whiteboard for URLs
        deploy_out = final_state.agent_outputs.get("deployer_agent")
        github_out = final_state.agent_outputs.get("github_agent")
        github_url = ""
        vercel_url = ""
        if deploy_out and deploy_out.data:
            github_url = deploy_out.data.get("github", {}).get("repository_url", "") or deploy_out.data.get("github", {}).get("repository_url", "")
            vercel_url = deploy_out.data.get("vercel", {}).get("deployment_url", "")
        if not github_url and github_out and github_out.data:
            github_url = github_out.data.get("repository", {}).get("url", "") or github_out.data.get("repository", {}).get("repository_url", "")

        # also fallback to direct file reads if needed for compat
        if not github_url or not vercel_url:
            deploy_file = os.path.join(abs_project_path, "docs", "deployment_result.json")
            if os.path.isfile(deploy_file):
                try:
                    with open(deploy_file, "r", encoding="utf-8") as f:
                        ddata = json.load(f)
                    github_url = ddata.get("github", {}).get("repository_url", github_url)
                    vercel_url = ddata.get("vercel", {}).get("deployment_url", vercel_url)
                except Exception:
                    pass

        duration = round(time.time() - start_time, 2)
        summary_text = f"Agent system deployed successfully.\n\nGitHub:\n{github_url}\n\nVercel:\n{vercel_url}"
        # compute retries performed as total retry counts
        retries_performed = sum(final_state.retry_counts.values())

        return {
            "status": "success",
            "project_path": project_path,
            "github_url": github_url,
            "vercel_url": vercel_url,
            "summary": summary_text,
            "duration_seconds": duration,
            "retries_performed": retries_performed,
            "stages_completed": [k for k,v in final_state.stage_states.items() if v == "completed"],
            "pipeline_log": pipeline_log,
            "whiteboard": {
                "run_id": final_state.run_id,
                "state_version": final_state.state_version,
                "progress": final_state.progress,
                "current_stage": final_state.current_stage,
                "current_agent": final_state.current_agent,
            },
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
    orchestrator = RootAgent()
    return orchestrator.run_pipeline(
        user_idea=user_idea,
        project_path=project_path,
        gemini_api_key=gemini_api_key,
    )
