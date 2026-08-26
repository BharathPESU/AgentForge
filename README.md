# AgentForge

AgentForge is an automated multi-agent system builder platform powered by Google Agent Development Kit (ADK) and Gemini models.

## Completed Features

- **Architect Agent** (`backend/agents/architect_agent.py`): Accepts natural-language user ideas, decomposes requirements into minimal specialized agents, designates a root orchestrator, defines wiring contracts, and outputs a validated `docs/plan.json`.
- **Designer Agent** (`backend/agents/designer_agent.py`): Accepts architectural `plan.json`, generates complete system prompts, typed inputs/outputs, model settings, minimum capability tool specifications, and outputs a validated `docs/design.json`.
- **Coder Agent** (`backend/agents/coder_agent.py`): Accepts `plan.json` and `design.json`, copies `backend/template/` as baseline, generates dynamic agent modules (`agents/<agent_id>/agent.py`, `prompt.py`, `tools.py`), implements assigned tools, configures `settings.yaml`, and wires the root orchestrator.
- **Tester Agent** (`backend/agents/tester_agent.py`): Validates `coder_result.json`, `plan.json`, `design.json`, and generated code across a 15-step testing pipeline, executes generated pytest suites, performs smoke tests, scans for secret exposure, checks Vercel structure compatibility, and outputs `docs/test_result.json`.
- **GitHub Agent** (`backend/agents/github_agent.py`): Accepts `test_result.json`, verifies validation passed, derives repository slug, performs secret safety checks, creates remote repository via GitHub REST API, initializes Git, commits files, sets remote origin, pushes `main` branch, and outputs `docs/github_result.json`.
- **Deployer Agent** (`backend/agents/deployer_agent.py`): Accepts `github_result.json` and `test_result.json`, verifies publication and testing succeeded, creates/finds Vercel project, injects `GEMINI_API_KEY` into Vercel environment variables directly without disk storage, deploys generated project to Vercel, verifies deployment status and HTTP URL accessibility, and outputs `docs/deployment_result.json`.

## Quick Start

### Installation

```bash
cd backend
pip install -r requirements.txt
```

### Environment Setup

Set your Gemini API key, GitHub token, and Vercel token in `.env`:

```env
GEMINI_API_KEY=your_api_key_here
GITHUB_TOKEN=your_github_pat_here
VERCEL_TOKEN=your_vercel_token_here
```

### Running Tests

```bash
pytest backend/tests/
```

## Pipeline Artifact Flow

```text
User Idea ──> Architect Agent ──> plan.json ──> Designer Agent ──> design.json ──> Coder Agent ──> generated/<project>/ ──> Tester Agent ──> test_result.json ──> GitHub Agent ──> github_result.json ──> Deployer Agent ──> deployment_result.json
```

## Final Deployment Summary

Upon completion of the full multi-agent build pipeline:

```text
Agent system deployed successfully.

GitHub:
<actual GitHub repository URL>

Vercel:
<actual Vercel deployment URL>
```

## Documentation

- [Implementation Details](docs/implementation.md)
- [Agent Specifications](docs/agent-specification.md)
- [Architecture](docs/architecture.md)
- [Workflow](docs/workflow.md)
- [Development Phases](docs/phases.md)
