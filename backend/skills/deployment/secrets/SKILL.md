---
name: secrets
description: Guidelines for secret safety, Vercel environment variable configuration, and zero credential exposure.
---

# Deployment Secret Management Skill

This skill documents rules for secret handling during deployment.

## Rules

1. **Direct Vercel Injection**: Inject `GEMINI_API_KEY` directly via Vercel REST API (`POST /v10/projects/{id}/env`).
2. **Zero Disk Exposure**: NEVER write real API keys or tokens to `.env`, `README.md`, `github_result.json`, `deployment_result.json`, or git commits.
3. **Redaction**: Never print or log `VERCEL_TOKEN` or `GEMINI_API_KEY` values in tool output or agent returns.
