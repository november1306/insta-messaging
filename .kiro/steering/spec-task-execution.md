# Spec Task Execution Workflow

## MANDATORY: Always Follow Commit Workflow

When executing spec tasks, you MUST follow this workflow for EVERY task:

1. **Mark task as in_progress** using taskStatus tool
2. **Implement the task** according to requirements
3. **Test the implementation** (run server, test endpoints, check diagnostics)
4. **Stage changes**: `git add <files>`
5. **Run review**: `claude-review-local.cmd --staged`
6. **Fix critical issues** identified by review
7. **Re-stage and re-review** until clean
8. **Commit**: `git commit -m "descriptive message"`
9. **Mark task as completed** using taskStatus tool

## Critical Rules

- NEVER skip the review step
- NEVER commit without running claude-review-local.cmd first
- ALWAYS fix critical issues before committing
- ALWAYS include test files in staged changes
- ONLY mark task complete after successful commit

## What to Fix vs Skip in Reviews

**MUST FIX:**
- Critical bugs that cause runtime failures
- Security vulnerabilities (unless explicitly deferred in task)
- Data integrity issues
- Missing error handling for production
- Database transaction issues (missing commit, etc.)

**CAN SKIP (if task says "minimal" or "MVP"):**
- Requests for "real" encryption when task says "simple encryption"
- Requests for comprehensive validation when task says "skip validation"
- Style preferences and subjective opinions
- Over-optimization suggestions for MVP
- Edge cases not relevant to current task

## Task Completion Checklist

Before marking a task complete:
- [ ] Code implements all task requirements
- [ ] Tests pass
- [ ] No critical diagnostics errors
- [ ] Changes staged
- [ ] Review run and critical issues fixed
- [ ] Changes committed
- [ ] Task marked as completed

## Remember

The spec tasks are designed to be incremental. Priority 1 tasks are intentionally minimal - don't add Priority 2 features unless the task explicitly requires them.
