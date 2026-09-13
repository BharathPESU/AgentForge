# AgentForge System Architecture

## Overview

AgentForge is an automated multi-agent builder platform powered by Google ADK and Gemini LLMs.

**Orchestration Model: Shared Whiteboard + Supervisor**

```text
              ┌─────────────────────┐
              │   SUPERVISOR AGENT  │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  SHARED WHITEBOARD  │
              │                     │
              │ Context             │
              │ State               │
              │ Memory              │
              │ Decisions           │
              │ Errors              │
              │ History             │
              │ Progress            │
              └──────────┬──────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
     SPECIALIST       SPECIALIST       SPECIALIST
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
                    WHITEBOARD
```

The Supervisor controls the workflow. The Whiteboard is the primary runtime communication mechanism. Specialist agents communicate via the Whiteboard, not direct JSON files.

Legacy artifact flow (now optional compatibility outputs, not communication backbone):

```text
User Idea (Natural Language)
            │
            ▼
    [Architect Agent]  (Implemented)
            │
            ▼
     docs/plan.json            (optional artifact — whiteboard is primary)
            │
            ▼
    [Designer Agent]   (Implemented)
            │
            ▼
    docs/design.json            (optional artifact — whiteboard is primary)
            │
            ▼
    [Coder Agent]      (Implemented)
            │
            ▼
   generated/<project>/         (artifact reference on whiteboard)
            │
            ▼
    [Tester Agent]     (Implemented)
            │
            ▼
  docs/test_result.json         (optional artifact)
            │
            ▼
    [GitHub Agent]     (Implemented)
            │
            ▼
 docs/github_result.json        (optional artifact)
            │
            ▼
    [Deployer Agent]   (Implemented)
            │
            ▼
docs/deployment_result.json     (optional artifact)
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

## Shared Whiteboard & Supervisor Layer (Primary Communication)

AgentForge now uses a synchronized Shared Whiteboard as the runtime source of truth, coordinated by a Supervisor Agent:

- **Whiteboard State** (`backend/context/models.py`): Strongly typed `WhiteboardState` with `run_id`, `project_id`, `current_agent`, `current_stage`, `status`, `stage_states`, `agent_context`, `agent_outputs`, `decisions`, `errors`, `retry_counts`, `artifacts`, `execution_history`, `progress`, `state_version`.
- **Synchronized Access** (`backend/context/whiteboard.py` + `backend/context/sync.py`): Thread-safe `read()`, `update()`, `patch()`, `append_event()`, `compare_and_update()` with optimistic `state_version` checks (`StaleWhiteboardUpdateError`).
- **Manager** (`backend/context/manager.py`): `create_run()`, `start_agent()`, `complete_agent()`, `fail_agent()`, `append_event()`, `persist()` — persists lightweight `whiteboard.json` to `generated/<project>/docs/whiteboard.json` without storing secrets or large source files.
- **Store** (`backend/context/store.py`): In-memory registry `run_id -> Whiteboard` + `project_id -> run_id` with disk fallback.
- **Selector** (`backend/context/selector.py`): `WhiteboardContextSelector.for_agent()` returns compact per-agent context (architect: idea only; designer: architecture; coder: architecture+design; tester: arch+design+implementation; github: test_result; deployer: github+test).
- **Supervisor** (`backend/agents/supervisor_agent.py`): Deterministic routing based on whiteboard — `decide_next()` implements happy-path `architect→designer→coder→tester→github→deployer→finish` + failure routing (`tester implementation → coder`, `design → designer`, `architecture → architect`, `github → github`, `vercel build → coder`, `vercel config → deployer`) with `MAX_SUPERVISOR_STEPS=12` and `MAX_AGENT_RETRIES=3`.
- **Supervisor Prompt** (`backend/prompts/supervisor_prompt.md`): Instruction defining team, RoutingRules, and structured `RoutingDecision` (`next_agent`, `action` in `continue|retry|blocked|finish`, `reason`, `confidence`).
- **Root Orchestrator** (`backend/agents/root_agent.py`): `USER → SUPERVISOR → WHITEBOARD → SPECIALIST → WHITEBOARD → SUPERVISOR` loop. Each specialist does `READ WHITEBOARD → PERFORM TASK → WRITE RESULT TO WHITEBOARD → RETURN TO SUPERVISOR`. No direct agent-to-agent calls.
- **API Observability** (`backend/api/routes.py`): `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/state`, `GET /api/runs/{run_id}/events`, `GET /api/whiteboard/{project_name}` expose `current_agent`, `current_stage`, `status`, `progress`, `retry_counts`, `errors`, `execution_history` for the React dashboard. `GET /api/projects/{project}/execution` and `/logs` prefer whiteboard when available.
- **Artifact References**: Whiteboard stores `{artifact_type, path, producer, status, summary}` rather than large file contents. Generated project files remain on filesystem / Supabase Storage.

## Legacy Shared Context & Memory Layer (Compatibility)

- **Context Service** (`backend/services/context_service.py`): Maintained for backward compatibility; mirrors whiteboard stage transitions to `context.json` but is no longer the communication backbone.
- **Context Selector** (`backend/services/context_selector.py`): Legacy selector for old `context.json` flow.
- **Context Tools** (`backend/tools/context_tools.py`): Legacy helpers.
- **Long-Term Memory Service** (`backend/services/memory_service.py`): Optional persistent memory.
- **Fallback Mechanism**: Agents are whiteboard-first with file fallback: `designer` reads `architecture` from whiteboard, `coder` reads `architecture+design`, `tester` reads `implementation`, etc. If whiteboard unavailable or disabled, agents gracefully fall back to reading JSON artifacts directly from disk. JSON artifacts (`plan.json`, `design.json`, etc.) remain as optional user-visible outputs but are NOT required for inter-agent communication.

