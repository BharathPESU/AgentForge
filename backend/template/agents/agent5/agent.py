"""
Agent 5 definition: Critic & Verifier.
Integrates Google GenAI SDK / ADK with quality assessment and validation tools.
"""

import os
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from .prompt import SYSTEM_INSTRUCTION, AGENT_NAME, AGENT_ROLE
from .tools import TOOLS_LIST


class CriticAgent:
    """Specialized Agent for Quality Assurance, Fact-Checking & Criticism."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-pro",
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
        """Evaluate response or audit claims against quality criteria."""
        if not self.client:
            return {
                "agent": self.name,
                "role": self.role,
                "response": f"[MOCK CRITIC AGENT] Quality Audit Complete:\n\n- Composite Score: 9.2/10\n- Verification Status: PASSED\n- Strengths: Concise, modular, well-documented.\n- Suggestions: Ready for production deployment.",
                "tools_used": ["evaluate_rubric_scores"],
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


def get_agent(**kwargs) -> CriticAgent:
    """Factory method to instantiate Agent 5."""
    return CriticAgent(**kwargs)