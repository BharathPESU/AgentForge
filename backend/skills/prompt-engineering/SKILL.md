---
name: prompt-engineering
description: Guidelines for engineering complete, unambiguous, and robust system instruction prompts for AI agents.
---

# Prompt Engineering Skill

This skill provides rules for generating complete system instruction prompts for generated agents.

## Structure of an Implementation-Ready System Prompt

Every system prompt created by the Designer Agent must contain:

1. **Role & Identity**: State who the agent is (e.g. *"You are the Knowledge Retrieval Agent."*).
2. **Goal & Mission**: State the primary objective.
3. **Input Specifications**: List expected input fields and format.
4. **Task Execution Steps**: Provide step-by-step instructions on how to process incoming input.
5. **Tool Usage Policy**: State when and how tools should be called, and when tools must NOT be called.
6. **Constraints**: State strict behavioral boundaries (e.g. *"Do not invent facts not found in retrieved docs."*).
7. **Error Handling**: Explain how to behave when a tool fails or input is missing.
8. **Output Specifications**: Describe the required output format and schema.

Avoid vague prompts like *"You are a helpful assistant"*. Always produce precise, context-specific, constraint-enforced prompts.
