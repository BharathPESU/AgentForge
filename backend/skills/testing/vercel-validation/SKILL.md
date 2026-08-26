---
name: vercel-validation
description: Validating project structure and dependencies for Vercel deployment compatibility.
---

# Vercel Validation Skill

This skill documents rules for checking Vercel deployment structure.

## Verification Checklist

1. **Requirements**: Verify `requirements.txt` exists and lists runtime dependencies.
2. **API Entrypoint**: Verify `fast_api.py` or `api/index.py` exists and exports the ASGI app.
3. **No Deployment**: Do NOT attempt deployment. Verification is structural only.
