# Agent Specifications

## 1. Architect Agent

- **Location**: `backend/agents/architect_agent.py`
- **System Prompt**: `backend/prompts/architect_prompt.md`
- **Output Schema**: `backend/schemas/plan_schema.json`
- **Primary Output**: `docs/plan.json` or `backend/docs/plan.json`
- **Responsibility**: Takes a user's natural-language idea, decomposes it into minimal specialized agents, defines responsibilities, root orchestrator, and communication wiring.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- **Tools**:
  - `read_project_document`
  - `read_schema`
  - `validate_plan_json`
  - `write_plan_json`

## 2. Designer Agent

- **Location**: `backend/agents/designer_agent.py`
- **System Prompt**: `backend/prompts/designer_prompt.md`
- **Output Schema**: `backend/schemas/design_schema.json`
- **Input File**: `docs/plan.json` or `backend/docs/plan.json`
- **Primary Output**: `docs/design.json` or `backend/docs/design.json`
- **Responsibility**: Takes `plan.json` and creates implementation-ready agent specifications, complete system prompts, typed inputs/outputs, minimum capability tool specifications, and handoff contracts while preserving architecture wiring.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- **Tools**:
  - `read_plan_json`
  - `read_project_document`
  - `read_schema`
  - `validate_design_json`
  - `write_design_json`

## 3. Future Agents (Pending Implementation)

- **Coder Agent** (`backend/agents/coder_agent.py`): Generate Python code and implementation files from `design.json`.
- **Tester Agent** (`backend/agents/tester_agent.py`): Execute test suites and verify system functionality.
- **GitHub Agent** (`backend/agents/github_agent.py`): Create GitHub repositories and push code.
- **Deployer Agent** (`backend/agents/deployer_agent.py`): Deploy services to hosting infrastructure.
