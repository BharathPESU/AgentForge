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
- **Frontend Overview Console**: Hexagonal 6-Node Series Pipeline Visualization (`Frontend/artifacts/agentforge-frontend/src/pages/dashboard.tsx`)

---

## Hexagonal Series Pipeline Visualization (`dashboard.tsx`)

The AgentForge Overview / Build Console has been updated to feature a 6-node hexagonal series pipeline diagram matching modern dark-mode aesthetic standards:

### Features & Layout
1. **6 Hexagonal Nodes in Series**:
   - **Node 1 (ARCHITECTURE)**: Building/Blueprint Icon (`Building2`), "System architecture defined"
   - **Node 2 (DESIGN)**: Edit Document Icon (`FileEdit`), "Detailed design completed"
   - **Node 3 (CODING)**: Code Brackets Icon (`Code2`), "Code implementation completed"
   - **Node 4 (TESTING)**: Checklist Icon (`ClipboardCheck`), "Testing passed successfully"
   - **Node 5 (GITHUB)**: GitHub Logo (`Github`), "Code pushed to GitHub repository"
   - **Node 6 (DEPLOYMENT)**: Cloud Upload Icon (`CloudUpload`), "Deployed successfully on Vercel"
2. **Dynamic Stage & Pulse Animations**:
   - Running stage nodes feature active keyframe blinking/pulsing glow effects (`animate-hex-blink`).
   - Connecting arrows feature animated particle dashed flow (`animate-dash-flow`).
   - Completed stage nodes feature checkmark badges and glowing borders.
3. **Full-Width Extended Layout**:
   - Removed the obsolete "Project signal" side panel to extend the pipeline visualization across the full width.
4. **Interactive Completion Banner**:
   - On pipeline completion, renders a completion banner with "PIPELINE EXECUTION COMPLETE", live Vercel URL, and an interactive "Navigate to Deployment" action button.

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
- Frontend compilation verified with clean zero-error TypeScript build.
