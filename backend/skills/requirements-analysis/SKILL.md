---
name: requirements-analysis
description: Methodology for transforming informal natural-language ideas into structured system requirements and agent roles.
---

# Requirements Analysis Skill

This skill provides a systematic pipeline for transforming user ideas into concrete agent architectures.

## Pipeline Breakdown

```text
User Idea
   ↓
Core Goals & Scope
   ↓
Key Capabilities Needed
   ↓
Role & Responsibility Division
   ↓
Agent Mapping & ID Assignment
   ↓
Data Flow & Communication Wiring
```

## Key Rules

1. **Explicit Assumptions**: If the user idea leaves technical details ambiguous (e.g. data storage choice), record reasonable assumptions explicitly in `assumptions`.
2. **Goal Extraction**: State the primary goal concise and actionable.
3. **No Bloat**: Keep responsibility boundaries clean and avoid adding extraneous steps not implied by the idea.
