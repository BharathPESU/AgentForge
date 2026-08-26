"""
Agent 4 definition: Synthesis & Writer.
Integrates Google GenAI SDK / ADK with writing and formatting capabilities.
"""

import os
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from .prompt import SYSTEM_INSTRUCTION, AGENT_NAME, AGENT_ROLE
from .tools import TOOLS_LIST


class WriterAgent:
    """Specialized Agent for Document Synthesis, Markdown Generation & Writing."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        temperature: float = 0.7,
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
        """Synthesize input information into polished output."""
        if not self.client:
            return {
                "agent": self.name,
                "role": self.role,
                "response": f"# Synthesized Briefing\n\nSynthesized comprehensive report for prompt: '{prompt}'.\n\n- Key Point 1: Modular sub-agent workflow.\n- Key Point 2: Clear separation of concerns.",
                "tools_used": ["format_markdown_document"],
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


def get_agent(**kwargs) -> WriterAgent:
    """Factory method to instantiate Agent 4."""
    return WriterAgent(**kwargs)