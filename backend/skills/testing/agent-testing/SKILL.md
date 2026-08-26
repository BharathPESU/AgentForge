---
name: agent-testing
description: Guidance on verifying agent initialization, tool registration, inputs/outputs, and behavior.
---

# Agent Testing Skill

This skill documents rules for verifying individual agent modules in generated applications.

## Verification Checklist

1. **Module Existence**: Verify `agents/<agent_id>/agent.py`, `prompt.py`, and `tools.py` exist.
2. **Factory Function**: Ensure `get_agent(**kwargs)` factory is exported.
3. **Agent Class**: Verify the agent class implements `run(prompt: str, context: Optional[Dict]) -> Dict`.
4. **Tool Registration**: Ensure all tools listed in `tools.py` are registered in `TOOLS_LIST`.
