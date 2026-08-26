# Changelog

All notable changes to AgentForge will be documented in this file.

## [0.4.0] - 2026-08-26

### Added
- Implemented **Tester Agent** (`backend/agents/tester_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Tester Agent in `backend/prompts/tester_prompt.md`.
- Created output JSON Schema for Tester Agent execution in `backend/schemas/test_result_schema.json`.
- Implemented 15 deterministic tester tools in `backend/tools/tester_tools.py` (`read_file`, `list_directory`, `search_files`, `execute_command`, `validate_plan`, `validate_design`, `inspect_project`, `create_test_file`, `run_test`, `run_test_suite`, `check_import`, `check_agent_wiring`, `run_agent_interaction_test`, `run_smoke_test`, `check_vercel_structure`, `scan_for_secrets`, `check_independent_execution`).
- Added 7 skill guides in `backend/skills/testing/` (`agent-testing`, `multi-agent-communication`, `integration-testing`, `smoke-testing`, `security-checking`, `vercel-validation`, `failure-diagnosis`).
- Created unit and integration test suite (`backend/tests/test_tester.py`) covering all 10 required test scenarios.
- Updated system documentation and `docs/implementation.md`.

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

## [0.1.0] - 2026-08-26

### Added
- Implemented **Architect Agent** (`backend/agents/architect_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Architect Agent in `backend/prompts/architect_prompt.md`.
- Created output JSON Schema for architecture plan in `backend/schemas/plan_schema.json`.
- Implemented deterministic file and validation tools in `backend/tools/file_tools.py`.
- Created unit and integration test suite (`backend/tests/test_architect.py`).
