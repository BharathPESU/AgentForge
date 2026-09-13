"""Typed shared Whiteboard state models for AgentForge."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


AgentName = Literal[
    "architect_agent",
    "designer_agent",
    "coder_agent",
    "tester_agent",
    "github_agent",
    "deployer_agent",
]

StageName = Literal[
    "architect",
    "designer",
    "coder",
    "tester",
    "github",
    "deployer",
]

StageStatus = Literal["waiting", "in_progress", "completed", "failed", "retrying", "blocked"]
RunStatus = Literal["pending", "running", "completed", "failed", "blocked", "cancelled"]
RoutingAction = Literal["continue", "retry", "blocked", "finish"]


AGENT_TO_STAGE: Dict[str, str] = {
    "architect_agent": "architect",
    "designer_agent": "designer",
    "coder_agent": "coder",
    "tester_agent": "tester",
    "github_agent": "github",
    "deployer_agent": "deployer",
}

STAGE_TO_AGENT: Dict[str, str] = {stage: agent for agent, stage in AGENT_TO_STAGE.items()}
STAGE_ORDER: List[str] = ["architect", "designer", "coder", "tester", "github", "deployer"]
ALLOWED_AGENTS = set(AGENT_TO_STAGE.keys())


class ArtifactReference(BaseModel):
    """Reference to a generated artifact without embedding large content."""

    artifact_type: str
    path: str
    producer: AgentName
    status: str = "completed"
    summary: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WhiteboardEvent(BaseModel):
    """Compact execution history item."""

    event_type: str
    stage: Optional[str] = None
    agent: Optional[str] = None
    status: str
    summary: str = ""
    artifact: str = ""
    attempt: int = 1
    timestamp: float


class AgentOutput(BaseModel):
    """Structured specialist result stored on the whiteboard."""

    agent: AgentName
    status: str
    summary: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    files_changed: List[str] = Field(default_factory=list)
    errors: List[Any] = Field(default_factory=list)
    next_recommendation: Optional[str] = None


class WhiteboardState(BaseModel):
    """Shared source of truth for a single AgentForge run."""

    run_id: str
    user_id: str = "user_default"
    project_id: str
    project_path: str
    user_idea: str
    current_agent: Optional[str] = None
    current_stage: str = "architect"
    status: RunStatus = "pending"
    progress: int = 0
    stage_states: Dict[str, StageStatus] = Field(
        default_factory=lambda: {stage: "waiting" for stage in STAGE_ORDER}
    )
    agent_context: Dict[str, Any] = Field(default_factory=dict)
    agent_outputs: Dict[str, AgentOutput] = Field(default_factory=dict)
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Any] = Field(default_factory=list)
    retry_counts: Dict[str, int] = Field(default_factory=dict)
    files_changed: List[str] = Field(default_factory=list)
    artifacts: Dict[str, ArtifactReference] = Field(default_factory=dict)
    execution_history: List[WhiteboardEvent] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    state_version: int = 1


class RoutingDecision(BaseModel):
    """Supervisor routing decision with bounded targets and actions."""

    next_agent: Optional[AgentName] = None
    action: RoutingAction
    reason: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
