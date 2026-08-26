---
name: security-checking
description: Scanning source files, environment configurations, and documentation for secret leakage.
---

# Security Checking Skill

This skill documents rules for secret scanning and security checks.

## Detection Rules

1. **Pattern Matching**: Search for GitHub tokens (`ghp_`), Google API keys (`AIzaSy`), OpenAI keys (`sk-`), and raw credentials.
2. **Safe Placeholders**: Exclude standard example placeholders like `"YOUR_GEMINI_API_KEY_HERE"`.
3. **Safe Reporting**: Never include actual secret strings in error outputs or test results. Report file location and secret category only.
