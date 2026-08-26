"""Root entrypoint for AgentForge backend multi-agent builder platform."""

from backend.agents.root_agent import RootAgent, run_pipeline


def get_root_agent() -> RootAgent:
    """Instantiate and return the AgentForge Master Root Agent."""
    return RootAgent()


__all__ = ["RootAgent", "run_pipeline", "get_root_agent"]
