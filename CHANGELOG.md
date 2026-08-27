# Changelog

All notable changes to AgentForge will be documented in this file.

## [0.9.0] - 2026-08-28

## [0.9.1] - 2026-08-28

### Added
- Implemented `TaskQueue` FIFO data structure class in `Frontend/artifacts/agentforge-frontend/src/lib/taskQueue.ts`.
- Added prompt enqueuing and confirmation message `"the task has been added to the queue"` in `src/pages/chat.tsx`.
- Added Chat Input Locking (`isLocked`) disabling textarea, submit button, and presets while pipeline execution is active.
- Added automatic page navigation to the Overview section (`/`) immediately after enqueueing a task.

- Replaced Overview section pipeline diagram with a custom 6-node hexagonal series pipeline component in `Frontend/artifacts/agentforge-frontend/src/pages/dashboard.tsx`.
- Added glowing pulse animations for active running stages (`animate-hex-blink`) and particle dash flow for connecting arrows (`animate-[#dash-flow]`).
- Added icons for each stage: Architecture (`Building2`), Design (`FileEdit`), Coding (`Code2`), Testing (`ClipboardCheck`), GitHub (`Github`), Deployment (`CloudUpload`).
- Extended pipeline container full-width to the right side, removing the old "Project signal" card.
- Added pipeline completion banner with live Vercel URL and interactive "Navigate to Deployment" action button.


## [0.8.0] - 2026-08-26

### Added
- Configured `gemini-3.5-flash` model as default across all builder agents and `backend/config/settings.yaml`.
- Created thread-safe round-robin API key manager in `backend/roundRobin.py`.
- Populated `.env` with 30 Gemini API keys (`GEMINI_API_KEY1` through `GEMINI_API_KEY30`).
- Integrated round-robin key rotation into all agent invocation steps.
- Created unit test suite `backend/tests/test_round_robin.py` covering key rotation.

## [0.7.0] - 2026-08-26

### Added
- Implemented **Root Agent** (`backend/agents/root_agent.py`) master orchestrator class `RootAgent` and `run_pipeline` helper.
- Exported all agents and root pipeline orchestrator in `backend/agents/__init__.py`.
- Added feedback retry loop between Tester Agent and Coder Agent (up to 3 retries) on test failure.
- Created unit & integration test suite `backend/tests/test_root.py` covering master pipeline orchestration.

## [0.6.0] - 2026-08-26

### Added
- Implemented **Deployer Agent** (`backend/agents/deployer_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for Deployer Agent in `backend/prompts/deployer_prompt.md`.
- Created output JSON Schema for deployment results in `backend/schemas/deployment_result_schema.json`.
- Implemented Vercel REST API service wrapper in `backend/services/vercel_service.py`.
- Implemented deterministic tools in `backend/tools/deployer_tools.py`.
- Added skill guides in `backend/skills/deployment/`.
- Created unit and integration test suite (`backend/tests/test_deployer.py`).

## [0.5.0] - 2026-08-26

### Added
- Implemented **GitHub Agent** (`backend/agents/github_agent.py`) using Google ADK (`google.adk.Agent`, `google.adk.Runner`).
- Added system prompt for GitHub Agent in `backend/prompts/github_prompt.md`.
- Created output JSON Schema for GitHub Agent execution in `backend/schemas/github_result_schema.json`.
- Implemented GitHub REST API service wrapper in `backend/services/github_service.py`.
- Implemented deterministic tools in `backend/tools/github_tools.py`.
- Added skill guides in `backend/skills/github/` and `backend/skills/git/`.
- Created unit and integration test suite (`backend/tests/test_github.py`).

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
