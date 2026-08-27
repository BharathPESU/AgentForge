"""
Google ADK Multi-Agent System Entrypoint
"""

import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()


class RootOrchestrator:
    """Default Root Orchestrator for multi-agent project template."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or {}
        self.sub_agents: Dict[str, Any] = {}

    def list_agents(self) -> List[Dict[str, Any]]:
        return []

    def route_query(self, user_query: str) -> str:
        return "agent1"

    def run_agent(self, agent_id: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"status": "success", "agent": agent_id, "response": f"Processed: {prompt}"}

    def run_pipeline(self, user_query: str) -> Dict[str, Any]:
        return {"status": "success", "query": user_query, "final_response": "Multi-agent pipeline complete."}

    def chat(self, user_query: str, auto_route: bool = True) -> Dict[str, Any]:
        return self.run_pipeline(user_query)


_root_instance: Optional[RootOrchestrator] = None


def get_root_agent() -> RootOrchestrator:
    global _root_instance
    if _root_instance is None:
        _root_instance = RootOrchestrator()
    return _root_instance
