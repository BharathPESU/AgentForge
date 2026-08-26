# AgentForge — Implementation Details

## Overview

This document describes the implemented components of AgentForge:
- **Master Orchestrator**: Root Agent (`backend/agents/root_agent.py`)
- **Phase 1**: Architect Agent (`docs/plan.json`)
- **Phase 2**: Designer Agent (`docs/design.json`)
- **Phase 3**: Coder Agent (Google ADK Python Code Generation)
- **Phase 4**: Tester Agent (Validation, Diagnostics, Handoff)
- **Phase 5**: GitHub Agent (Repository Creation, Git Staging, Remote Push, Handoff)
- **Phase 6**: Deployer Agent (Vercel Project Creation, Gemini API Key Env Injection, Deployment, Verification, Handoff)

---

## Master Root Orchestrator Implementation

### Mission
The Root Agent (`backend/agents/root_agent.py`) coordinates the entire 6-agent builder pipeline sequentially:
1. **Architect Agent** (`ArchitectAgent`): Natural language idea -> `docs/plan.json`.
2. **Designer Agent** (`DesignerAgent`): `plan.json` -> `docs/design.json`.
3. **Coder Agent** (`CoderAgent`): `plan.json` + `design.json` -> `generated/<project>/` + `docs/coder_result.json`.
4. **Tester Agent** (`TesterAgent`): Project validation & pytest suite execution -> `docs/test_result.json`.
   - *Feedback Loop*: On testing failure, automatically triggers Coder Agent retry loop (up to 3 retries) and re-evaluates.
5. **GitHub Agent** (`GitHubAgent`): Verified project -> GitHub REST API repo creation, git init/add/commit/push -> `docs/github_result.json`.
6. **Deployer Agent** (`DeployerAgent`): Verified project + GitHub URL -> Vercel project creation, direct `GEMINI_API_KEY` env var injection, Vercel deployment, URL verification -> `docs/deployment_result.json`.

---

## 1. Architect Agent Implementation

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/architect_agent.py` | ADK Agent wrapper with runner, retry self-correction loop, and plan generator |
| System Prompt | `backend/prompts/architect_prompt.md` | System prompt defining agent instructions, constraints, and JSON requirements |
| Output Schema | `backend/schemas/plan_schema.json` | JSON Schema specifying structure for `plan.json` |
| Tools | `backend/tools/file_tools.py` | Deterministic file and validation tools |
| Tests | `backend/tests/test_architect.py` | Pytest test suite covering schema, wiring, root agent, and file operations |

---

## 2. Designer Agent Implementation

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/designer_agent.py` | ADK Agent wrapper with runner, retry self-correction loop, and design generator |
| System Prompt | `backend/prompts/designer_prompt.md` | System prompt defining prompt generation, tool specifications, and parity rules |
| Output Schema | `backend/schemas/design_schema.json` | JSON Schema specifying detailed design contract for `design.json` |
| Tools | `backend/tools/designer_tools.py` | Deterministic tools (`read_plan_json`, `read_schema`, `validate_design_json`, `write_design_json`) |
| Tests | `backend/tests/test_designer.py` | Pytest test suite covering plan loading, parity preservation, prompts, tools, and wiring |

---

## 3. Coder Agent Implementation

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/coder_agent.py` | ADK Agent wrapper with template copying, dynamic agent directory generation, tool implementation, and root wiring |
| System Prompt | `backend/prompts/coder_prompt.md` | System prompt defining template-first rules, minimal targeted edits, and handoff contracts |
| Output Schema | `backend/schemas/coder_result_schema.json` | JSON Schema for Coder Agent execution output and handoff contract |
| Tools | `backend/tools/coder_tools.py` | Deterministic tools (`copy_template`, `read_file`, `write_file`, `edit_file`, `list_directory`, `terminal_execute`, `validate_plan`, `validate_design`, `inspect_generated_structure`) |
| Tests | `backend/tests/test_coder.py` | Pytest test suite covering plan/design validation, template copying, dynamic agent count, tool implementation, root orchestrator wiring |

---

## 4. Tester Agent Implementation

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/tester_agent.py` | ADK Agent wrapper with 15-step validation pipeline and handoff builder |
| System Prompt | `backend/prompts/tester_prompt.md` | System prompt defining validation steps, failure categories, and status rules |
| Output Schema | `backend/schemas/test_result_schema.json` | JSON Schema for Tester Agent output and handoff contract for GitHub Agent |
| Tools | `backend/tools/tester_tools.py` | 15 deterministic tools for project inspection, pytest suite generation/execution, smoke testing, secret scanning, and independent run verification |
| Skills | `backend/skills/testing/` | Skill suite (7 sub-skills: `agent-testing`, `multi-agent-communication`, `integration-testing`, `smoke-testing`, `security-checking`, `vercel-validation`, `failure-diagnosis`) |
| Tests | `backend/tests/test_tester.py` | Pytest test suite covering 10 validation scenarios |

---

## 5. GitHub Agent Implementation

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/github_agent.py` | ADK Agent wrapper with 12-step GitHub publishing pipeline and handoff builder |
| System Prompt | `backend/prompts/github_prompt.md` | System prompt defining test result verification, repo slug formatting, secret safety, and git push rules |
| Output Schema | `backend/schemas/github_result_schema.json` | JSON Schema for GitHub Agent output and handoff contract for Deployer Agent |
| Service | `backend/services/github_service.py` | Service wrapper for GitHub REST API (`GET /user`, `GET /repos/{owner}/{name}`, `POST /user/repos`) |
| Tools | `backend/tools/github_tools.py` | Deterministic tools (`read_file`, `list_directory`, `inspect_project`, `check_git_status`, `initialize_git`, `create_github_repository`, `add_files`, `commit_changes`, `set_remote`, `push_repository`, `get_repository_info`, `scan_project_secrets`) |
| Skills | `backend/skills/github/SKILL.md`<br>`backend/skills/git/SKILL.md` | Skill guides for GitHub REST API integration and Git publication workflows |
| Tests | `backend/tests/test_github.py` | Pytest test suite covering 9 scenarios |

---

## 6. Deployer Agent Implementation

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/deployer_agent.py` | ADK Agent wrapper with 11-step Vercel deployment pipeline |
| System Prompt | `backend/prompts/deployer_prompt.md` | System prompt defining GitHub & test verification, secret management, Vercel API deployment, and zero secret leakage rules |
| Output Schema | `backend/schemas/deployment_result_schema.json` | JSON Schema for Deployer Agent output and final completion contract |
| Service | `backend/services/vercel_service.py` | Service wrapper for Vercel REST API |
| Tools | `backend/tools/deployer_tools.py` | Deterministic tools |
| Skills | `backend/skills/deployment/` | Skill suite (4 sub-skills) |
| Tests | `backend/tests/test_deployer.py` | Pytest test suite covering 12 scenarios |

---

### Testing Status

- All **66 test cases** across `test_architect.py` (9), `test_coder.py` (10), `test_designer.py` (10), `test_tester.py` (10), `test_github.py` (9), `test_deployer.py` (12), and `test_root.py` (6) pass cleanly.
