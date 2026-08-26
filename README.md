# AgentForge

AgentForge is an automated multi-agent system builder platform powered by Google Agent Development Kit (ADK) and Gemini models.

## Completed Features

- **Architect Agent** (`backend/agents/architect_agent.py`): Accepts natural-language user ideas, decomposes requirements into minimal specialized agents, designates a root orchestrator, defines wiring contracts, and outputs a validated `docs/plan.json`.
- **Designer Agent** (`backend/agents/designer_agent.py`): Accepts architectural `plan.json`, generates complete system prompts, typed inputs/outputs, model settings, minimum capability tool specifications, and outputs a validated `docs/design.json`.
- **Coder Agent** (`backend/agents/coder_agent.py`): Accepts `plan.json` and `design.json`, copies `backend/template/` as baseline, generates dynamic agent modules (`agents/<agent_id>/agent.py`, `prompt.py`, `tools.py`), implements assigned tools, configures `settings.yaml`, and wires the root orchestrator.
- **Tester Agent** (`backend/agents/tester_agent.py`): Validates `coder_result.json`, `plan.json`, `design.json`, and generated code across a 15-step testing pipeline, executes generated pytest suites, performs smoke tests, scans for secret exposure, checks Vercel deployment structure compatibility, and outputs `docs/test_result.json`.

## Quick Start

### Installation

```bash
cd backend
pip install -r requirements.txt
```

### Environment Setup

Set your Gemini API key in `.env`:

```env
GEMINI_API_KEY=your_api_key_here
```

### Running Tests

```bash
pytest backend/tests/
```

## Pipeline Artifact Flow

```text
User Idea ──> Architect Agent ──> plan.json ──> Designer Agent ──> design.json ──> Coder Agent ──> generated/<project>/ ──> Tester Agent ──> test_result.json
```

## Documentation

- [Implementation Details](docs/implementation.md)
- [Agent Specifications](docs/agent-specification.md)
- [Architecture](docs/architecture.md)
- [Workflow](docs/workflow.md)
- [Development Phases](docs/phases.md)
