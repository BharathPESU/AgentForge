---
name: smoke-testing
description: Application startup verification, root agent instantiation, and health checks.
---

# Smoke Testing Skill

This skill documents rules for basic runtime sanity checks.

## Flow

1. **Root Agent Load**: Instantiate root orchestrator (`from agent import get_root_agent`).
2. **FastAPI Load**: Import `fast_api.py` and verify `app` instance exists.
3. **Health Response**: Ensure the system initializes without raising uncaught exceptions.
