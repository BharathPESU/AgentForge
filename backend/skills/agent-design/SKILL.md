---
name: agent-design
description: Design principles for transforming high-level multi-agent plans into implementation-ready agent specifications.
---

# Agent Design Skill

This skill provides best practices for translating architectural plans into detailed agent designs.

## Key Design Principles

1. **Parity Preservation**: Keep agent IDs, count, root orchestrator status, and wiring identical to `plan.json`.
2. **Minimal Tool Capability**: Assign tools strictly based on minimum necessity. Do not grant generic toolsets (e.g. filesystem or shell) to agents that only perform reasoning or routing.
3. **Structured Contracts**: Define explicit typed schemas for every input and output attribute (`name`, `type`, `description`, `required`).
4. **Handoff Topology**: Map upstream and downstream dependencies explicitly for every agent based on wiring connections.
5. **System Instructions**: Craft self-contained, unambiguous system prompts for each agent covering role, process, tool policy, constraints, and error recovery.
