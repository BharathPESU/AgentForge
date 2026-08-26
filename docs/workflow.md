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

## Stage 3: Code Generation (Next Stage)

- Input: `docs/design.json`
- Output: Google ADK Python code files (`agent.py`, `tools.py`, `prompt.py`).
