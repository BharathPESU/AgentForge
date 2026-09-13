# Agent Specifications

## 1. Architect Agent

- **Location**: `backend/agents/architect_agent.py`
- **System Prompt**: `backend/prompts/architect_prompt.md`
- **Output Schema**: `backend/schemas/plan_schema.json`
- **Primary Output**: `docs/plan.json` or `backend/docs/plan.json`
- **Responsibility**: Takes a user's natural-language idea, decomposes it into minimal specialized agents, defines responsibilities, root orchestrator, and communication wiring.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 2. Designer Agent

- **Location**: `backend/agents/designer_agent.py`
- **System Prompt**: `backend/prompts/designer_prompt.md`
- **Output Schema**: `backend/schemas/design_schema.json`
- **Input File**: `docs/plan.json` or `backend/docs/plan.json`
- **Primary Output**: `docs/design.json` or `backend/docs/design.json`
- **Responsibility**: Takes `plan.json` and creates implementation-ready agent specifications, complete system prompts, typed inputs/outputs, minimum capability tool specifications, and handoff contracts while preserving architecture wiring.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 3. Coder Agent

- **Location**: `backend/agents/coder_agent.py`
- **System Prompt**: `backend/prompts/coder_prompt.md`
- **Output Schema**: `backend/schemas/coder_result_schema.json`
- **Input Files**: `plan.json`, `design.json`
- **Primary Output**: Working Google ADK Python application in `generated/<project>/`
- **Responsibility**: Copies `backend/template/` as baseline, performs targeted code modifications to create agent subdirectories (`agents/<agent_id>/agent.py`, `prompt.py`, `tools.py`), implements assigned tools, configures `settings.yaml`, and wires the root orchestrator.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 4. Tester Agent

- **Location**: `backend/agents/tester_agent.py`
- **System Prompt**: `backend/prompts/tester_prompt.md`
- **Output Schema**: `backend/schemas/test_result_schema.json`
- **Input Files**: `coder_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Primary Output**: `docs/test_result.json`
- **Responsibility**: Performs 15-step validation suite covering plan/design schemas, project file structure, agent/tool availability, root agent wiring, pytest suite generation and execution, smoke tests, Vercel structure compatibility, secret scanning, and independent execution check.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 5. GitHub Agent

- **Location**: `backend/agents/github_agent.py`
- **System Prompt**: `backend/prompts/github_prompt.md`
- **Output Schema**: `backend/schemas/github_result_schema.json`
- **Input Files**: `test_result.json`, `coder_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Primary Output**: `docs/github_result.json`
- **Responsibility**: Verifies test result status is `passed`, inspects project files, formats repository name slug, checks for secret exposure, creates remote GitHub repository via GitHub REST API, initializes local Git repository, stages project files (excluding `.env`), creates single commit, sets remote origin URL, pushes `main` branch to remote origin, and outputs `docs/github_result.json` for handoff to `deployer_agent`.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 6. Deployer Agent

- **Location**: `backend/agents/deployer_agent.py`
- **System Prompt**: `backend/prompts/deployer_prompt.md`
- **Output Schema**: `backend/schemas/deployment_result_schema.json`
- **Input Files**: `github_result.json`, `test_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Primary Output**: `docs/deployment_result.json`
- **Responsibility**: Verifies GitHub publication succeeded (`status == "success"`) and testing passed (`status == "passed"`), inspects project files, creates or finds corresponding Vercel project, injects `GEMINI_API_KEY` into Vercel environment variables directly without disk storage, deploys generated project to Vercel, verifies deployment status and HTTP URL accessibility, and outputs `docs/deployment_result.json` containing GitHub and Vercel URLs.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

---

## 7. Supervisor Agent

- **Location**: `backend/agents/supervisor_agent.py`
- **System Prompt**: `backend/prompts/supervisor_prompt.md`
- **Input**: `WhiteboardState` (shared whiteboard)
- **Output**: `RoutingDecision` (`next_agent`, `action` in `continue|retry|blocked|finish`, `reason`, `confidence`)
- **Responsibility**: Inspects whiteboard (`current_stage`, `stage_states`, `agent_outputs`, `errors`, `retry_counts`, `artifacts`, `execution_history`), applies deterministic routing (happy-path `architect→designer→coder→tester→github→deployer→finish` and failure routing `implementation→coder`, `design→designer`, `architecture→architect`, `github→github`, `vercel build→coder`, `vercel config→deployer`), enforces `MAX_SUPERVISOR_STEPS=12` and `MAX_AGENT_RETRIES=3`, never performs specialist work.

## 8. Shared Whiteboard Layer (Primary Communication)

- **Models**: `backend/context/models.py` (`WhiteboardState`, `ArtifactReference`, `AgentOutput`, `WhiteboardEvent`, `RoutingDecision`)
- **Whiteboard**: `backend/context/whiteboard.py` (synchronized `read`, `update`, `patch`, `append_event`, `compare_and_update` with `state_version`)
- **Sync**: `backend/context/sync.py` (`StaleWhiteboardUpdateError`, `SynchronizedWhiteboard`)
- **Manager**: `backend/context/manager.py` (`create_run`, `get`, `get_for_project`, `start_agent`, `complete_agent`, `fail_agent`, `persist`, sanitized summaries)
- **Store**: `backend/context/store.py` (in-memory `run_id→Whiteboard` + `project_id→run_id`, persists `whiteboard.json`)
- **Selector**: `backend/context/selector.py` (`WhiteboardContextSelector.for_agent` — compact per-agent context)
- **Events**: `backend/context/events.py` (`make_event`, `AGENT_STARTED`, `AGENT_COMPLETED`, `AGENT_FAILED`, `RETRY`, `RUN_COMPLETED`)
- **Root Orchestrator**: `backend/agents/root_agent.py` implements `USER → SUPERVISOR → WHITEBOARD → SPECIALIST → WHITEBOARD → SUPERVISOR` loop; each specialist does `READ→PERFORM→WRITE→RETURN`.
- **Responsibility**: Runtime source of truth for `run_id`, `project_id`, `current_agent`, `current_stage`, `status`, `progress`, `decisions`, `errors`, `retry_counts`, `artifacts` (references, not large files), `history`. Prevents stale writes, reduces token usage via selector, excludes secrets.

## 9. Legacy Shared Context & Memory Layer (Compatibility)

- **Context Service**: `backend/services/context_service.py`
- **Context Selector**: `backend/services/context_selector.py`
- **Context Prompt Builder**: `backend/services/context_prompt_builder.py`
- **Memory Service**: `backend/services/memory_service.py`
- **Context Tools**: `backend/tools/context_tools.py`
- **Schema**: `backend/schemas/context_schema.json`
- **Responsibility**: Legacy compatibility layer mirroring whiteboard to `context.json`; agents now use whiteboard-first with file fallback.
