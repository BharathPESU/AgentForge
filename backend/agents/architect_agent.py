"""Architect Agent implementation for AgentForge using Google ADK."""

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

import google.adk as adk
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from backend.tools.file_tools import (
    read_project_document,
    read_schema,
    validate_plan_json,
    write_plan_json,
)

from backend.roundRobin import set_gemini_api_key_env

load_dotenv()

MAX_PLAN_RETRIES = 3
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


PROMPT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "architect_prompt.md"
)


def load_architect_instruction(prompt_path: Optional[str] = None) -> str:
    """Load the Architect Agent system instruction from markdown file."""
    path = prompt_path or PROMPT_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON object from raw LLM output string."""
    if not text or not isinstance(text, str):
        return None

    cleaned = text.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Match codeblocks like ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Match outer braces
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


class ArchitectAgent:
    """Architect Agent responsible for transforming natural language user ideas
    into structured machine-readable multi-agent architecture plan.json files.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        prompt_path: Optional[str] = None,
        schema_path: Optional[str] = None,
    ):
        self.model_name = model_name or DEFAULT_MODEL
        self.prompt_path = prompt_path
        self.schema_path = schema_path
        self.instruction = load_architect_instruction(prompt_path)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        """Instantiate Google ADK Agent with deterministic tools."""
        return adk.Agent(
            name="architect_agent",
            description="AgentForge Architect Agent for multi-agent system design",
            model=self.model_name,
            instruction=self.instruction,
            tools=[
                read_project_document,
                read_schema,
                validate_plan_json,
                write_plan_json,
            ],
        )

    def generate_plan(
        self,
        user_idea: str,
        project_path: str = ".",
        override_llm_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate, validate, self-correct, and save the architecture plan.json.
        
        Args:
            user_idea: Natural language description of the target system.
            project_path: Directory where docs/plan.json should be saved.
            override_llm_response: Optional string override for testing/mocking.
            
        Returns:
            Dict containing status ('success' or 'failed'), plan dict, and output path.
        """
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        current_input = f"User Request / System Idea:\n{user_idea}\n\nProduce a valid plan.json following the schema."
        last_errors: List[str] = []

        for attempt in range(1, MAX_PLAN_RETRIES + 1):
            raw_response_text = ""

            if override_llm_response is not None:
                raw_response_text = override_llm_response
            elif api_key:
                raw_response_text = self._run_adk_runner(current_input)
            else:
                # Fallback for offline testing without API keys when no mock is passed
                return {
                    "status": "failed",
                    "stage": "architecture",
                    "errors": ["API key (GEMINI_API_KEY / GOOGLE_API_KEY) not found in environment."],
                }

            plan_data = extract_json_from_text(raw_response_text)

            if not plan_data:
                validation_res = {
                    "valid": False,
                    "errors": [f"Could not parse valid JSON from response: '{raw_response_text[:100]}...'"],
                }
            else:
                validation_res = validate_plan_json(plan_data, self.schema_path)

            if validation_res["valid"]:
                # Save plan to disk
                saved_file_path = write_plan_json(project_path, plan_data)
                
                # Re-read and re-validate saved file to guarantee file creation integrity
                with open(saved_file_path, "r", encoding="utf-8") as f:
                    reloaded_plan = json.load(f)
                
                re_val = validate_plan_json(reloaded_plan, self.schema_path)
                if not re_val["valid"]:
                    return {
                        "status": "failed",
                        "stage": "architecture",
                        "errors": [f"Saved plan file re-validation failed: {re_val['errors']}"],
                    }

                return {
                    "status": "success",
                    "plan": reloaded_plan,
                    "file_path": saved_file_path,
                    "attempts": attempt,
                }
            else:
                last_errors = validation_res["errors"]
                # Formulate correction prompt for self-correction loop
                current_input = (
                    f"Previous attempt failed schema/semantic validation with the following errors:\n"
                    + "\n".join(f"- {e}" for e in last_errors)
                    + "\n\nPlease fix all errors and return the corrected complete JSON plan."
                )

        return {
            "status": "failed",
            "stage": "architecture",
            "errors": [
                f"Validation failed after {MAX_PLAN_RETRIES} attempts. Last errors: {last_errors}"
            ],
        }

    def _run_adk_runner(self, prompt: str) -> str:
        """Run ADK Agent using Runner and InMemorySessionService."""
        session_service = InMemorySessionService()
        runner = adk.Runner(
            agent=self.adk_agent,
            app_name="agentforge",
            session_service=session_service,
            auto_create_session=True,
        )

        session_id = str(uuid.uuid4())
        content = types.Content(parts=[types.Part.from_text(text=prompt)])
        
        output_chunks: List[str] = []
        events = runner.run(
            user_id="agentforge_user",
            session_id=session_id,
            new_message=content,
        )

        for event in events:
            if hasattr(event, "content") and event.content:
                if hasattr(event.content, "parts"):
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            output_chunks.append(part.text)
            elif hasattr(event, "text") and event.text:
                output_chunks.append(event.text)

        return "".join(output_chunks)
