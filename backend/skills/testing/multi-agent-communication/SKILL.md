---
name: multi-agent-communication
description: Verifying agent wiring, input propagation, output passing, and interaction flows.
---

# Multi-Agent Communication Skill

This skill documents rules for verifying communication wiring between agents.

## Rules

1. **Wiring Parity**: Root `agent.py` must import and initialize all sub-agents declared in `plan.json`.
2. **Context Passing**: Verify output from upstream agents is accessible by downstream agents.
3. **Communication Contracts**: Flag input/output schema mismatches as `COMMUNICATION_ERROR`.
