# AgentForge — Implementation Details

## Overview

This document describes the implemented components of AgentForge:
- **Phase 1**: Architect Agent (`docs/plan.json`)
- **Phase 2**: Designer Agent (`docs/design.json`)
- **Phase 3**: Coder Agent (Google ADK Python Code Generation)
- **Phase 4**: Tester Agent (Validation, Diagnostics, Handoff)
- **Phase 5**: GitHub Agent (Repository Creation, Git Staging, Remote Push, Handoff)

---

## 1. Architect Agent Implementation

### Mission
The Architect Agent transforms a user's natural-language idea into a structured, machine-readable multi-agent architecture output file (`docs/plan.json`).

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/architect_agent.py` | ADK Agent wrapper with runner, retry self-correction loop, and plan generator |
| System Prompt | `backend/prompts/architect_prompt.md` | System prompt defining agent instructions, constraints, and JSON requirements |
| Output Schema | `backend/schemas/plan_schema.json` | JSON Schema specifying structure for `plan.json` |
| Tools | `backend/tools/file_tools.py` | Deterministic file and validation tools |
| Tests | `backend/tests/test_architect.py` | Pytest test suite covering schema, wiring, root agent, and file operations |

---

## 2. Designer Agent Implementation

### Mission
The Designer Agent receives the architectural plan (`docs/plan.json`) and transforms it into a complete detailed design specification (`docs/design.json`).

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/designer_agent.py` | ADK Agent wrapper with runner, retry self-correction loop, and design generator |
| System Prompt | `backend/prompts/designer_prompt.md` | System prompt defining prompt generation, tool specifications, and parity rules |
| Output Schema | `backend/schemas/design_schema.json` | JSON Schema specifying detailed design contract for `design.json` |
| Tools | `backend/tools/designer_tools.py` | Deterministic tools (`read_plan_json`, `read_schema`, `validate_design_json`, `write_design_json`) |
| Tests | `backend/tests/test_designer.py` | Pytest test suite covering plan loading, parity preservation, prompts, tools, and wiring |

---

## 3. Coder Agent Implementation

### Mission
The Coder Agent takes `plan.json` and `design.json`, copies `backend/template/`, and performs targeted code generation to implement the designed Google ADK application.

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/coder_agent.py` | ADK Agent wrapper with template copying, dynamic agent directory generation, tool implementation, and root wiring |
| System Prompt | `backend/prompts/coder_prompt.md` | System prompt defining template-first rules, minimal targeted edits, and handoff contracts |
| Output Schema | `backend/schemas/coder_result_schema.json` | JSON Schema for Coder Agent execution output and handoff contract |
| Tools | `backend/tools/coder_tools.py` | Deterministic tools (`copy_template`, `read_file`, `write_file`, `edit_file`, `list_directory`, `terminal_execute`, `validate_plan`, `validate_design`, `inspect_generated_structure`) |
| Tests | `backend/tests/test_coder.py` | Pytest test suite covering plan/design validation, template copying, dynamic agent count, tool implementation, root orchestrator wiring |

---

## 4. Tester Agent Implementation

### Mission
The Tester Agent performs 15-step validation across `coder_result.json`, `plan.json`, `design.json`, and the generated project runtime. It generates/executes pytest unit tests, runs smoke tests, scans for secrets, checks Vercel structure compatibility, and outputs `docs/test_result.json`.

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

### Mission
The GitHub Agent consumes the approved generated project and publishes it to GitHub after verifying `test_result.json` status is `passed`. It creates the remote repository via GitHub REST API, initializes local git repository, performs security secret safety checks, stages files (excluding `.env`), creates a clean single commit, sets remote origin, pushes to `main` branch, and outputs `docs/github_result.json`.

| Component | File Path | Description |
|---|---|---|
| Core Agent | `backend/agents/github_agent.py` | ADK Agent wrapper with 12-step GitHub publishing pipeline and handoff builder |
| System Prompt | `backend/prompts/github_prompt.md` | System prompt defining test result verification, repo slug formatting, secret safety, and git push rules |
| Output Schema | `backend/schemas/github_result_schema.json` | JSON Schema for GitHub Agent output and handoff contract for Deployer Agent |
| Service | `backend/services/github_service.py` | Service wrapper for GitHub REST API (`GET /user`, `GET /repos/{owner}/{name}`, `POST /user/repos`) |
| Tools | `backend/tools/github_tools.py` | Deterministic tools (`read_file`, `list_directory`, `inspect_project`, `check_git_status`, `initialize_git`, `create_github_repository`, `add_files`, `commit_changes`, `set_remote`, `push_repository`, `get_repository_info`, `scan_project_secrets`) |
| Skills | `backend/skills/github/SKILL.md`<br>`backend/skills/git/SKILL.md` | Skill guides for GitHub REST API integration and Git publication workflows |
| Tests | `backend/tests/test_github.py` | Pytest test suite covering 9 scenarios (test verification, repo slug formatting, duplicate checks, repo creation, git init, commit, remote, push, secret safety) |

---

### Testing Status

- All 48 test cases across `test_architect.py` (9), `test_coder.py` (10), `test_designer.py` (10), `test_tester.py` (10), and `test_github.py` (9) pass cleanly.
