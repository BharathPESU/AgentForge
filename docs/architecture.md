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
    [Coder Agent]      (Pending)
            │
            ▼
    [Tester Agent]     (Pending)
            │
            ▼
    [Deployer Agent]   (Pending)
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
