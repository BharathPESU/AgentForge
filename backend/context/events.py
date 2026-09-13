"""Whiteboard event helpers."""

from __future__ import annotations

import time
from typing import Optional

from backend.context.models import WhiteboardEvent


AGENT_STARTED = "agent_started"
AGENT_COMPLETED = "agent_completed"
AGENT_FAILED = "agent_failed"
ARTIFACT_CREATED = "artifact_created"
RETRY = "retry"
RUN_COMPLETED = "run_completed"
RUN_FAILED = "run_failed"


def make_event(
    event_type: str,
    status: str,
    summary: str = "",
    stage: Optional[str] = None,
    agent: Optional[str] = None,
    artifact: str = "",
    attempt: int = 1,
) -> WhiteboardEvent:
    """Create a compact timestamped whiteboard event."""
    return WhiteboardEvent(
        event_type=event_type,
        stage=stage,
        agent=agent,
        status=status,
        summary=summary,
        artifact=artifact,
        attempt=attempt,
        timestamp=time.time(),
    )
