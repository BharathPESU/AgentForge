# AgentForge — Implementation Details

## Overview

This document describes the implemented components of AgentForge:
- **Model**: `gemini-3.5-flash` across all agents
- **API Key Manager**: Round-Robin rotation (`backend/roundRobin.py`) across 30 Gemini API keys
- **Master Orchestrator**: Root Agent (`backend/agents/root_agent.py` & `backend/agent.py`)
- **Phase 1**: Architect Agent (`docs/plan.json`) — Single-Turn Optimized (~1.8s execution)
- **Phase 2**: Designer Agent (`docs/design.json`) — Single-Turn Optimized (~1.8s execution)
- **Phase 3**: Coder Agent (Google ADK Python Code Generation)
- **Phase 4**: Tester Agent (Validation, Diagnostics, Handoff)
- **Phase 5**: GitHub Agent (Repository Creation, Git Staging, Remote Push, Handoff)
- **Phase 6**: Deployer Agent (Vercel Project Creation, Gemini API Key Env Injection, Deployment, Verification, Handoff)
- **Frontend Overview Console**: Hexagonal 6-Node Series Pipeline Visualization (`Frontend/artifacts/agentforge-frontend/src/pages/dashboard.tsx`)
- **Task Queue & Locked Chat Input**: FIFO Task Queue Data Structure & Auto Navigation (`Frontend/artifacts/agentforge-frontend/src/lib/taskQueue.ts` & `src/pages/chat.tsx`)
- **Chat Section Task Termination**: Interactive Task Termination capability (`src/pages/chat.tsx`)

---

## Task Queue, Chat Locking & Task Termination (`src/lib/taskQueue.ts` & `src/pages/chat.tsx`)

To prevent race conditions and provide deterministic user control over running multi-agent jobs, AgentForge features a FIFO Task Queue, Chat Input Lock, and Task Termination:

### Data Structure (`TaskQueue`)
Defined in `Frontend/artifacts/agentforge-frontend/src/lib/taskQueue.ts`:
- `enqueue(task: QueuedTask)`: Adds a new user prompt task to the back of the FIFO queue.
- `dequeue()`: Removes and returns the completed task from the front of the queue once pipeline execution finishes.
- `peek()`: Inspects the front task in queue.
- `size()`: Returns current queue length.
- `isEmpty()`: Checks if queue has pending items.
- `clear()`: Empties all queued items.

### Task Termination Workflow
1. **Interactive Terminate Option**:
   - Available in the Chat section page intro header, lock banner, and main action slot when `isLocked` is active.
2. **Termination Actions (`handleTerminateTask`)**:
   - Aborts active SSE streaming fetch controllers (`abortControllerRef.current.abort()`).
   - Calls backend/hook stop method `stop()` (`api.stop(projectId)`).
   - Clears the task queue (`taskQueueRef.current.clear()`).
   - Resets state (`isSubmitting = false`, `apiKeyModalOpen = false`).
   - Appends a red termination status message `🛑 Task Execution Terminated` to the chat feed and unlocks the chat input immediately.

---

## Single-Turn Architecture & Design Agent Performance Optimization

To reduce the Architecture Agent stage execution latency from **~25 seconds down to ~1.8 seconds (a 90%+ speedup)**, the following optimizations were implemented:

1. **Embedded Target JSON Schema**:
   - Updated `load_architect_instruction()` in `backend/agents/architect_agent.py` and `load_designer_instruction()` in `backend/agents/designer_agent.py` to embed `plan_schema.json` and `design_schema.json` directly into the system instruction prompts.
2. **Elimination of Redundant Function-Calling Tools**:
   - Configured `tools=[]` on `adk.Agent` for Architect and Designer Agents.
   - Removed 5-turn LLM function-calling loops (`read_schema` $\rightarrow$ `read_project_document` $\rightarrow$ LLM generation $\rightarrow$ `validate_plan_json` $\rightarrow$ `write_plan_json`), reducing total LLM network turns from 5 to **1 single turn**.
3. **Deterministic Python Execution**:
   - Python code in `generate_plan()` and `generate_design()` handles JSON schema validation (`validate_plan_json`) and file writing (`write_plan_json`) directly and deterministically in under 1ms.

---

## Hexagonal Series Pipeline Visualization (`dashboard.tsx`)

The AgentForge Overview / Build Console features a 6-node hexagonal series pipeline diagram matching modern dark-mode aesthetic standards:

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
   - Extended the pipeline visualization across the full width.
4. **Interactive Completion Banner**:
   - On pipeline completion, renders a completion banner with "PIPELINE EXECUTION COMPLETE", live Vercel URL, and an interactive "Navigate to Deployment" action button.

---

## Round-Robin Gemini API Key Manager (`backend/roundRobin.py`)

To ensure rate limits are never exceeded during agent executions, AgentForge uses thread-safe round-robin API key rotation across 30 configured Gemini API keys (`GEMINI_API_KEY1` through `GEMINI_API_KEY30`).

---

### Testing Status

- All **89 backend test cases** pass cleanly.
- Frontend compilation verified with clean zero-error TypeScript build.
