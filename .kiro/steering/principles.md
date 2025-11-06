# Development Principles

## Core Philosophy

This is an **MVP in active development**. Focus on getting it working, not perfection.

### YAGNI (You Aren't Gonna Need It)
- Start minimal, add complexity only when needed
- Don't build features for hypothetical future requirements
- Comments in code often reference YAGNI to explain simpler approaches

### KISS (Keep It Simple, Stupid)
- Prefer simple, readable solutions over clever ones
- Avoid over-engineering and premature optimization
- If it works and is maintainable, it's good enough

### DRY (Don't Repeat Yourself)
- Extract repeated logic into reusable functions
- Use parametrized error messages instead of duplicating text
- Consolidate validation logic into single methods

## Code Quality Standards

### What Matters
- **Critical bugs and security issues** - Must be fixed
- **First launch behavior** - App must work on initial deployment
- **Clear error messages** - Missing config should be obvious
- **Production readiness** - Deployment concerns are priority

### What Doesn't Matter (Yet)
- **Test coverage** - NO tests required during MVP development
- **Edge case handling** - Handle common cases, skip rare scenarios
- **Comprehensive validation** - Basic validation is sufficient
- **Performance optimization** - Optimize only when needed

## Configuration Management

### No Defaults or Placeholders
- Never use fake default values (e.g., `"dev_verify_token_12345"`)
- Empty string if not configured, not placeholder text
- Clear error messages showing what's missing and where to get it

### Environment Variables
- All secrets in environment variables, never in code
- `.env` file for local development (gitignored)
- Platform environment variables for production
- TODO: GitHub Secrets integration for CI/CD

## Error Handling

### Clear and Actionable
- Error messages must explain what's wrong
- Include where to get missing values (URLs, dashboard locations)
- Log warnings on startup for missing configuration
- Fail fast in production, warn in development

### Example
```python
# ❌ Bad: Silent failure or cryptic error
if not token:
    return False

# ✅ Good: Clear, actionable error
if not token:
    logger.error(
        "FACEBOOK_APP_SECRET not configured. "
        "Get it from: https://developers.facebook.com/apps/YOUR_APP_ID/settings/basic/"
    )
    return False
```

## Security

### Always Validate
- Webhook signature validation is mandatory (no bypass)
- Use constant-time comparison for signatures
- Never log secrets or personal data
- Encrypt sensitive data at rest

### Deployment Ready
- App must work on first launch with proper config
- Clear errors if secrets are missing
- No insecure defaults that could reach production

## Code Review Focus

When reviewing code, prioritize:
1. **Security issues** - Signature validation, secret handling
2. **Deployment readiness** - First launch behavior, error messages
3. **Code clarity** - YAGNI, KISS, DRY principles
4. **Critical bugs** - Things that break core functionality

Skip:
- Test coverage (not required yet)
- Edge case handling (unless critical)
- Performance optimization (unless blocking)
- Comprehensive documentation (basic is fine)

## Comments and Documentation

### When to Comment
- Explain WHY, not WHAT (code shows what)
- Reference YAGNI when choosing simpler approach
- Add TODOs for future improvements (e.g., GitHub Secrets)
- Document security considerations

### When NOT to Comment
- Don't state the obvious
- Don't repeat what the code clearly shows
- Don't add noise without value
