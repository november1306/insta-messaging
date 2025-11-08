---
inclusion: always
---

# Commit Workflow - MANDATORY

## Pre-Commit Review Process

**ALWAYS follow this workflow before committing:**

1. **Stage your changes**
   ```bash
   git add <files>
   ```

2. **Run Claude review**
   ```bash
   claude-review-local.cmd --staged
   ```

3. **Fix critical issues**
   - Address all critical bugs and security issues
   - Fix data integrity problems
   - Resolve deployment-breaking issues

4. **Re-review after fixes**
   ```bash
   git add <fixed-files>
   claude-review-local.cmd --staged
   ```

5. **Iterate until clean**
   - Repeat steps 3-4 until only minor or not-worth-fixing issues remain
   - Minor issues: style preferences, subjective opinions, over-optimization suggestions

6. **Commit when ready**
   ```bash
   git commit -m "your message"
   ```

## Why This Matters

- **Claude 3.5 Sonnet v2 (4.5)** catches issues that I (Kiro/Claude 3.5 Sonnet v1) might miss
- Prevents critical bugs from entering the codebase
- Ensures production readiness before pushing
- Faster feedback loop than waiting for GitHub Actions

## What to Fix vs Skip

**MUST FIX:**
- Critical bugs that cause runtime failures
- Security vulnerabilities
- Data integrity issues (missing FKs, inconsistent defaults)
- Configuration issues that break first launch
- Missing error handling for production

**CAN SKIP (if minor):**
- Style preferences
- Over-optimization suggestions for MVP
- Subjective code organization opinions
- Edge cases not relevant to current use case

## Example Workflow

```bash
# 1. Make changes
# (edit files)

# 2. Stage
git add app/db/models.py

# 3. Review
claude-review-local.cmd --staged

# 4. Fix critical issues found
# (edit files)

# 5. Re-stage and review
git add app/db/models.py
claude-review-local.cmd --staged

# 6. Commit when clean
git commit -m "feat: add database models"
```

## Integration with Kiro Workflow

As Kiro agent:
1. Implement the task
2. Test locally (getDiagnostics, run server)
3. **Stage and run claude-review-local.cmd** ← NEW STEP
4. Fix issues and re-review
5. Commit only when review is clean
6. Push to remote

This ensures every commit is reviewed by the latest Claude model before entering the codebase.
