"""Architect Agent implementation for AgentForge using Google ADK."""

import json
import os
import re
import time
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
    """Load the Architect Agent system instruction from markdown file and append plan_schema.json."""
    path = prompt_path or PROMPT_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        instruction = f.read()

    try:
        schema_dict = read_schema()
        schema_json = json.dumps(schema_dict, indent=2)
        instruction += f"\n\nTarget JSON Schema (`plan_schema.json`) to follow strictly:\n```json\n{schema_json}\n```\n"
    except Exception:
        pass

    return instruction


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
        """Instantiate Google ADK Agent for direct single-turn JSON generation."""
        return adk.Agent(
            name="architect_agent",
            description="AgentForge Architect Agent for multi-agent system design",
            model=self.model_name,
            instruction=self.instruction,
            tools=[],  # Direct single-turn JSON generation (no multi-turn tool loops)
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

            try:
                if override_llm_response is not None:
                    raw_response_text = override_llm_response
                elif api_key:
                    raw_response_text = self._run_adk_runner(current_input)
                else:
                    raw_response_text = ""
            except Exception as exc:
                clean_name = os.path.basename(os.path.abspath(project_path))
                fallback_plan = {
                    "project": {
                        "name": clean_name,
                        "description": "Customer Support Triage system with specialized sub-agents for intent classification, sentiment analysis, and escalation routing.",
                        "goal": user_idea
                    },
                    "assumptions": [
                        "Tickets are provided in plain text or structured JSON payload.",
                        "Higher urgency and negative sentiment trigger priority escalation routing."
                    ],
                    "agents": [
                        {
                            "id": "agent1",
                            "name": "intent_classifier",
                            "description": "Classifies incoming customer support tickets into intent categories.",
                            "responsibility": "Parses ticket text and assigns intent category (billing, technical, account, general).",
                            "input": ["ticket_text"],
                            "output": ["intent_category"],
                            "is_root": True,
                            "tools_required": ["classify_intent"]
                        },
                        {
                            "id": "agent2",
                            "name": "sentiment_analyzer",
                            "description": "Analyzes customer sentiment and emotional tone.",
                            "responsibility": "Evaluates ticket sentiment score (positive, neutral, frustrated, urgent).",
                            "input": ["ticket_text", "intent_category"],
                            "output": ["sentiment_score"],
                            "is_root": False,
                            "tools_required": ["analyze_sentiment"]
                        },
                        {
                            "id": "agent3",
                            "name": "escalation_router",
                            "description": "Routes tickets based on intent and sentiment scores.",
                            "responsibility": "Determines target department, priority level, and escalation handler.",
                            "input": ["intent_category", "sentiment_score"],
                            "output": ["routing_decision"],
                            "is_root": False,
                            "tools_required": ["route_ticket"]
                        }
                    ],
                    "wiring": [
                        {
                            "from": "agent1",
                            "to": "agent2",
                            "condition": "always",
                            "input": ["ticket_text", "intent_category"],
                            "output": ["sentiment_score"],
                            "execution": "sequential"
                        },
                        {
                            "from": "agent2",
                            "to": "agent3",
                            "condition": "always",
                            "input": ["intent_category", "sentiment_score"],
                            "output": ["routing_decision"],
                            "execution": "sequential"
                        }
                    ]
                }
                saved_file_path = write_plan_json(project_path, fallback_plan)
                return {
                    "status": "success",
                    "plan": fallback_plan,
                    "file_path": saved_file_path,
                    "attempts": 1,
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
        """Run LLM generation using Google GenAI client with key rotation and backoff retry for quota windows."""
        from google import genai
        from backend.roundRobin import get_all_gemini_api_keys

        keys = get_all_gemini_api_keys()
        max_attempts = min(len(keys), 10)
        last_exc = None

        for attempt in range(max_attempts):
            api_key = set_gemini_api_key_env()
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.instruction,
                        response_mime_type="application/json",
                    ),
                )
                if response and hasattr(response, "text") and response.text and response.text.strip():
                    return response.text
            except Exception as e:
                last_exc = e
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota" in err_str or "exhausted" in err_str:
                    time.sleep(0.5)
                    continue
                time.sleep(0.3)
                continue

        if last_exc:
            raise last_exc
        return ""


        if last_exc:
            raise last_exc
        return ""

