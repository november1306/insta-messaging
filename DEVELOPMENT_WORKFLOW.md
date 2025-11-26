# Development Workflow & Testing Strategy

## Overview

This document outlines the complete development cycle for testing and deploying fixes to the Instagram Messaging application.

## Environment Setup

- **Test Environment:** 185.156.43.172
- **Database:** Separate test.db for testing (preserves production data)
- **Environment:** `ENVIRONMENT=test` with `LOG_LEVEL=DEBUG`

## Full Development Cycle

### 1. **Identify Issue**

Issues can come from:
- Application errors in logs
- Bug reports
- Feature requests
- Code review findings

**Check logs for errors:**
```bash
# SSH into test server
ssh root@185.156.43.172

# View recent errors
sudo journalctl -u insta-messaging -n 100 --no-pager | grep -i error

# Follow live logs
sudo journalctl -u insta-messaging -f
```

### 2. **Create Fix Branch**

```bash
# Create a new branch for the fix
git checkout -b fix/description-of-issue

# Make your changes locally
# Test locally if possible

# Commit changes
git add .
git commit -m "fix: description of what was fixed"

# Push to GitHub
git push origin fix/description-of-issue
```

### 3. **Deploy to Test Environment**

**Option A: Deploy specific branch**
1. Go to GitHub Actions: https://github.com/november1306/insta-messaging/actions
2. Click "Deploy to Test Environment"
3. Click "Run workflow"
4. Enter your branch name (e.g., `fix/description-of-issue`)
5. Click "Run workflow"

**Option B: Deploy current branch via workflow**
```bash
# The workflow will auto-detect the current branch
# Just trigger it from the Actions tab
```

### 4. **Verify Fix on Test**

After deployment completes:

```bash
# 1. Check service status
curl http://185.156.43.172/health

# 2. Check API documentation
# Open in browser: http://185.156.43.172/docs

# 3. Test the specific fix
# Make API calls or use the frontend

# 4. Monitor logs for errors
ssh root@185.156.43.172
sudo journalctl -u insta-messaging -f

# 5. Test webhooks (if applicable)
# Use ngrok URL from deployment output
```

**Verification Checklist:**
- [ ] Service starts without errors
- [ ] Health endpoint returns 200 OK
- [ ] API docs load correctly
- [ ] Frontend loads without console errors
- [ ] Specific bug/issue is resolved
- [ ] No new errors in logs
- [ ] Database migrations ran successfully (if any)

### 5. **Create Pull Request**

Once verified on test:

```bash
# Create PR via GitHub CLI or web interface
gh pr create --base main --title "fix: description" --body "
## Summary
Brief description of what was fixed

## Problem
What issue this addresses

## Solution
How it was fixed

## Testing
- [x] Tested on test environment (185.156.43.172)
- [x] Service starts successfully
- [x] No errors in logs
- [x] Specific functionality works as expected

## Test URLs
- Health: http://185.156.43.172/health
- API Docs: http://185.156.43.172/docs
"
```

### 6. **Code Review & Merge**

- Wait for review/approval
- Address any feedback
- Merge to `main` when approved

### 7. **Production Deployment**

**Currently Manual:**
1. Go to GitHub Actions
2. Click "Deploy to Production VPS"
3. Click "Run workflow"
4. Verify production deployment

**Future: Automatic deployment on merge to main (optional)**

## Error Identification Workflow

### Finding Errors in Test Environment

```bash
# SSH to test server
ssh root@185.156.43.172

# Check service status
sudo systemctl status insta-messaging

# View recent errors (last 100 lines)
sudo journalctl -u insta-messaging -n 100 --no-pager | grep -E "(ERROR|CRITICAL|Exception|Traceback)"

# Search for specific error
sudo journalctl -u insta-messaging --no-pager | grep "specific error message"

# View all logs since last restart
sudo journalctl -u insta-messaging --no-pager --since "1 hour ago"

# Check database migrations status
cd /opt/insta-messaging
sudo -u insta-messaging /opt/insta-messaging/venv/bin/alembic current
```

### Common Error Categories

1. **Startup Errors**
   - Import errors
   - Configuration errors
   - Database connection issues

2. **Runtime Errors**
   - API endpoint errors
   - Webhook processing errors
   - Database query errors

3. **Integration Errors**
   - Instagram API errors
   - CRM integration errors
   - Authentication errors

## Quick Commands Reference

### Test Server Access
```bash
# SSH to test server
ssh root@185.156.43.172

# View logs
sudo journalctl -u insta-messaging -f

# Restart service
sudo systemctl restart insta-messaging

# Check service status
sudo systemctl status insta-messaging

# Check database
sqlite3 /opt/insta-messaging/data/test.db ".tables"

# Check Python version in venv
/opt/insta-messaging/venv/bin/python --version

# Check installed packages
/opt/insta-messaging/venv/bin/pip list
```

### Local Development
```bash
# Run locally
./scripts/linux/dev-all.sh

# Run tests (if any)
pytest

# Check code quality
flake8 app/
```

## Rollback Strategy

If a deployment breaks:

```bash
# SSH to test server
ssh root@185.156.43.172

# Go to app directory
cd /opt/insta-messaging

# Check recent commits
git log --oneline -10

# Rollback to previous commit
sudo -u insta-messaging git checkout <previous-commit-hash>

# Restart service
sudo systemctl restart insta-messaging

# Or deploy a known-good branch via GitHub Actions
```

## Best Practices

1. **Always test on test environment first** - Never deploy untested code
2. **Check logs after every deployment** - Ensure no new errors
3. **Use descriptive commit messages** - Helps with debugging later
4. **Keep PRs small and focused** - Easier to review and debug
5. **Document breaking changes** - Update docs if API changes
6. **Monitor after production deploy** - Watch logs for 5-10 minutes

## Troubleshooting

### Service won't start
```bash
# Check detailed logs
sudo journalctl -u insta-messaging -n 50 --no-pager

# Try manual start to see errors
cd /opt/insta-messaging
sudo -u insta-messaging /opt/insta-messaging/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Database errors
```bash
# Check migrations
cd /opt/insta-messaging
sudo -u insta-messaging /opt/insta-messaging/venv/bin/alembic current
sudo -u insta-messaging /opt/insta-messaging/venv/bin/alembic history

# Re-run migrations
sudo -u insta-messaging /opt/insta-messaging/venv/bin/alembic upgrade head
```

### Permission errors
```bash
# Fix ownership
sudo chown -R insta-messaging:insta-messaging /opt/insta-messaging

# Fix data directory permissions
sudo chown insta-messaging:insta-messaging /opt/insta-messaging/data
sudo chmod 755 /opt/insta-messaging/data
```

## Next Steps

1. **Set up automated testing** - Add pytest tests
2. **Set up error monitoring** - Sentry or similar
3. **Add health checks** - More detailed health endpoint
4. **Set up staging environment** - Separate from test if needed
5. **Automate production deployments** - Deploy on merge to main (optional)
