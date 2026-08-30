# AgentForge System Architecture

## Overview

AgentForge is an automated multi-agent builder platform powered by Google ADK and Gemini LLMs.

```text
User Idea (Natural Language)
            │
            ▼
    [Architect Agent]  (Implemented)
            │
            ▼
     docs/plan.json
            │
            ▼
    [Designer Agent]   (Implemented)
            │
            ▼
    docs/design.json
            │
            ▼
    [Coder Agent]      (Implemented)
            │
            ▼
   generated/<project>/
            │
            ▼
    [Tester Agent]     (Implemented)
            │
            ▼
  docs/test_result.json
            │
            ▼
    [GitHub Agent]     (Implemented)
            │
            ▼
 docs/github_result.json
            │
            ▼
    [Deployer Agent]   (Implemented)
            │
            ▼
docs/deployment_result.json
```

## Implemented Architecture Stages

### 1. Architect Agent
- **Component**: `backend/agents/architect_agent.py`
- **Output Artifact**: `docs/plan.json` or `backend/docs/plan.json`
- **Validation**: Strict JSON Schema (`backend/schemas/plan_schema.json`) + semantic checks.

### 2. Designer Agent
- **Component**: `backend/agents/designer_agent.py`
- **Input Artifact**: `docs/plan.json` or `backend/docs/plan.json`
- **Output Artifact**: `docs/design.json` or `backend/docs/design.json`
- **Validation**: Strict JSON Schema (`backend/schemas/design_schema.json`) + parity checks with `plan.json`.

### 3. Coder Agent
- **Component**: `backend/agents/coder_agent.py`
- **Input Artifacts**: `plan.json`, `design.json`
- **Output**: Working Google ADK Python application copied from `backend/template/` and updated in `generated/<project>/`
- **Validation**: Pre-generation validation of plan/design + handoff contract check.

### 4. Tester Agent
- **Component**: `backend/agents/tester_agent.py`
- **Input Artifacts**: `coder_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Output Artifact**: `docs/test_result.json`
- **Validation**: 15-step validation pipeline (plan/design schema checks, project structure, agent/tool availability, root agent wiring, pytest suite execution, smoke test, Vercel structure check, secret exposure scanning, independent run verification).

### 5. GitHub Agent
- **Component**: `backend/agents/github_agent.py`
- **Input Artifacts**: `test_result.json`, `coder_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Output Artifact**: `docs/github_result.json`
- **Validation**: Test result verification, secret safety check, remote repository creation via GitHub REST API, git commit, remote push.

### 6. Deployer Agent
- **Component**: `backend/agents/deployer_agent.py`
- **Input Artifacts**: `github_result.json`, `test_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Output Artifact**: `docs/deployment_result.json`
- **Validation**: GitHub result verification, test result verification, Vercel project management, direct Vercel environment variable injection for Gemini API key, Vercel deployment, URL verification.

---

## Shared Context & Memory Layer

AgentForge includes a non-intrusive shared context compatibility layer around the existing 6-agent compiler pipeline:

- **Context Service** (`backend/services/context_service.py`): Manages thread-safe execution run contexts, stage history, and event logging in `generated/<project>/docs/context.json`.
- **Context Selector** (`backend/services/context_selector.py`): Extracts stage-relevant context summaries for downstream agents to optimize token usage.
- **Context Tools** (`backend/tools/context_tools.py`): Exposes deterministic helper functions for querying active context and retrieving full JSON artifacts on demand.
- **Long-Term Memory Service** (`backend/services/memory_service.py`): Optional persistent memory store for reusable architecture patterns and preferences.
- **Fallback Mechanism**: If context storage is disabled (`AGENT_CONTEXT_ENABLED=false`) or fails, agents gracefully fall back to reading JSON artifacts directly from disk.

