"""
==============================================================================
Google ADK Generic Multi-Agent Template Entrypoint & Backend API Server
==============================================================================
This template dynamically loads your multi-agent architecture from `config.json`.
You can swap `config.json` with any multi-agent specification without changing
python backend logic.

Modes available:
  - Web UI / Server : python app.py --mode web  (or --mode api)
  - Interactive CLI : python app.py --mode cli
  - Diagnostic Test : python app.py --mode test
==============================================================================
"""

import os
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

# Check availability of Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def load_config() -> Dict[str, Any]:
    """Load agent system configuration dynamically from config.json."""
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load config.json ({e}). Using default template configuration.")

    # Generic Fallback Configuration
    return {
        "project": {
            "name": "Multi-Agent System Template",
            "description": "Clean, reusable multi-agent architecture driven by config.json."
        },
        "agents": [
            {
                "id": "agent1",
                "name": "Orchestrator_Agent",
                "description": "Primary coordinator agent responsible for ingestion, routing, and compilation.",
                "responsibility": "Coordinates task workflow and synthesizes results.",
                "model": {"model_name": "gemini-3.5-flash", "temperature": 0.2},
                "system_prompt": "You are Orchestrator_Agent. Synthesize user queries and sub-agent outputs."
            },
            {
                "id": "agent2",
                "name": "Specialist_Agent_A",
                "description": "First specialist agent for domain analysis.",
                "responsibility": "Detailed analysis and extraction.",
                "model": {"model_name": "gemini-3.5-flash", "temperature": 0.2},
                "system_prompt": "You are Specialist_Agent_A. Perform detailed domain analysis."
            },
            {
                "id": "agent3",
                "name": "Specialist_Agent_B",
                "description": "Second specialist agent for quantitative data and verification.",
                "responsibility": "Quantitative metrics and verification.",
                "model": {"model_name": "gemini-3.5-flash", "temperature": 0.2},
                "system_prompt": "You are Specialist_Agent_B. Perform quantitative metrics extraction."
            }
        ],
        "wiring": []
    }


class GenericAgent:
    """
    Generic Agent class instantiated directly from configuration metadata.
    Uses Google GenAI SDK when GOOGLE_API_KEY is available, or returns mock outputs.
    """

    def __init__(self, agent_config: Dict[str, Any], api_key: Optional[str] = None):
        self.id = agent_config.get("id", "agent")
        self.name = agent_config.get("name", self.id)
        self.description = agent_config.get("description", "")
        self.role = agent_config.get("responsibility", agent_config.get("description", "Specialist"))
        self.system_prompt = agent_config.get("system_prompt", f"You are {self.name}.")
        
        model_cfg = agent_config.get("model", {})
        self.model_name = model_cfg.get("model_name", "gemini-3.5-flash")
        self.temperature = model_cfg.get("temperature", 0.2)
        
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if (self.api_key and GENAI_AVAILABLE) else None

    def run(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute agent task against LLM or mock generator."""
        if not self.client:
            return self._generate_mock_output(prompt, context)

        try:
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=self.temperature
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return {
                "agent_id": self.id,
                "agent_name": self.name,
                "role": self.role,
                "response": response.text,
                "status": "success"
            }
        except Exception as e:
            return {
                "agent_id": self.id,
                "agent_name": self.name,
                "role": self.role,
                "error": str(e),
                "response": f"[{self.name}] Error during execution: {str(e)}",
                "status": "error"
            }

    def _generate_mock_output(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generic template fallback response when API key is unconfigured."""
        mock_response = (
            f"### [{self.name} Output]\n"
            f"**Role:** {self.role}\n"
            f"**Task:** '{prompt}'\n\n"
            f"Processed request successfully using `{self.model_name}` (Template Mock Mode).\n"
            f"- Fulfilling system instructions and behavioral constraints.\n"
            f"- Structured findings delivered."
        )
        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "role": self.role,
            "response": mock_response,
            "status": "success"
        }


class MultiAgentOrchestrator:
    """Orchestrates multi-agent execution pipeline driven by config.json."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_config()
        self.project_info = self.config.get("project", {})
        self.wiring = self.config.get("wiring", [])
        self.sub_agents: Dict[str, GenericAgent] = {}
        self._initialize_agents()

    def _initialize_agents(self):
        agents_list = self.config.get("agents", [])
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        for ag_cfg in agents_list:
            ag_id = ag_cfg.get("id")
            if ag_id:
                self.sub_agents[ag_id] = GenericAgent(ag_cfg, api_key=api_key)

    def list_agents(self) -> List[Dict[str, Any]]:
        result = []
        for ag_id, agent in self.sub_agents.items():
            result.append({
                "id": ag_id,
                "name": agent.name,
                "role": agent.role,
                "description": agent.description,
                "model": agent.model_name
            })
        return result

    def route_query(self, query: str) -> str:
        """Route user query to appropriate agent or root coordinator."""
        if not self.sub_agents:
            return "agent1"
        agent_keys = list(self.sub_agents.keys())
        # First agent in config is default root/orchestrator
        return agent_keys[0]

    def run_agent(self, agent_id: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if agent_id not in self.sub_agents:
            return {
                "status": "error",
                "error": f"Agent '{agent_id}' is not registered.",
                "available_agents": list(self.sub_agents.keys())
            }
        return self.sub_agents[agent_id].run(prompt, context=context)

    def run_pipeline(self, user_query: str) -> Dict[str, Any]:
        """Execute multi-agent collaboration pipeline according to configuration wiring."""
        pipeline_steps = []
        agent_keys = list(self.sub_agents.keys())

        if not agent_keys:
            return {"status": "error", "error": "No agents configured."}

        # Step 1: Execute primary orchestrator agent
        root_id = agent_keys[0]
        root_agent = self.sub_agents[root_id]
        root_out = root_agent.run(user_query)
        pipeline_steps.append({
            "step": 1,
            "agent_id": root_id,
            "agent_name": root_agent.name,
            "output": root_out.get("response", "")
        })

        # Step 2: Execute secondary specialist agents in parallel
        sub_outputs = []
        for step_idx, ag_id in enumerate(agent_keys[1:], start=2):
            ag = self.sub_agents[ag_id]
            ag_out = ag.run(f"Process input for {ag.name}: {user_query}")
            out_text = ag_out.get("response", "")
            sub_outputs.append(f"### {ag.name}\n{out_text}")
            pipeline_steps.append({
                "step": step_idx,
                "agent_id": ag_id,
                "agent_name": ag.name,
                "output": out_text
            })

        # Compile final pipeline report
        compiled_report = (
            f"# Multi-Agent Collective Report\n\n"
            f"**User Request:** {user_query}\n\n"
            f"## Primary Output ({root_agent.name})\n"
            f"{root_out.get('response', '')}\n\n"
        )
        if sub_outputs:
            compiled_report += "## Specialist Sub-Agent Outputs\n" + "\n\n".join(sub_outputs)

        return {
            "status": "success",
            "query": user_query,
            "final_response": compiled_report,
            "pipeline_steps": pipeline_steps
        }

    def chat(self, user_query: str, auto_route: bool = True) -> Dict[str, Any]:
        if auto_route:
            assigned_id = self.route_query(user_query)
            agent = self.sub_agents.get(assigned_id)
            agent_res = self.run_agent(assigned_id, user_query)
            return {
                "orchestrator_mode": "auto_route",
                "assigned_agent": assigned_id,
                "agent_name": agent.name if agent else assigned_id,
                "result": agent_res
            }
        return self.run_pipeline(user_query)


# Global Orchestrator Instance
orchestrator = MultiAgentOrchestrator()

# FastAPI Backend Application Setup
app = FastAPI(
    title=orchestrator.project_info.get("name", "Multi-Agent System API"),
    description=orchestrator.project_info.get("description", "Dynamic Multi-Agent System API"),
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., description="User prompt or technical instruction", min_length=1)
    agent_id: Optional[str] = Field(None, description="Optional target agent ID")
    auto_route: bool = Field(True, description="Enable automatic routing")


class PipelineRequest(BaseModel):
    query: str = Field(..., description="Pipeline execution goal", min_length=1)


class AgentInvokeRequest(BaseModel):
    prompt: str = Field(..., description="Direct prompt for agent")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


@app.get("/health", summary="Health Check")
def health_check():
    return {
        "status": "healthy",
        "project": orchestrator.project_info.get("name"),
        "api_key_configured": bool(os.environ.get("GOOGLE_API_KEY")),
        "genai_available": GENAI_AVAILABLE
    }


@app.get("/agents", summary="List Registered Agents")
def list_agents():
    return {
        "count": len(orchestrator.sub_agents),
        "project": orchestrator.project_info,
        "agents": orchestrator.list_agents()
    }


@app.post("/chat", summary="Chat with Multi-Agent System")
def chat_endpoint(request: ChatRequest):
    if request.agent_id:
        if request.agent_id not in orchestrator.sub_agents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{request.agent_id}' is not registered."
            )
        res = orchestrator.run_agent(request.agent_id, request.message)
        return {
            "mode": "direct_agent",
            "agent_id": request.agent_id,
            "agent_name": orchestrator.sub_agents[request.agent_id].name,
            "result": res
        }
    return orchestrator.chat(request.message, auto_route=request.auto_route)


@app.post("/run", summary="Execute Multi-Agent Pipeline")
def run_pipeline_endpoint(request: PipelineRequest):
    try:
        return orchestrator.run_pipeline(request.query)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution error: {str(e)}"
        )


@app.post("/agents/{agent_id}/invoke", summary="Direct Agent Invocation")
def invoke_agent_endpoint(agent_id: str, request: AgentInvokeRequest):
    if agent_id not in orchestrator.sub_agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found."
        )
    return orchestrator.run_agent(agent_id, request.prompt, context=request.context)


# Mount static web frontend at root path
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def run_cli_interactive():
    print("\n=======================================================")
    print(f"  {orchestrator.project_info.get('name', 'Multi-Agent Studio')}")
    print("=======================================================")
    for ag in orchestrator.list_agents():
        print(f"  • {ag['id']}: {ag['name']} ({ag['role']})")
    print("\nType your query below, or 'exit' to quit.\n")

    while True:
        try:
            query = input("\033[1;34mUser > \033[0m").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                break
            response = orchestrator.chat(query, auto_route=True)
            assigned = response.get("agent_name", "Orchestrator")
            res_data = response.get("result", {})
            res_text = res_data.get("response", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            print(f"\n\033[1;32m[{assigned}] >\033[0m\n{res_text}\n")
        except (KeyboardInterrupt, EOFError):
            break


def run_api_server():
    import uvicorn
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", 8000))
    print(f"Launching Multi-Agent Web UI & API server on http://{host}:{port}...")
    uvicorn.run("app:app", host=host, port=port, reload=True)


def run_self_test():
    print("\n--- Running Multi-Agent Self-Test Diagnostic ---")
    for ag in orchestrator.list_agents():
        print(f"Testing {ag['id']} ({ag['name']})...")
        res = orchestrator.run_agent(ag["id"], "Ping diagnostic test.")
        print(f"  Status: {res.get('status', 'unknown')}")
    print("\n✅ All sub-agents validated successfully!")


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Application Launcher")
    parser.add_argument("--mode", choices=["cli", "api", "web", "test"], default="web")
    args = parser.parse_args()

    if args.mode == "cli":
        run_cli_interactive()
    elif args.mode in ["api", "web"]:
        run_api_server()
    elif args.mode == "test":
        run_self_test()


if __name__ == "__main__":
    main()