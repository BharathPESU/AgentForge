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
- **Task Queue & Locked Chat Input**: FIFO Task Queue Data Structure & Auto Navigation (`Frontend/artifacts/agentforge-frontend/src/lib/taskQueue.ts` & `src/pages/chat.tsx`)

---

## Task Queue & Locked Chat Section (`src/lib/taskQueue.ts` & `src/pages/chat.tsx`)

To prevent race conditions and provide a deterministic multi-agent execution pipeline, AgentForge features a FIFO Task Queue and Chat Input Lock:

### Data Structure (`TaskQueue`)
Defined in `Frontend/artifacts/agentforge-frontend/src/lib/taskQueue.ts`:
- `enqueue(task: QueuedTask)`: Adds a new user prompt task to the back of the FIFO queue.
- `dequeue()`: Removes and returns the completed task from the front of the queue once pipeline execution finishes.
- `peek()`: Inspects the front task in queue.
- `size()`: Returns current queue length.
- `isEmpty()`: Checks if queue has pending items.

### Workflow & Locking Behavior
1. **Submission**: When a prompt is submitted in the Chat section:
   - The prompt is enqueued into `TaskQueue`.
   - A confirmation message `📥 "the task has been added to the queue"` is rendered in the chat feed.
2. **Chat Input Lock**:
   - The chat section immediately locks input (`isLocked = true`).
   - Textarea, Submit button, and Preset prompt buttons are disabled while pipeline execution is active.
   - A lock banner displays: `🔒 Pipeline is currently executing. Chat input is locked until the work is completed.`
3. **Auto Navigation**:
   - Immediately after outputting the queue confirmation message, the page automatically navigates to the **Overview section** (`/`), where the 6-node hexagonal series pipeline starts running.
4. **Unlock**:
   - Upon completion of all 6 pipeline stages (`status === 'COMPLETED'`), the task is dequeued and the Chat input unlocks for new prompts.

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

- All **69 test cases** across `test_architect.py` (9), `test_coder.py` (10), `test_designer.py` (10), `test_tester.py` (10), `test_github.py` (9), `test_deployer.py` (12), `test_root.py` (6), and `test_round_robin.py` (3) pass cleanly.
- Frontend compilation verified with clean zero-error TypeScript build.
