"""
Google ADK Root Orchestrator Agent
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

from agents.agent1.agent import get_agent as get_agent1
from agents.agent2.agent import get_agent as get_agent2
from agents.agent3.agent import get_agent as get_agent3
from agents.agent4.agent import get_agent as get_agent4
from agents.agent5.agent import get_agent as get_agent5

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def load_settings() -> Dict[str, Any]:
    settings_path = Path(__file__).parent / "settings.yaml"
    if settings_path.exists():
        with open(settings_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


class RootOrchestrator:
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or load_settings()
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.model_name = (
            self.settings.get("models", {}).get("default") or "gemini-2.5-flash"
        )
        self.client = genai.Client(api_key=self.api_key) if (self.api_key and GENAI_AVAILABLE) else None
        self.sub_agents: Dict[str, Any] = {}
        self._initialize_sub_agents()

    def _initialize_sub_agents(self):
        agent_configs = self.settings.get("agents", {})

        cfg1 = agent_configs.get("agent1", {})
        if cfg1.get("enabled", True):
            self.sub_agents["agent1"] = get_agent1(
                model_name=cfg1.get("model", "gemini-2.5-flash"),
                temperature=cfg1.get("temperature", 0.3),
                api_key=self.api_key
            )

        cfg2 = agent_configs.get("agent2", {})
        if cfg2.get("enabled", True):
            self.sub_agents["agent2"] = get_agent2(
                model_name=cfg2.get("model", "gemini-2.5-pro"),
                temperature=cfg2.get("temperature", 0.2),
                api_key=self.api_key
            )

        cfg3 = agent_configs.get("agent3", {})
        if cfg3.get("enabled", True):
            self.sub_agents["agent3"] = get_agent3(
                model_name=cfg3.get("model", "gemini-2.5-flash"),
                temperature=cfg3.get("temperature", 0.1),
                api_key=self.api_key
            )

        cfg4 = agent_configs.get("agent4", {})
        if cfg4.get("enabled", True):
            self.sub_agents["agent4"] = get_agent4(
                model_name=cfg4.get("model", "gemini-2.5-flash"),
                temperature=cfg4.get("temperature", 0.7),
                api_key=self.api_key
            )

        cfg5 = agent_configs.get("agent5", {})
        if cfg5.get("enabled", True):
            self.sub_agents["agent5"] = get_agent5(
                model_name=cfg5.get("model", "gemini-2.5-pro"),
                temperature=cfg5.get("temperature", 0.1),
                api_key=self.api_key
            )

    def list_agents(self) -> List[Dict[str, Any]]:
        agent_list = []
        for key, agent in self.sub_agents.items():
            agent_list.append({
                "id": key,
                "name": getattr(agent, "name", key),
                "role": getattr(agent, "role", "Specialist"),
                "model": getattr(agent, "model_name", "unknown"),
                "tools": [t.__name__ for t in getattr(agent, "tools", [])]
            })
        return agent_list

    def route_query(self, user_query: str) -> str:
        q_lower = user_query.lower()
        if any(w in q_lower for w in ["code", "python", "script", "function", "debug", "algorithm", "program"]):
            return "agent2"
        if any(w in q_lower for w in ["calculate", "math", "statistics", "dataset", "numbers", "formula", "percent"]):
            return "agent3"
        if any(w in q_lower for w in ["write", "report", "summarize", "draft", "article", "readme", "essay"]):
            return "agent4"
        if any(w in q_lower for w in ["critique", "review", "verify", "fact-check", "score", "audit", "validate"]):
            return "agent5"
        return "agent1"

    def run_agent(self, agent_id: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if agent_id not in self.sub_agents:
            return {
                "status": "error",
                "error": f"Agent '{agent_id}' is not registered or disabled.",
                "available_agents": list(self.sub_agents.keys())
            }
        return self.sub_agents[agent_id].run(prompt, context=context)

    def run_pipeline(self, user_query: str) -> Dict[str, Any]:
        workflow_steps = []

        res_agent = self.sub_agents.get("agent1")
        research_out = res_agent.run(f"Research and gather facts for: {user_query}") if res_agent else {}
        workflow_steps.append({
            "step": 1,
            "agent": "agent1 (Research)",
            "output": research_out.get("response", "")
        })

        target_specialist = "agent2" if ("code" in user_query.lower() or "program" in user_query.lower()) else "agent3"
        spec_agent = self.sub_agents.get(target_specialist)
        spec_prompt = f"Using this research:\n{research_out.get('response', '')}\n\nDeliver the technical/data solution for: {user_query}"
        specialist_out = spec_agent.run(spec_prompt) if spec_agent else {}
        workflow_steps.append({
            "step": 2,
            "agent": f"{target_specialist} (Specialist)",
            "output": specialist_out.get("response", "")
        })

        writer_agent = self.sub_agents.get("agent4")
        writer_prompt = f"Synthesize a complete final report combining:\n\nResearch:\n{research_out.get('response', '')}\n\nTechnical Solution:\n{specialist_out.get('response', '')}\n\nUser Goal: {user_query}"
        writer_out = writer_agent.run(writer_prompt) if writer_agent else {}
        workflow_steps.append({
            "step": 3,
            "agent": "agent4 (Writer)",
            "output": writer_out.get("response", "")
        })

        critic_agent = self.sub_agents.get("agent5")
        critic_prompt = f"Review and verify this output report:\n{writer_out.get('response', '')}\n\nOriginal Request: {user_query}"
        critic_out = critic_agent.run(critic_prompt) if critic_agent else {}
        workflow_steps.append({
            "step": 4,
            "agent": "agent5 (Critic)",
            "output": critic_out.get("response", "")
        })

        return {
            "status": "success",
            "query": user_query,
            "final_response": writer_out.get("response", ""),
            "critic_verdict": critic_out.get("response", ""),
            "pipeline_steps": workflow_steps
        }

    def chat(self, user_query: str, auto_route: bool = True) -> Dict[str, Any]:
        if auto_route:
            assigned_id = self.route_query(user_query)
            agent_result = self.run_agent(assigned_id, user_query)
            return {
                "orchestrator_mode": "auto_route",
                "assigned_agent": assigned_id,
                "agent_name": getattr(self.sub_agents.get(assigned_id), "name", assigned_id),
                "result": agent_result
            }
        return self.run_pipeline(user_query)


_root_instance: Optional[RootOrchestrator] = None


def get_root_agent() -> RootOrchestrator:
    global _root_instance
    if _root_instance is None:
        _root_instance = RootOrchestrator()
    return _root_instance