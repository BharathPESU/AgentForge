---
name: python-vercel
description: Python and FastAPI serverless deployment structures for Vercel.
---

# Python Vercel Deployment Skill

This skill documents rules for Python / FastAPI Vercel application deployment.

## Structure Requirements

1. **Requirements**: Verify `requirements.txt` includes `fastapi`, `uvicorn`, `google-genai`, `google-adk`.
2. **API Entrypoint**: Verify `fast_api.py` or `api/index.py` exports the FastAPI ASGI app.
3. **No Business Logic Edits**: Do NOT rewrite agent logic or tools during deployment setup.
