# 🔒 Security Quick Reference

## ⚡ Quick Checks Before Commit

```bash
# 1. Check what you're committing
git diff --staged

# 2. Search for potential secrets
git diff --staged | grep -iE "(token|key|password|secret|api_key)"

# 3. Verify .env is not staged
git status | grep ".env"
```

## 🚨 Emergency: Secret Exposed!

### Just Committed (Not Pushed)
```bash
# Undo commit, keep changes
git reset --soft HEAD~1

# Unstage the file
git restore --staged <file-with-secret>

# Add to .gitignore
echo "<file-with-secret>" >> .gitignore
```

### Already Pushed to GitHub
```bash
# 1. REVOKE THE CREDENTIAL IMMEDIATELY!
#    - GitHub: https://github.com/settings/tokens
#    - Instagram: Facebook Developer Console

# 2. Remove from history (DANGEROUS - coordinate with team)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch <file>" \
  --prune-empty --tag-name-filter cat -- --all

# 3. Force push (WARNING: Rewrites history)
git push origin --force --all

# 4. Generate new credentials
# 5. Update all systems
```

## ✅ Safe Patterns

### Environment Variables
```python
# ✅ GOOD
import os
API_KEY = os.getenv("API_KEY")

# ❌ BAD
API_KEY = "sk-1234567890"
```

### Logging
```python
# ✅ GOOD
logger.info(f"User {user_id} authenticated")

# ❌ BAD
logger.info(f"Token: {token}")
```

### Configuration
```python
# ✅ GOOD
from app.config import settings
token = settings.instagram_page_access_token

# ❌ BAD
token = "IGAALkT2BsMhxBZAFR..."
```

## 📁 Files to Never Commit

```gitignore
.env                          # Environment variables
.env.local                    # Local overrides
.kiro/settings/mcp.json       # Kiro IDE tokens
*.pem                         # Private keys
*.key                         # Key files
id_rsa                        # SSH keys
credentials.json              # Service account keys
```

## 🔍 Pre-Commit Checklist

- [ ] No hardcoded tokens/keys/passwords
- [ ] .env file not in git status
- [ ] Sensitive files in .gitignore
- [ ] No credentials in comments
- [ ] No test data with real credentials

## 🛠️ Useful Commands

```bash
# Find potential secrets in repo
git grep -iE "(password|token|key|secret)" | grep -v ".md"

# Check if file is ignored
git check-ignore <filename>

# See what's tracked by git
git ls-files | grep <pattern>

# Remove file from git but keep locally
git rm --cached <file>
```

## 📞 Need Help?

1. Check [SECURITY.md](../SECURITY.md) for detailed guide
2. Review [.gitignore](../.gitignore) for protected files
3. Open a private security advisory on GitHub

---

**Remember**: When in doubt, DON'T commit. Ask first!
