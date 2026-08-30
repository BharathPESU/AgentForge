# Agent Specifications

## 1. Architect Agent

- **Location**: `backend/agents/architect_agent.py`
- **System Prompt**: `backend/prompts/architect_prompt.md`
- **Output Schema**: `backend/schemas/plan_schema.json`
- **Primary Output**: `docs/plan.json` or `backend/docs/plan.json`
- **Responsibility**: Takes a user's natural-language idea, decomposes it into minimal specialized agents, defines responsibilities, root orchestrator, and communication wiring.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 2. Designer Agent

- **Location**: `backend/agents/designer_agent.py`
- **System Prompt**: `backend/prompts/designer_prompt.md`
- **Output Schema**: `backend/schemas/design_schema.json`
- **Input File**: `docs/plan.json` or `backend/docs/plan.json`
- **Primary Output**: `docs/design.json` or `backend/docs/design.json`
- **Responsibility**: Takes `plan.json` and creates implementation-ready agent specifications, complete system prompts, typed inputs/outputs, minimum capability tool specifications, and handoff contracts while preserving architecture wiring.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 3. Coder Agent

- **Location**: `backend/agents/coder_agent.py`
- **System Prompt**: `backend/prompts/coder_prompt.md`
- **Output Schema**: `backend/schemas/coder_result_schema.json`
- **Input Files**: `plan.json`, `design.json`
- **Primary Output**: Working Google ADK Python application in `generated/<project>/`
- **Responsibility**: Copies `backend/template/` as baseline, performs targeted code modifications to create agent subdirectories (`agents/<agent_id>/agent.py`, `prompt.py`, `tools.py`), implements assigned tools, configures `settings.yaml`, and wires the root orchestrator.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 4. Tester Agent

- **Location**: `backend/agents/tester_agent.py`
- **System Prompt**: `backend/prompts/tester_prompt.md`
- **Output Schema**: `backend/schemas/test_result_schema.json`
- **Input Files**: `coder_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Primary Output**: `docs/test_result.json`
- **Responsibility**: Performs 15-step validation suite covering plan/design schemas, project file structure, agent/tool availability, root agent wiring, pytest suite generation and execution, smoke tests, Vercel structure compatibility, secret scanning, and independent execution check.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 5. GitHub Agent

- **Location**: `backend/agents/github_agent.py`
- **System Prompt**: `backend/prompts/github_prompt.md`
- **Output Schema**: `backend/schemas/github_result_schema.json`
- **Input Files**: `test_result.json`, `coder_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Primary Output**: `docs/github_result.json`
- **Responsibility**: Verifies test result status is `passed`, inspects project files, formats repository name slug, checks for secret exposure, creates remote GitHub repository via GitHub REST API, initializes local Git repository, stages project files (excluding `.env`), creates single commit, sets remote origin URL, pushes `main` branch to remote origin, and outputs `docs/github_result.json` for handoff to `deployer_agent`.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

## 6. Deployer Agent

- **Location**: `backend/agents/deployer_agent.py`
- **System Prompt**: `backend/prompts/deployer_prompt.md`
- **Output Schema**: `backend/schemas/deployment_result_schema.json`
- **Input Files**: `github_result.json`, `test_result.json`, `plan.json`, `design.json`, `generated/<project>/`
- **Primary Output**: `docs/deployment_result.json`
- **Responsibility**: Verifies GitHub publication succeeded (`status == "success"`) and testing passed (`status == "passed"`), inspects project files, creates or finds corresponding Vercel project, injects `GEMINI_API_KEY` into Vercel environment variables directly without disk storage, deploys generated project to Vercel, verifies deployment status and HTTP URL accessibility, and outputs `docs/deployment_result.json` containing GitHub and Vercel URLs.
- **Framework**: Google ADK (`google.adk.Agent`, `google.adk.Runner`).

---

## 7. Shared Context & Memory Layer Services

- **Context Service**: `backend/services/context_service.py`
- **Context Selector**: `backend/services/context_selector.py`
- **Context Prompt Builder**: `backend/services/context_prompt_builder.py`
- **Memory Service**: `backend/services/memory_service.py`
- **Context Tools**: `backend/tools/context_tools.py`
- **Schema**: `backend/schemas/context_schema.json`
- **Responsibility**: Manages execution state, stage history, and artifact references across builder agents while providing token-efficient stage-relevant context injection and fallback capabilities.
