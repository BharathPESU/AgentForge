"""Designer Agent implementation for AgentForge using Google ADK."""

import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import google.adk as adk
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from backend.agents.architect_agent import extract_json_from_text
from backend.tools.designer_tools import (
    read_plan_json,
    read_schema,
    validate_design_json,
    write_design_json,
)
from backend.tools.file_tools import read_project_document

from backend.roundRobin import set_gemini_api_key_env

load_dotenv()

MAX_DESIGN_RETRIES = 3
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


PROMPT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "designer_prompt.md"
)


def load_designer_instruction(prompt_path: Optional[str] = None) -> str:
    """Load the Designer Agent system instruction from markdown file and append design_schema.json."""
    path = prompt_path or PROMPT_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        instruction = f.read()

    try:
        schema_dict = read_schema()
        schema_json = json.dumps(schema_dict, indent=2)
        instruction += f"\n\nTarget JSON Schema (`design_schema.json`) to follow strictly:\n```json\n{schema_json}\n```\n"
    except Exception:
        pass

    return instruction


class DesignerAgent:
    """Designer Agent responsible for transforming architectural plan.json files
    into detailed implementation design.json files for Coder Agent consumption.
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
        self.instruction = load_designer_instruction(prompt_path)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        """Instantiate Google ADK Agent for single-turn structured design generation."""
        return adk.Agent(
            name="designer_agent",
            description="AgentForge Designer Agent for detailed agent and tool design",
            model=self.model_name,
            instruction=self.instruction,
            tools=[],  # Direct single-turn JSON generation (no multi-turn tool loops)
        )


    def generate_design(
        self,
        project_path: str = ".",
        override_llm_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate, validate, self-correct, and save the design.json file.
        
        Args:
            project_path: Directory or path where plan.json exists and design.json will be written.
            override_llm_response: Optional string override for testing/mocking.
            
        Returns:
            Dict containing status, output paths, and design specifications.
        """
        # Step 1: Read and validate plan.json
        plan_res = read_plan_json(project_path)
        if not plan_res["valid"]:
            return {
                "status": "failed",
                "stage": "design",
                "errors": plan_res["errors"],
                "ready_for_coding": False,
            }

        plan_data = plan_res["data"]
        plan_file_path = plan_res["file_path"]

        set_gemini_api_key_env()
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        plan_str = json.dumps(plan_data, indent=2)
        current_input = (
            f"Here is the valid architecture plan.json to design:\n\n{plan_str}\n\n"
            f"Produce the complete, detailed implementation design.json matching design_schema.json."
        )

        last_errors: List[str] = []

        # Step 2: Self-correction generation loop
        for attempt in range(1, MAX_DESIGN_RETRIES + 1):
            raw_response_text = ""

            if override_llm_response is not None:
                raw_response_text = override_llm_response
            elif api_key:
                raw_response_text = self._run_adk_runner(current_input)
            else:
                return {
                    "status": "failed",
                    "stage": "design",
                    "errors": ["API key (GEMINI_API_KEY / GOOGLE_API_KEY) not found in environment."],
                    "ready_for_coding": False,
                }

            design_data = extract_json_from_text(raw_response_text)

            if not design_data:
                validation_res = {
                    "valid": False,
                    "errors": [f"Could not parse valid JSON from response: '{raw_response_text[:100]}...'"],
                }
            else:
                validation_res = validate_design_json(design_data, plan_data)

            if validation_res["valid"]:
                # Step 3: Write design.json to disk
                saved_file_path = write_design_json(project_path, design_data, plan_data)

                # Step 4: Re-read and re-validate saved file to guarantee file creation integrity
                with open(saved_file_path, "r", encoding="utf-8") as f:
                    reloaded_design = json.load(f)

                re_val = validate_design_json(reloaded_design, plan_data)
                if not re_val["valid"]:
                    return {
                        "status": "failed",
                        "stage": "design",
                        "errors": [f"Saved design file re-validation failed: {re_val['errors']}"],
                        "ready_for_coding": False,
                    }

                total_tools = sum(len(a.get("tools", [])) for a in reloaded_design.get("agents", []))

                return {
                    "status": "success",
                    "project_path": project_path,
                    "input": plan_file_path,
                    "output": saved_file_path,
                    "design": reloaded_design,
                    "file_path": saved_file_path,
                    "agents_designed": len(reloaded_design.get("agents", [])),
                    "tools_defined": total_tools,
                    "wiring_preserved": True,
                    "schema_valid": True,
                    "ready_for_coding": True,
                    "attempts": attempt,
                }
            else:
                last_errors = validation_res["errors"]
                current_input = (
                    f"Previous design attempt failed validation with the following errors:\n"
                    + "\n".join(f"- {e}" for e in last_errors)
                    + "\n\nPlease fix all errors and return the corrected complete design.json."
                )

        return {
            "status": "failed",
            "stage": "design",
            "errors": [
                f"Design validation failed after {MAX_DESIGN_RETRIES} attempts. Last errors: {last_errors}"
            ],
            "ready_for_coding": False,
        }

    def _run_adk_runner(self, prompt: str) -> str:
        """Run ADK Agent using Runner and InMemorySessionService with automatic key rotation on 429 quota errors."""
        max_attempts = 10
        last_exc = None

        for attempt in range(max_attempts):
            set_gemini_api_key_env()
            self.adk_agent = self._build_adk_agent()

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
            try:
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

                result_text = "".join(output_chunks)
                if result_text.strip():
                    return result_text
            except Exception as e:
                last_exc = e
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota" in err_str or "exhausted" in err_str:
                    time.sleep(1.0)
                    continue
                raise e

        if last_exc:
            raise last_exc
        return ""

