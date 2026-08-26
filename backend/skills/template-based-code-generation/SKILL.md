---
name: template-based-code-generation
description: Guidance on reusing project templates, minimal targeted edits, and preserving working infrastructure.
---

# Template-Based Code Generation Skill

This skill documents rules for generating multi-agent projects using AgentForge's tested template baseline.

## Core Rules

1. **Inspect Before Modifying**: Inspect existing template files (`agent.py`, `settings.yaml`, `fast_api.py`, etc.) before making edits.
2. **Template Copying**: Copy `backend/template/` to `generated/<project>/` as the initial baseline when creating new projects.
3. **Minimal Targeted Modifications**:
   - Only edit code required by `design.json` and `plan.json`.
   - Preserve existing ADK boilerplate, API routes, helper functions, and frontend integrations.
   - Do not replace entire working template files if small targeted modifications achieve the goal.
4. **Dynamic Agent Count**: Read agent IDs strictly from `plan.json` / `design.json` rather than hardcoding a fixed number of agents.
