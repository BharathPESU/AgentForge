"""Supervisor Agent for AgentForge — routes via shared Whiteboard."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import google.adk as adk

from backend.context.models import ALLOWED_AGENTS, RoutingDecision, WhiteboardState

MAX_SUPERVISOR_STEPS = 12
MAX_AGENT_RETRIES = 3

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "..", "prompts", "supervisor_prompt.md")


def load_supervisor_instruction(prompt_path: Optional[str] = None) -> str:
    path = prompt_path or PROMPT_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Supervisor prompt not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Routing helpers -------------------------------------------------------------

def _failure_category(failures: list) -> str:
    if not failures:
        return ""
    # first failure category dominates routing
    cat = failures[0].get("category", "") if isinstance(failures[0], dict) else ""
    return str(cat).upper()


def decide_next(state: WhiteboardState, supervisor_step: int = 0) -> RoutingDecision:
    """Deterministic routing decision based solely on Whiteboard state.

    No LLM call required for basic pipeline — deterministic ensures tests pass
    without API keys and avoids extra token cost. LLM can be layered later.
    """
    # Step limit guard
    if supervisor_step >= MAX_SUPERVISOR_STEPS:
        return RoutingDecision(
            next_agent=None,
            action="blocked",
            reason=f"max_steps_exceeded: {MAX_SUPERVISOR_STEPS} supervisor steps reached",
            confidence=1.0,
        )

    stage_states = state.stage_states
    outputs = state.agent_outputs
    retry_counts = state.retry_counts

    # Helper to check retry budget
    def _can_retry(agent: str) -> bool:
        return retry_counts.get(agent, 0) < MAX_AGENT_RETRIES

    # Determine completion flags
    arch_done = stage_states.get("architect") == "completed"
    design_done = stage_states.get("designer") == "completed"
    coder_done = stage_states.get("coder") == "completed"
    tester_done = stage_states.get("tester") == "completed"
    github_done = stage_states.get("github") == "completed"
    deployer_done = stage_states.get("deployer") == "completed"

    arch_failed = stage_states.get("architect") == "failed"
    design_failed = stage_states.get("designer") == "failed"
    coder_failed = stage_states.get("coder") == "failed"
    tester_status = outputs.get("tester_agent")
    github_status = outputs.get("github_agent")
    deployer_status = outputs.get("deployer_agent")

    # Failure routing — check tester failures first (highest priority after step limit)
    if tester_status is not None:
        t_data = tester_status.data if hasattr(tester_status, "data") else {}
        # failures list may be in t_data
        failures = t_data.get("failures", []) if isinstance(t_data, dict) else []
        status = tester_status.status if hasattr(tester_status, "status") else str(t_data.get("status", ""))
        category = _failure_category(failures)

        if status in ("failed", "blocked"):
            # Architecture/design errors route backwards
            if "ARCHITECTURE" in category:
                if not _can_retry("architect_agent"):
                    return RoutingDecision(next_agent=None, action="blocked", reason="architect max retries exceeded after tester architecture error", confidence=0.95)
                return RoutingDecision(next_agent="architect_agent", action="retry", reason=f"Tester reported architecture error: {failures[0].get('message','')[:200]}", confidence=0.95)
            if "DESIGN" in category:
                if not _can_retry("designer_agent"):
                    return RoutingDecision(next_agent=None, action="blocked", reason="designer max retries exceeded after tester design error", confidence=0.95)
                return RoutingDecision(next_agent="designer_agent", action="retry", reason=f"Tester reported design error: {failures[0].get('message','')[:200]}", confidence=0.95)
            # Implementation / runtime / test errors route to coder
            if any(k in category for k in ("IMPLEMENTATION", "RUNTIME", "TEST", "COMMUNICATION", "SECURITY", "DEPLOYMENT_STRUCTURE", "LOCAL_SERVER", "MOCK_OUTPUT", "SMOKE")):
                if not _can_retry("coder_agent"):
                    return RoutingDecision(next_agent=None, action="blocked", reason="coder max retries exceeded after tester implementation error", confidence=0.95)
                return RoutingDecision(next_agent="coder_agent", action="retry", reason=f"Tester reported implementation error: {failures[0].get('message','')[:200]}", confidence=0.95)
            # Generic tester failed without category — default to coder
            if status == "failed":
                if _can_retry("coder_agent"):
                    return RoutingDecision(next_agent="coder_agent", action="retry", reason="Tester failed; retrying coder", confidence=0.85)
                return RoutingDecision(next_agent=None, action="blocked", reason="coder max retries exceeded", confidence=0.9)

        # Tester blocked (plan/design missing) — route to architect/designer accordingly
        if status == "blocked":
            if "ARCHITECTURE" in category:
                return RoutingDecision(next_agent="architect_agent", action="retry", reason="Tester blocked on architecture", confidence=0.95)
            if "DESIGN" in category:
                return RoutingDecision(next_agent="designer_agent", action="retry", reason="Tester blocked on design", confidence=0.95)

    # GitHub failure routing
    if github_status is not None and github_status.status in ("failed", "blocked"):
        reason_msg = github_status.summary[:200] if hasattr(github_status, "summary") else "github failed"
        if github_status.status == "blocked":
            # usually testing_not_passed -> route to tester
            return RoutingDecision(next_agent="tester_agent", action="retry", reason=reason_msg, confidence=0.9)
        if _can_retry("github_agent"):
            return RoutingDecision(next_agent="github_agent", action="retry", reason=reason_msg, confidence=0.9)
        return RoutingDecision(next_agent=None, action="blocked", reason="github max retries exceeded", confidence=0.9)

    # Deployer failure routing
    if deployer_status is not None and deployer_status.status in ("failed", "blocked"):
        fail_data = deployer_status.data if hasattr(deployer_status, "data") else {}
        category = ""
        if isinstance(fail_data, dict):
            failure = fail_data.get("failure", {})
            if isinstance(failure, dict):
                category = str(failure.get("category", "")).upper()
        if "VERCEL_BUILD" in category or "BUILD" in category:
            if _can_retry("coder_agent"):
                return RoutingDecision(next_agent="coder_agent", action="retry", reason="Deployer build failure; retrying coder", confidence=0.9)
            return RoutingDecision(next_agent=None, action="blocked", reason="coder max retries exceeded after deployer build error", confidence=0.9)
        if "VERCEL_PROJECT" in category or "MISSING_GITHUB" in category or "TESTS_NOT_PASSED" in category:
            if _can_retry("deployer_agent"):
                return RoutingDecision(next_agent="deployer_agent", action="retry", reason="Deployer config failure; retrying deployer", confidence=0.85)
            return RoutingDecision(next_agent=None, action="blocked", reason="deployer max retries exceeded", confidence=0.9)
        # generic deployer failure retry deployer
        if _can_retry("deployer_agent"):
            return RoutingDecision(next_agent="deployer_agent", action="retry", reason=deployer_status.summary[:200], confidence=0.8)
        return RoutingDecision(next_agent=None, action="blocked", reason="deployer max retries exceeded", confidence=0.9)

    # Check in_progress stages — should not double-schedule
    for stage, status in stage_states.items():
        if status == "in_progress":
            return RoutingDecision(next_agent=None, action="blocked", reason=f"stage {stage} already in_progress", confidence=0.9)
        if status == "failed":
            # Direct stage failure is terminal — do not auto-retry; pipeline should fail fast.
            # Retries are only via tester/deployer-induced routing above.
            return RoutingDecision(next_agent=None, action="blocked", reason=f"stage {stage} failed terminally", confidence=0.95)

    # Happy path progression
    if not arch_done:
        if arch_failed:
            return RoutingDecision(next_agent=None, action="blocked", reason="architect failed terminally", confidence=1.0)
        return RoutingDecision(next_agent="architect_agent", action="continue", reason="Architecture not yet complete", confidence=0.98)

    if not design_done:
        if design_failed:
            return RoutingDecision(next_agent=None, action="blocked", reason="designer failed terminally", confidence=1.0)
        return RoutingDecision(next_agent="designer_agent", action="continue", reason="Design not yet complete", confidence=0.98)

    if not coder_done:
        if coder_failed:
            return RoutingDecision(next_agent=None, action="blocked", reason="coder failed terminally", confidence=1.0)
        return RoutingDecision(next_agent="coder_agent", action="continue", reason="Coding not yet complete", confidence=0.98)

    if not tester_done:
        return RoutingDecision(next_agent="tester_agent", action="continue", reason="Ready for testing", confidence=0.98)

    if not github_done:
        return RoutingDecision(next_agent="github_agent", action="continue", reason="Tests passed; ready for GitHub publish", confidence=0.98)

    if not deployer_done:
        return RoutingDecision(next_agent="deployer_agent", action="continue", reason="GitHub complete; ready for deployment", confidence=0.98)

    # All done
    return RoutingDecision(next_agent=None, action="finish", reason="All stages completed successfully", confidence=1.0)


class SupervisorAgent:
    """Supervisor that decides routing based on Whiteboard state."""

    def __init__(self, model_name: Optional[str] = None, prompt_path: Optional[str] = None):
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.instruction = load_supervisor_instruction(prompt_path)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        return adk.Agent(
            name="supervisor_agent",
            description="AgentForge Supervisor Agent for whiteboard-coordinated routing",
            model=self.model_name,
            instruction=self.instruction,
            tools=[],
        )

    def route(self, state: WhiteboardState, supervisor_step: int = 0) -> RoutingDecision:
        """Return deterministic routing decision for given whiteboard snapshot."""
        return decide_next(state, supervisor_step=supervisor_step)

    def next_agent(self, state: WhiteboardState, supervisor_step: int = 0) -> Dict[str, Any]:
        """Dict-shaped helper for RootAgent orchestration."""
        decision = self.route(state, supervisor_step=supervisor_step)
        return decision.model_dump(mode="json")
