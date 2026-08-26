---
name: vercel
description: Vercel deployment, project management, and REST API integration rules.
---

# Vercel Deployment Skill

This skill documents rules for interacting with Vercel APIs.

## Flow

1. **Authentication**: Use `VERCEL_TOKEN` Bearer auth for API calls (`POST /v9/projects`, `POST /v10/projects/{id}/env`, `POST /v13/deployments`).
2. **Project Reuse**: Reuse existing Vercel project if already present.
3. **Deployment Target**: Deploy to `production` target.
