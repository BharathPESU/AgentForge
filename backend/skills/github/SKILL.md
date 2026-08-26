---
name: github
description: Guidelines for GitHub REST API usage, repository creation, PAT authentication, and secret protection.
---

# GitHub Publishing Skill

This skill documents rules and practices for AgentForge GitHub repository integration.

## Core Rules

1. **Test Verification**: Verify `test_result.json` has `status: "passed"` before attempting repository creation.
2. **Repository Naming**: Format `plan.json` project names into clean GitHub repository slugs (e.g. `ai_customer_support` -> `ai-customer-support`).
3. **API Authentication**: Use Bearer token authentication in HTTP headers (`Authorization: Bearer <TOKEN>`). Never embed tokens in stored git configuration or JSON output files.
4. **Visibility Control**: Default to private repositories (`private: true`) unless `GITHUB_REPOSITORY_PRIVATE=false` is explicitly set.
5. **Conflict Handling**: Do NOT overwrite existing repositories automatically (`status: "failed"`, `reason: "repository_already_exists"`).
