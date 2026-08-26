# Changelog

All notable changes to AgentForge will be documented in this file.

## [0.5.0] - 2026-08-26

### Added
- Implemented **GitHub Agent** (`backend/agents/github_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for GitHub Agent in `backend/prompts/github_prompt.md`.
- Created output JSON Schema for GitHub Agent execution in `backend/schemas/github_result_schema.json`.
- Implemented GitHub REST API service wrapper in `backend/services/github_service.py`.
- Implemented deterministic tools in `backend/tools/github_tools.py` (`read_file`, `list_directory`, `inspect_project`, `check_git_status`, `initialize_git`, `create_github_repository`, `add_files`, `commit_changes`, `set_remote`, `push_repository`, `get_repository_info`, `scan_project_secrets`).
- Added skill guides in `backend/skills/github/` and `backend/skills/git/`.
- Created unit and integration test suite (`backend/tests/test_github.py`) covering 9 test scenarios.
- Updated system documentation and `docs/implementation.md`.

## [0.4.0] - 2026-08-26

### Added
- Implemented **Tester Agent** (`backend/agents/tester_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Tester Agent in `backend/prompts/tester_prompt.md`.
- Created output JSON Schema for Tester Agent execution in `backend/schemas/test_result_schema.json`.
- Implemented 15 deterministic tester tools in `backend/tools/tester_tools.py`.
- Added 7 skill guides in `backend/skills/testing/`.
- Created unit and integration test suite (`backend/tests/test_tester.py`).

## [0.3.0] - 2026-08-26

### Added
- Implemented **Coder Agent** (`backend/agents/coder_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Coder Agent in `backend/prompts/coder_prompt.md`.
- Created output JSON Schema for Coder Agent execution in `backend/schemas/coder_result_schema.json`.
- Implemented deterministic coder tools in `backend/tools/coder_tools.py`.
- Added skill guides (`template-based-code-generation`, `python-code-generation`, `tool-implementation`).
- Created unit and integration test suite (`backend/tests/test_coder.py`).

## [0.2.0] - 2026-08-26

### Added
- Implemented **Designer Agent** (`backend/agents/designer_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Designer Agent in `backend/prompts/designer_prompt.md`.
- Created output JSON Schema for detailed design in `backend/schemas/design_schema.json`.
- Implemented deterministic designer tools in `backend/tools/designer_tools.py`.
- Added skill guides (`agent-design`, `prompt-engineering`, `tool-design`).
- Created unit and integration test suite (`backend/tests/test_designer.py`).

## [0.1.0] - 2026-08-26

### Added
- Implemented **Architect Agent** (`backend/agents/architect_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Architect Agent in `backend/prompts/architect_prompt.md`.
- Created output JSON Schema for architecture plan in `backend/schemas/plan_schema.json`.
- Implemented deterministic file and validation tools in `backend/tools/file_tools.py`.
- Created unit and integration test suite (`backend/tests/test_architect.py`).
