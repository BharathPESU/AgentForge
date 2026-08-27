"""
FastAPI application entrypoint compatibility shim.
Re-exports FastAPI app from app.py.
"""

from app import app, orchestrator

__all__ = ["app", "orchestrator"]
