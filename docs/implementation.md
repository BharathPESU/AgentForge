# AgentForge — Implementation Details

## Overview

This document describes the implemented components of AgentForge:
- **Model**: `gemini-3.5-flash` across all agents
- **API Key Manager**: Round-Robin rotation (`backend/roundRobin.py`) across 30 Gemini API keys
- **Master Orchestrator**: Root Agent (`backend/agents/root_agent.py` & `backend/agent.py`)
- **Phase 1**: Architect Agent (`docs/plan.json`)
- **Phase 2**: Designer Agent (`docs/design.json`)
- **Phase 3**: Coder Agent (Google ADK Python Code Generation)
- **Phase 4**: Tester Agent (Validation, Diagnostics, Handoff)
- **Phase 5**: GitHub Agent (Repository Creation, Git Staging, Remote Push, Handoff)
- **Phase 6**: Deployer Agent (Vercel Project Creation, Gemini API Key Env Injection, Deployment, Verification, Handoff)

---

## Round-Robin Gemini API Key Manager (`backend/roundRobin.py`)

To ensure rate limits are never exceeded during agent executions, AgentForge uses thread-safe round-robin API key rotation across 30 configured Gemini API keys (`GEMINI_API_KEY1` through `GEMINI_API_KEY30`).

### Functions
- `get_next_gemini_api_key() -> str`: Returns the next API key in round-robin sequence.
- `set_gemini_api_key_env() -> str`: Selects the next key and updates `os.environ["GEMINI_API_KEY"]` and `os.environ["GOOGLE_API_KEY"]`.
- `get_all_gemini_api_keys() -> List[str]`: Retrieves all loaded API keys.
- `reset_round_robin()`: Resets counter for testing.

---

## Agent Model Configuration

All agents default to `gemini-3.5-flash`:
- **Architect Agent** (`backend/agents/architect_agent.py`)
- **Designer Agent** (`backend/agents/designer_agent.py`)
- **Coder Agent** (`backend/agents/coder_agent.py`)
- **Tester Agent** (`backend/agents/tester_agent.py`)
- **GitHub Agent** (`backend/agents/github_agent.py`)
- **Deployer Agent** (`backend/agents/deployer_agent.py`)
- **Root Agent** (`backend/agents/root_agent.py`)
- **Settings**: `backend/config/settings.yaml`

---

### Testing Status

- All **69 test cases** across `test_architect.py` (9), `test_coder.py` (10), `test_designer.py` (10), `test_tester.py` (10), `test_github.py` (9), `test_deployer.py` (12), `test_root.py` (6), and `test_round_robin.py` (3) pass cleanly.
