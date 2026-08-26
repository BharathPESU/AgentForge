---
name: failure-diagnosis
description: Categorizing test failures, detecting responsible upstream agents, and providing actionable correction advice.
---

# Failure Diagnosis Skill

This skill documents guidelines for diagnosing test failures and assigning upstream responsibility.

## Categorization & Upstream Routing

| Category | Responsible Agent | Description |
|---|---|---|
| `ARCHITECTURE_ERROR` | `architect_agent` | Invalid `plan.json` or root agent violation |
| `DESIGN_ERROR` | `designer_agent` | Invalid `design.json` or prompt/tool spec mismatch |
| `IMPLEMENTATION_ERROR` | `coder_agent` | Missing files, broken imports, missing tools |
| `COMMUNICATION_ERROR` | `coder_agent` | Broken root orchestrator wiring or agent routing |
| `SECURITY_ERROR` | `coder_agent` | Hard-coded secrets in source files |
| `DEPLOYMENT_STRUCTURE_ERROR` | `coder_agent` | Missing `requirements.txt` or ASGI entrypoint |
| `RUNTIME_ERROR` | `coder_agent` | Uncaught exceptions during initialization or smoke test |
