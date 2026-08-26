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

### Later Stages (Pending)
- Coder, Tester, GitHub, Deployer agent functional requirements.
