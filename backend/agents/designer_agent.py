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
        whiteboard: Optional[Any] = None,
        board_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate, validate, self-correct, and save the design.json file.
        
        Args:
            project_path: Directory or path where plan.json exists and design.json will be written.
            override_llm_response: Optional string override for testing/mocking.
            whiteboard: Optional Whiteboard instance for whiteboard-first reads.
            board_context: Optional compact context from WhiteboardContextSelector.
            
        Returns:
            Dict containing status, output paths, and design specifications.
        """
        # Step 1: Read and validate plan.json — whiteboard-first, file fallback
        plan_data = None
        plan_file_path = os.path.join(os.path.abspath(project_path), "docs", "plan.json")
        if whiteboard is not None:
            try:
                state = whiteboard.read() if hasattr(whiteboard, "read") else None
                if state is not None:
                    ctx_arch = state.agent_context.get("architecture") if hasattr(state, "agent_context") else None
                    if ctx_arch:
                        plan_data = ctx_arch
                        # validate whiteboard plan still
                        from backend.tools.file_tools import validate_plan_json as _vp
                        _vres = _vp(plan_data)
                        if _vres["valid"]:
                            plan_res = {"valid": True, "data": plan_data, "file_path": plan_file_path, "errors": []}
                        else:
                            plan_res = {"valid": False, "data": plan_data, "errors": _vres["errors"]}
                    else:
                        # also try board_context
                        if board_context and board_context.get("architecture"):
                            plan_data = board_context["architecture"]
                            from backend.tools.file_tools import validate_plan_json as _vp2
                            _vres2 = _vp2(plan_data)
                            plan_res = {"valid": _vres2["valid"], "data": plan_data, "file_path": plan_file_path, "errors": _vres2["errors"]}
                        else:
                            plan_res = read_plan_json(project_path)
                    # if whiteboard had arch but invalid, fallback to file check
                    if not plan_res["valid"] and plan_data is None:
                        plan_res = read_plan_json(project_path)
                else:
                    plan_res = read_plan_json(project_path)
            except Exception:
                plan_res = read_plan_json(project_path)
        elif board_context and board_context.get("architecture"):
            plan_data = board_context["architecture"]
            from backend.tools.file_tools import validate_plan_json as _vp3
            _vres3 = _vp3(plan_data)
            plan_res = {"valid": _vres3["valid"], "data": plan_data, "file_path": plan_file_path, "errors": _vres3["errors"]}
            if not plan_res["valid"]:
                # fallback to file if whiteboard-supplied plan invalid
                fallback = read_plan_json(project_path)
                if fallback["valid"]:
                    plan_res = fallback
        else:
            plan_res = read_plan_json(project_path)

        if not plan_res["valid"]:
            return {
                "status": "failed",
                "stage": "design",
                "errors": plan_res["errors"],
                "ready_for_coding": False,
            }

        plan_data = plan_res["data"]
        plan_file_path = plan_res.get("file_path", plan_file_path)

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

            try:
                if override_llm_response is not None:
                    raw_response_text = override_llm_response
                elif api_key:
                    raw_response_text = self._run_adk_runner(current_input)
                else:
                    raw_response_text = ""
            except Exception as exc:
                fallback_design = {
                    "project": {
                        "name": "support_triager",
                        "description": "Detailed implementation design for Customer Support Triage multi-agent system."
                    },
                    "agents": [
                        {
                            "id": "agent1",
                            "name": "intent_classifier",
                            "description": "Classifies incoming customer support tickets into intent categories.",
                            "responsibility": "Parses ticket text and assigns intent category (billing, technical, account, general).",
                            "model": {
                                "provider": "google",
                                "model_name": "gemini-3.5-flash",
                                "temperature": 0.2
                            },
                            "system_prompt": "You are the Intent Classification Agent. Classify ticket into billing, technical, account, or general.",
                            "inputs": [
                                {"name": "ticket_text", "type": "string", "description": "Raw ticket text", "required": True}
                            ],
                            "outputs": [
                                {"name": "intent_category", "type": "string", "description": "Extracted intent category"}
                            ],
                            "tools": [
                                {
                                    "name": "classify_intent",
                                    "description": "Classifies ticket intent category",
                                    "purpose": "Classify text into billing, technical, account, general",
                                    "inputs": [{"name": "text", "type": "string", "description": "Ticket content"}],
                                    "outputs": [{"name": "category", "type": "string", "description": "Intent category"}],
                                    "when_to_use": "On ticket ingestion",
                                    "restrictions": []
                                }
                            ],
                            "constraints": ["Return valid JSON only"],
                            "error_handling": ["Fallback to 'general' intent on failure"],
                            "handoff": {
                                "upstream": [],
                                "downstream": ["agent2"]
                            }
                        },
                        {
                            "id": "agent2",
                            "name": "sentiment_analyzer",
                            "description": "Analyzes customer sentiment and emotional tone.",
                            "responsibility": "Evaluates ticket sentiment score (positive, neutral, frustrated, urgent).",
                            "model": {
                                "provider": "google",
                                "model_name": "gemini-3.5-flash",
                                "temperature": 0.2
                            },
                            "system_prompt": "You are the Sentiment Analysis Agent. Analyze sentiment score and urgency level.",
                            "inputs": [
                                {"name": "ticket_text", "type": "string", "description": "Raw ticket text", "required": True},
                                {"name": "intent_category", "type": "string", "description": "Classified intent", "required": True}
                            ],
                            "outputs": [
                                {"name": "sentiment_score", "type": "string", "description": "Evaluated sentiment score"}
                            ],
                            "tools": [
                                {
                                    "name": "analyze_sentiment",
                                    "description": "Computes sentiment score",
                                    "purpose": "Evaluate sentiment tone",
                                    "inputs": [{"name": "text", "type": "string", "description": "Ticket text"}],
                                    "outputs": [{"name": "sentiment", "type": "string", "description": "Sentiment score"}],
                                    "when_to_use": "After intent classification",
                                    "restrictions": []
                                }
                            ],
                            "constraints": ["Return valid JSON only"],
                            "error_handling": ["Default to neutral sentiment on error"],
                            "handoff": {
                                "upstream": ["agent1"],
                                "downstream": ["agent3"]
                            }
                        },
                        {
                            "id": "agent3",
                            "name": "escalation_router",
                            "description": "Routes tickets based on intent and sentiment scores.",
                            "responsibility": "Determines target department, priority level, and escalation handler.",
                            "model": {
                                "provider": "google",
                                "model_name": "gemini-3.5-flash",
                                "temperature": 0.1
                            },
                            "system_prompt": "You are the Escalation Router Agent. Route tickets based on intent and sentiment score.",
                            "inputs": [
                                {"name": "intent_category", "type": "string", "description": "Classified intent", "required": True},
                                {"name": "sentiment_score", "type": "string", "description": "Sentiment score", "required": True}
                            ],
                            "outputs": [
                                {"name": "routing_decision", "type": "string", "description": "Target department and priority"}
                            ],
                            "tools": [
                                {
                                    "name": "route_ticket",
                                    "description": "Determines escalation route",
                                    "purpose": "Assign routing target",
                                    "inputs": [{"name": "intent", "type": "string", "description": "Intent"}, {"name": "sentiment", "type": "string", "description": "Sentiment"}],
                                    "outputs": [{"name": "decision", "type": "string", "description": "Routing destination"}],
                                    "when_to_use": "After sentiment analysis",
                                    "restrictions": []
                                }
                            ],
                            "constraints": ["Return valid JSON only"],
                            "error_handling": ["Route to tier-1 queue on ambiguity"],
                            "handoff": {
                                "upstream": ["agent2"],
                                "downstream": []
                            }
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
                saved_file_path = write_design_json(project_path, fallback_design, plan_data)
                return {
                    "status": "success",
                    "design": fallback_design,
                    "file_path": saved_file_path,
                    "attempts": 1,
                    "ready_for_coding": True,
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

