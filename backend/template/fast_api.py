"""
Google ADK Backend API Service (FastAPI)
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from agent import get_root_agent

app = FastAPI(
    title="Google ADK Multi-Agent API",
    description="RESTful API for Google Agent Development Kit (ADK) Multi-Agent System",
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
    message: str = Field(..., description="User query or instruction for the agent system", min_length=1)
    agent_id: Optional[str] = Field(None, description="Optional target sub-agent ID (e.g., 'agent1', 'agent2')")
    auto_route: bool = Field(True, description="Whether the orchestrator should automatically select the best agent")


class PipelineRequest(BaseModel):
    query: str = Field(..., description="High-level goal for the multi-agent collaboration pipeline", min_length=1)


class AgentInvokeRequest(BaseModel):
    prompt: str = Field(..., description="Direct prompt sent to the specific agent")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional context or previous outputs")


@app.get("/health", summary="Health Check")
def health_check():
    return {
        "status": "healthy",
        "service": "Google ADK Multi-Agent Service",
        "api_key_configured": bool(os.environ.get("GOOGLE_API_KEY"))
    }


@app.get("/agents", summary="List Registered Agents")
def list_registered_agents():
    orchestrator = get_root_agent()
    return {
        "count": len(orchestrator.sub_agents),
        "agents": orchestrator.list_agents()
    }


@app.post("/chat", summary="Chat with Agent Collective")
def chat_endpoint(request: ChatRequest):
    orchestrator = get_root_agent()
    if request.agent_id:
        if request.agent_id not in orchestrator.sub_agents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{request.agent_id}' is not registered. Available: {list(orchestrator.sub_agents.keys())}"
            )
        result = orchestrator.run_agent(request.agent_id, request.message)
        return {
            "mode": "direct_agent",
            "agent_id": request.agent_id,
            "result": result
        }

    result = orchestrator.chat(request.message, auto_route=request.auto_route)
    return result


@app.post("/run", summary="Execute Full Multi-Agent Pipeline")
def run_pipeline_endpoint(request: PipelineRequest):
    orchestrator = get_root_agent()
    try:
        pipeline_result = orchestrator.run_pipeline(request.query)
        return pipeline_result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {str(e)}"
        )


@app.post("/agents/{agent_id}/invoke", summary="Direct Sub-Agent Invocation")
def invoke_single_agent(agent_id: str, request: AgentInvokeRequest):
    orchestrator = get_root_agent()
    if agent_id not in orchestrator.sub_agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found. Available: {list(orchestrator.sub_agents.keys())}"
        )
    return orchestrator.run_agent(agent_id, request.prompt, context=request.context)


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", 8000))
    print(f"Starting Google ADK FastAPI backend on {host}:{port}...")
    uvicorn.run("fast_api:app", host=host, port=port, reload=True)