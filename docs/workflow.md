# AgentForge Workflow

## Stage 1: Architecture Planning (Implemented)

1. User inputs a natural language description of an agent system idea.
2. Architect Agent reads instructions from `backend/prompts/architect_prompt.md`.
3. Architect Agent analyzes requirements, determines specialized agents, root orchestrator, and communication wiring.
4. Output candidate JSON is validated against `backend/schemas/plan_schema.json`.
5. If invalid, the agent executes up to 3 retries for self-correction.
6. The validated plan is saved to `docs/plan.json` or `backend/docs/plan.json`.

## Stage 2: Detailed Design (Implemented)

1. Designer Agent receives `plan.json` from `<project_path>/docs/plan.json` or `backend/docs/plan.json`.
2. Designer Agent reads instructions from `backend/prompts/designer_prompt.md`.
3. Designer Agent crafts detailed system prompts, typed inputs/outputs, model parameters, and minimum capability tool specs for every agent while preserving plan wiring and agent IDs.
4. Output candidate JSON is validated against `backend/schemas/design_schema.json` and parity rules against `plan.json`.
5. If invalid, the agent executes up to 3 retries for self-correction.
6. The validated design is saved to `docs/design.json` or `backend/docs/design.json`.

## Stage 3: Code Generation (Implemented)

1. Coder Agent loads `plan.json` and `design.json`.
2. Coder Agent copies `backend/template/` to `generated/<project>/` if target does not exist.
3. Coder Agent generates `agents/<agent_id>/prompt.py`, `tools.py`, and `agent.py` for every designed agent.
4. Coder Agent wires root `agent.py` and updates `settings.yaml`.
5. Coder Agent returns structured handoff payload for testing (`coder_result.json`).

## Stage 4: System Testing (Implemented)

1. Tester Agent receives `coder_result.json`, `plan.json`, `design.json`, and the generated project.
2. Tester Agent validates architecture and design schemas; if invalid, marks `status: blocked` and routes back to Architect or Designer.
3. Tester Agent verifies project structure, agent modules, tool definitions, and root agent wiring.
4. Tester Agent generates and executes unit test suites using pytest.
5. Tester Agent executes smoke test, runs sandboxed terminal execution, launches local FastAPI server in sandboxed environment, executes `curl` requests against `/health`, `/agents`, and `/chat` endpoints, verifies Vercel structure compatibility, scans for secret exposure, and checks independent execution.
6. Tester Agent outputs `docs/test_result.json` specifying overall status (`passed`, `failed`, or `blocked`) and next action handoff (`github_agent` if all checks pass including local server curl tests, or `coder_agent` on failure).

## Stage 5: GitHub Integration (Implemented)

1. GitHub Agent receives `test_result.json`, `plan.json`, `design.json`, and the generated project.
2. GitHub Agent verifies `test_result.json` status is `passed`.
3. GitHub Agent formats repository slug from `plan.json` project metadata.
4. GitHub Agent performs secret safety check to prevent `.env` or credential leakage.
5. GitHub Agent creates remote repository via GitHub REST API (`POST /user/repos`).
6. GitHub Agent initializes local Git repository, stages project files, creates clean commit, sets remote origin, and pushes `main` branch.
7. GitHub Agent outputs `docs/github_result.json` for handoff to `deployer_agent`.

## Stage 6: Deployment (Implemented)

1. Deployer Agent receives `github_result.json`, `test_result.json`, `plan.json`, `design.json`, and the generated project.
2. Deployer Agent verifies `github_result.status == "success"` and `test_result.status == "passed"`.
3. Deployer Agent checks/creates corresponding Vercel project via Vercel REST API (`POST /v9/projects`).
4. Deployer Agent configures Gemini API key as a Vercel environment variable (`GEMINI_API_KEY`) without writing real keys to disk or repository.
5. Deployer Agent deploys generated project files to Vercel (`POST /v13/deployments`).
6. Deployer Agent verifies deployment status and HTTP URL accessibility.
7. Deployer Agent outputs `docs/deployment_result.json` containing GitHub repository URL and Vercel deployment URL.

---

## Shared Whiteboard & Supervisor Orchestration

Throughout Stages 1 through 6, AgentForge is coordinated via the Shared Whiteboard and Supervisor (`backend/context/` + `backend/agents/supervisor_agent.py`):

```text
USER
  │
  ▼
SUPERVISOR — inspects Whiteboard, decides next_agent (architect→designer→coder→tester→github→deployer)
  │
  ▼
SHARED WHITEBOARD — source of truth: user_idea, stage_states, agent_outputs, decisions, errors, retry_counts, artifacts, history, progress, state_version
  │
  ├── Architect reads user_idea → writes architecture → whiteboard
  ├── Designer reads architecture → writes design → whiteboard
  ├── Coder reads architecture+design → writes implementation → whiteboard
  ├── Tester reads arch+design+implementation → writes test_result → whiteboard
  ├── GitHub reads test_result → writes github_result → whiteboard
  └── Deployer reads github+test → writes deployment_result → whiteboard
        │
        ▼
    SUPERVISOR — re-reads whiteboard, handles retries (MAX_AGENT_RETRIES=3), enforces MAX_SUPERVISOR_STEPS=12, routes failures (implementation→coder, design→designer, architecture→architect, github→github, vercel build→coder, vercel config→deployer), then finish
```

- **Stage Initialization**: `WhiteboardManager.create_run(project_id, project_path, user_idea)` creates `WhiteboardState` (`run_id`, `state_version=1`, stage_states=`waiting`).
- **Stage Execution**: `WhiteboardManager.start_agent(board, agent)` marks `in_progress`, `WhiteboardContextSelector.for_agent()` injects compact context, agent does `READ→PERFORM→WRITE`, then `WhiteboardManager.complete_agent()` / `fail_agent()` stores `AgentOutput` + `ArtifactReference` + increments `state_version`.
- **Synchronization**: `Whiteboard` uses `RLock` + `compare_and_update(expected_version)` to prevent stale writes / lost updates.
- **Retry Continuity**: Tester→Coder retry loops preserve `run_id`/`project_id`, increment `retry_counts[coder_agent]`, reset downstream `stage_states` to `waiting` and clear stale outputs via `_reset_downstream_after_retry`, maintain full `execution_history`.
- **Artifact References**: Whiteboard stores `{path, type, producer, status, summary}` — not large file contents.
- **Fallback**: Whiteboard is primary; JSON artifacts (`plan.json`, `design.json`, etc.) are optional compatibility outputs. If whiteboard unavailable, agents fall back to direct file reads.

## Legacy Shared Execution Context (Compatibility)

Old `ContextService` (`backend/services/context_service.py`) is retained for backward compatibility and mirrors whiteboard transitions to `context.json`, but is no longer the communication backbone.

