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

## 3. Coder Agent

- **Location**: `backend/agents/coder_agent.py`
- **System Prompt**: `backend/prompts/coder_prompt.md`
- **Output Schema**: `backend/schemas/coder_result_schema.json`
- **Input Files**: `plan.json`, `design.json`
- **Primary Output**: Working Google ADK Python application in `generated/<project>/`
- **Responsibility**: Copies `backend/template/` as baseline, performs targeted code modifications to create agent subdirectories (`agents/<agent_id>/agent.py`, `prompt.py`, `tools.py`), implements assigned tools, configures `settings.yaml`, and wires the root orchestrator.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- **Tools**:
  - `copy_template`
  - `read_file`
  - `write_file`
  - `edit_file`
  - `list_directory`
  - `terminal_execute`
  - `validate_plan`
  - `validate_design`
  - `inspect_generated_structure`

## 4. Future Agents (Pending Implementation)

- **Tester Agent** (`backend/agents/tester_agent.py`): Execute test suites and verify system functionality.
- **GitHub Agent** (`backend/agents/github_agent.py`): Create GitHub repositories and push code.
- **Deployer Agent** (`backend/agents/deployer_agent.py`): Deploy services to hosting infrastructure.
