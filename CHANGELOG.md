# Changelog

All notable changes to AgentForge will be documented in this file.

## [0.3.0] - 2026-08-26

### Added
- Implemented **Coder Agent** (`backend/agents/coder_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Coder Agent in `backend/prompts/coder_prompt.md`.
- Created output JSON Schema for Coder Agent execution in `backend/schemas/coder_result_schema.json`.
- Implemented deterministic coder tools in `backend/tools/coder_tools.py` (`copy_template`, `read_file`, `write_file`, `edit_file`, `list_directory`, `terminal_execute`, `validate_plan`, `validate_design`, `inspect_generated_structure`).
- Added skill guides (`template-based-code-generation`, `python-code-generation`, `tool-implementation`).
- Created unit and integration test suite (`backend/tests/test_coder.py`) covering all 10 required test scenarios.
- Updated system documentation and `docs/implementation.md`.

## [0.2.0] - 2026-08-26

### Added
- Implemented **Designer Agent** (`backend/agents/designer_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Designer Agent in `backend/prompts/designer_prompt.md`.
- Created output JSON Schema for detailed design in `backend/schemas/design_schema.json`.
- Implemented deterministic designer tools in `backend/tools/designer_tools.py` (`read_plan_json`, `read_schema`, `validate_design_json`, `write_design_json`).
- Added skill guides (`agent-design`, `prompt-engineering`, `tool-design`).
- Created unit and integration test suite (`backend/tests/test_designer.py`).
- Added support for reading/writing artifacts under `backend/docs/plan.json` and `backend/docs/design.json`.

## [0.1.0] - 2026-08-26

### Added
- Implemented **Architect Agent** (`backend/agents/architect_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Architect Agent in `backend/prompts/architect_prompt.md`.
- Created output JSON Schema for architecture plan in `backend/schemas/plan_schema.json`.
- Implemented deterministic file and validation tools in `backend/tools/file_tools.py` (`read_project_document`, `read_schema`, `validate_plan_json`, `write_plan_json`).
- Added skill guides (`agent-architecture`, `google-adk`, `json-schema`, `requirements-analysis`).
- Created unit and integration test suite (`backend/tests/test_architect.py`).
