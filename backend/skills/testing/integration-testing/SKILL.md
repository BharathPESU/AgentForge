---
name: integration-testing
description: End-to-end testing, pytest suite execution, and workflow validation.
---

# Integration Testing Skill

This skill documents guidelines for automated test suite creation and execution.

## Standards

1. **Pytest Execution**: Run pytest suites using `python3 -m pytest tests/ -q`.
2. **Actual Counts**: Parse actual `tests_run`, `tests_passed`, and `tests_failed` from command output.
3. **No Inferred Success**: Never declare tests passed without empirical runtime execution logs.
