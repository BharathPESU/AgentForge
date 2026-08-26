---
name: python-code-generation
description: Code formatting standards, type hints, error handling, and Google ADK API usage for Python agent generation.
---

# Python Code Generation Skill

This skill documents Python coding standards for generated Google ADK agents.

## Principles

1. **Python 3.11+ Standards**: Use type hints (`Dict[str, Any]`, `List[str]`, `Optional[str]`), clear function names, and docstrings.
2. **Google ADK Integration**: Use current Google GenAI / ADK patterns (`google.genai`, `types.GenerateContentConfig`).
3. **Robust Agent Classes**:
   - Each agent exposes a `run(prompt: str, context: Optional[Dict[str, Any]])` method.
   - Each agent module provides a `get_agent(**kwargs)` factory function.
4. **Environment Variables**: Load secrets from `os.environ` (`GOOGLE_API_KEY`). Never hard-code API keys.
