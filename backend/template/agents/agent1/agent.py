"""
Agent 1 definition: Research Specialist.
Integrates Google GenAI SDK / ADK configuration with custom tools and instructions.
"""

import os
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

from .prompt import SYSTEM_INSTRUCTION, AGENT_NAME, AGENT_ROLE
from .tools import TOOLS_LIST


class ResearchAgent:
    """Specialized Agent for Research & Information Retrieval."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        temperature: float = 0.3,
        api_key: Optional[str] = None
    ):
        self.name = AGENT_NAME
        self.role = AGENT_ROLE
        self.model_name = model_name
        self.temperature = temperature
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.tools = TOOLS_LIST

    def get_system_instruction(self) -> str:
        return SYSTEM_INSTRUCTION

    def run(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the research agent on a given prompt."""
        if not self.client:
            return {
                "agent": self.name,
                "role": self.role,
                "response": f"[MOCK RESEARCH] Conducted in-depth research on: '{prompt}'. Identified key sources and structured findings.",
                "tools_used": ["search_knowledge_base", "fetch_web_summary"],
                "status": "success"
            }

        try:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=self.temperature,
                tools=self.tools
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return {
                "agent": self.name,
                "role": self.role,
                "response": response.text,
                "status": "success"
            }
        except Exception as e:
            return {
                "agent": self.name,
                "role": self.role,
                "error": str(e),
                "status": "error"
            }


def get_agent(**kwargs) -> ResearchAgent:
    """Factory method to instantiate Agent 1."""
    return ResearchAgent(**kwargs)