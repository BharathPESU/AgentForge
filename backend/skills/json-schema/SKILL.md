---
name: json-schema
description: JSON Schema validation standards, required field enforcement, and error diagnostic techniques.
---

# JSON Schema Skill

This skill documents JSON Schema standards for AgentForge plan artifacts.

## 1. Schema Validation Principles

- **Draft 7 Compatibility**: Use standard JSON Schema keywords (`$schema`, `type`, `properties`, `required`, `additionalProperties`).
- **Strict Validation**: Set `additionalProperties: false` on objects to prevent unexpected payload keys.
- **Pattern Matching**: Use regex patterns for machine IDs (e.g. `^agent[0-9]+$`).
- **Enumerations**: Restrict string properties with fixed values to clear enums (e.g. `["sequential", "parallel"]`).

## 2. Schema Validation Flow

- Validate output using Python `jsonschema.Draft7Validator`.
- Collect errors with exact property paths to feed back into model self-correction loops.
