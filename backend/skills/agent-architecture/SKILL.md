---
name: agent-architecture
description: Guidelines and patterns for multi-agent system decomposition, root orchestrator selection, wiring, and minimality.
---

# Agent Architecture Skill

This skill provides best practices for decomposing complex software requirements into multi-agent systems.

## 1. Principles of Multi-Agent System Design

- **Minimality**: Prefer simple architectures with the smallest number of agents necessary. Avoid creating helper/utility agents if a single agent can logically manage the task.
- **Single vs Multi-Agent Decision**:
  - Use a single agent when tasks share context, require the same tools, or follow simple linear steps.
  - Use multi-agent systems when tasks require distinct domain expertise, specialized tools, different execution environments, or benefit from parallel sub-tasks.
- **Root Orchestrator Pattern**:
  - Every multi-agent system must have exactly one root agent (`is_root: true`).
  - The root agent receives the primary user input, delegates tasks to downstream agents, and synthesizes the final response.

## 2. Agent Identifiers and Contracts

- **IDs**: Stable, machine-readable IDs (e.g. `agent1`, `agent2`, `agent3`).
- **Names**: Descriptive human-readable strings (e.g. `intent_router`, `docs_retriever`, `response_generator`).
- **Inputs & Outputs**: Explicitly list arrays of key data attributes exchanged (e.g. `["user_query"]` -> `["retrieved_context"]`).

## 3. Communication & Wiring Patterns

- **Sequential Execution**: Execution flows from Agent A to Agent B in order (`"execution": "sequential"`).
- **Parallel Execution**: Multiple agents operate independently on split inputs (`"execution": "parallel"`).
- **Conditional Routing**: Invocation depends on explicitly documented conditions (`"condition": "query_requires_docs"`).
- **Referential Integrity**: Every `from` and `to` field in wiring must reference a valid agent `id` in the system.
