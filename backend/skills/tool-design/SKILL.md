---
name: tool-design
description: Principles for tool specification design, input/output typing, safety permissions, and docstring formatting.
---

# Tool Design Skill

This skill documents tool specification guidelines for AgentForge detailed designs.

## Principles of Tool Design

1. **Deterministic Function Specs**: Tools are specified as plain Python function targets to be implemented by the Coder Agent.
2. **Minimum Capability Principle**: Only assign tools needed for the agent's core function.
3. **Docstring Quality**: Tool descriptions must clearly state purpose, input parameters, expected return values, and usage conditions so LLMs can invoke them accurately.
4. **Tool Categories**:
   - Internal processing
   - External APIs
   - Search & Retrieval
   - File & Document
   - Computation & Math
5. **Safety & Restrictions**: Define explicit restrictions for tools with side-effects (e.g. read-only permissions vs write permissions).
