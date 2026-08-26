---
name: git
description: Guidelines for local Git initialization, staging safety checks, single clean commits, and pushing to remote.
---

# Git Workflow Skill

This skill documents rules for local Git operations during publishing.

## Workflow

1. **Initialization**: Run `git init -b main` inside target project directory if not initialized.
2. **Secret Safety Check**: Verify `.env` is listed in `.gitignore` and scan for secrets BEFORE `git add .`.
3. **Staging & Commit**: Create a single clean commit (`feat: publish generated agent system`).
4. **Remote & Push**: Set clean `origin` URL and push `main` branch.
