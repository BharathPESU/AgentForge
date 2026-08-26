---
name: tool-implementation
description: Guidelines for implementing callable tool functions with docstrings, type annotations, and error handling.
---

# Tool Implementation Skill

This skill documents rules for implementing custom Python tools assigned to agents by `design.json`.

## Implementation Standard

1. **Function Signatures**: Add explicit type annotations for all inputs and returns.
2. **Docstrings**: Include Google-style docstrings with parameter descriptions and return value details.
3. **Return Format**: Return structured dictionary payloads containing status (`"success"` or `"error"`) and result fields.
4. **Export List**: Every `agents/<agent_id>/tools.py` must export a `TOOLS_LIST = [...]` list of callable functions.
5. **No Tools Case**: If `tools` is empty in `design.json`, export `TOOLS_LIST = []`.
