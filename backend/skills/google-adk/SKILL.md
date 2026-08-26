---
name: google-adk
description: Core concepts and patterns for Google ADK (Agent Development Kit), including Agents, Runners, tools, sessions, and state.
---

# Google ADK Architecture Skill

This skill documents current Google Agent Development Kit (ADK) usage patterns for multi-agent applications.

## 1. Core Abstractions

- **`google.adk.Agent`**: The foundational agent component in ADK.
  - Attributes: `name`, `instruction`, `model`, `tools`, `sub_agents`, `input_schema`, `output_schema`.
  - Configured with Gemini models (e.g. `gemini-2.5-flash`, `gemini-1.5-pro`).
- **`google.adk.Runner`**: Executes an agent within a session context.
  - Requires `agent`, `app_name`, `session_service` (e.g. `InMemorySessionService`).
  - Executes synchronously via `runner.run(...)` or asynchronously via `runner.run_async(...)`.
- **Session Services**:
  - `InMemorySessionService`: Manages session state in memory for testing and fast local execution.

## 2. Tool Integration

- Deterministic Python functions decorated or registered as tools with `Agent(tools=[...])`.
- Tools must have clean docstrings and typed arguments to enable accurate LLM tool-calling.

## 3. Execution & Context Management

- Pass user prompts using `types.Content` or standard string inputs.
- Keep session state isolated per execution session (`session_id`).
