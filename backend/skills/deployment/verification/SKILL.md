---
name: verification
description: Verification of Vercel deployment status, readiness, and public URL accessibility.
---

# Deployment Verification Skill

This skill documents rules for verifying deployment URLs.

## Flow

1. **Status Query**: Query `GET /v13/deployments/{id}` and check `readyState == "READY"`.
2. **URL Formatting**: Ensure URL has `https://` scheme.
3. **HTTP Check**: Test HTTP GET request to verify URL accessibility.
