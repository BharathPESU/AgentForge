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
5. Tester Agent executes smoke test, verifies Vercel structure compatibility, scans for secret exposure, and checks independent execution.
6. Tester Agent outputs `docs/test_result.json` specifying overall status (`passed`, `failed`, or `blocked`) and next action handoff (`github_agent` or `coder_agent`).

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

## Shared Execution Context & Memory Integration

Throughout Stages 1 through 6, AgentForge maintains an additive shared execution context (`backend/services/context_service.py`):
- **Stage Initialization**: On run start, `ContextService.create_run_context()` creates a new context (`run_id`, `project_id`, `user_idea`).
- **Stage Transitions**: As each stage begins, `ContextService.set_current_stage()` updates the active stage to `in_progress`.
- **Artifact Registration**: Upon stage completion, outputs are registered as artifact references in `context.json`.
- **Targeted Context Injection**: Downstream agents receive compact context blocks formatted by `ContextSelector` and `ContextPromptBuilder`.
- **Retry Continuity**: During Tester -> Coder retry loops, the same context is maintained with incremented attempt numbers.
- **Fallback**: If context is disabled (`AGENT_CONTEXT_ENABLED=false`), agents revert seamlessly to direct disk artifact reads.

