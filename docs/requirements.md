# AgentForge System Requirements

## Functional Requirements

### Architect Agent (Implemented)
- Shall accept natural language user input describing a target agent system.
- Shall output valid JSON conforming to `backend/schemas/plan_schema.json`.
- Shall specify a single root orchestrator agent (`is_root: true`).
- Shall enforce stable agent IDs (`agent1`, `agent2`, ...).
- Shall define communication wiring (source, target, condition, execution pattern).
- Shall perform schema validation and up to 3 self-correction retries.
- Shall save output to `docs/plan.json` or `backend/docs/plan.json`.

### Designer Agent (Implemented)
- Shall accept a valid `plan.json` as input.
- Shall reject invalid or missing `plan.json` files with a structured failure payload.
- Shall output valid JSON conforming to `backend/schemas/design_schema.json`.
- Shall generate implementation-ready system prompts for every agent.
- Shall assign tool specifications based on the minimum capability principle.
- Shall preserve agent count, agent IDs, root orchestrator status, and wiring from `plan.json`.
- Shall save output to `docs/design.json` or `backend/docs/design.json`.

### Coder Agent (Implemented)
- Shall accept `plan.json` and `design.json` as input.
- Shall reject invalid or missing plan/design files with a structured failure payload (`missing_plan` or `missing_design`).
- Shall copy `backend/template/` as baseline when project directory is new.
- Shall reuse existing project directory structure without destroying extra files.
- Shall generate `agent.py`, `prompt.py`, and `tools.py` for every agent in `design.json`.
- Shall wire root `agent.py` and update `settings.yaml` matching active agents.
- Shall return structured handoff payload matching `coder_result_schema.json`.

### Tester Agent (Implemented)
- Shall accept `coder_result.json`, `plan.json`, `design.json`, and the generated project as input.
- Shall perform a 15-step validation pipeline covering schema, structure, agents, tools, wiring, tests, smoke test, Vercel structure, security secret scanning, and independent execution.
- Shall generate unit tests in `generated/<project>/tests/` and execute them via pytest.
- Shall output valid JSON conforming to `test_result.json` schema.
- Shall route failures back to `coder_agent`, `designer_agent`, or `architect_agent`.
- Shall NOT modify production source code to fix failures.

### GitHub Agent (Implemented)
- Shall accept `test_result.json`, `plan.json`, `design.json`, and the generated project as input.
- Shall verify `test_result.json` status is `passed` before publishing.
- Shall derive valid repository name slug from `plan.json` metadata.
- Shall perform secret safety check verifying `.env` is ignored and no hardcoded credentials exist.
- Shall create remote GitHub repository using GitHub REST API.
- Shall initialize Git, stage project files, create single clean commit, set remote origin, and push `main` branch.
- Shall output valid JSON conforming to `github_result_schema.json` for handoff to `deployer_agent`.
- Shall NOT modify application source code.

### Later Stages (Pending)
- Deployer agent functional requirements.
