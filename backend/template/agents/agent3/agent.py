"""
Agent 3 definition: Data & Math Analyst.
Integrates Google GenAI SDK / ADK with quantitative and math tools.
"""

import os
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from .prompt import SYSTEM_INSTRUCTION, AGENT_NAME, AGENT_ROLE
from .tools import TOOLS_LIST


class DataAgent:
    """Specialized Agent for Numerical Calculations & Data Analytics."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        temperature: float = 0.1,
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
        """Execute numerical analysis or mathematical calculation."""
        if not self.client:
            return {
                "agent": self.name,
                "role": self.role,
                "response": f"[MOCK DATA AGENT] Computed quantitative breakdown for: '{prompt}'.",
                "tools_used": ["calculate_math_expression", "compute_descriptive_stats"],
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


def get_agent(**kwargs) -> DataAgent:
    """Factory method to instantiate Agent 3."""
    return DataAgent(**kwargs)