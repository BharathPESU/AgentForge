"""FastAPI Main Application Entrypoint for AgentForge.

Exposes RESTful API routes with CORS middleware configured for React frontend integration.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from backend.api.routes import router as api_router

app = FastAPI(
    title="AgentForge Backend API",
    description="RESTful API for AgentForge Automated Multi-Agent Builder Platform powered by Google ADK and Gemini",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for React frontend (Vite, CRA, Next.js, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes with /api prefix
app.include_router(api_router)


@app.get("/", summary="Root API Information")
def root_endpoint():
    """Root endpoint returning API metadata and available service links."""
    return {
        "status": "online",
        "service": "AgentForge Backend API",
        "version": "1.0.0",
        "documentation": "/docs",
        "health_check": "/api/health",
        "endpoints": {
            "full_pipeline": "POST /api/pipeline/run",
            "stage_architect": "POST /api/agents/architect",
            "stage_designer": "POST /api/agents/designer",
            "stage_coder": "POST /api/agents/coder",
            "stage_tester": "POST /api/agents/tester",
            "stage_github": "POST /api/agents/github",
            "stage_deployer": "POST /api/agents/deployer",
            "list_projects": "GET /api/projects",
            "project_details": "GET /api/projects/{project_name}",
        }
    }


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", 8000))
    print(f"Starting AgentForge FastAPI backend on http://{host}:{port}...")
    uvicorn.run("backend.api.main:app", host=host, port=port, reload=True)
