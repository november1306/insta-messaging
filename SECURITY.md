# Security Policy

## Sensitive Data Handling Strategy

This document outlines our approach to handling sensitive data in the Instagram Messenger Automation project.

## 🔒 What is Considered Sensitive Data?

### Critical (Never Commit)
- **API Keys & Tokens**: Instagram access tokens, Facebook app secrets, Claude API keys
- **Database Credentials**: MySQL passwords, connection strings with credentials
- **Encryption Keys**: APP_SECRET_KEY for encrypting account credentials
- **Personal Access Tokens**: GitHub tokens, deployment tokens
- **Webhook Secrets**: Webhook verify tokens

### Sensitive (Encrypt in Database)
- **Instagram Account Credentials**: Access tokens, app secrets (stored encrypted in MySQL)
- **User Data**: Customer messages, conversation history (stored with proper access control)

## 📋 Current Protection Mechanisms

### 1. Environment Variables (.env)
**What goes here:**
- Database connection details
- Encryption keys
- Server configuration

**Protection:**
```bash
# .env is in .gitignore
# Never commit .env file
# Use .env.example as template
```

**Example (.env):**
```env
# Database
MYSQL_HOST=localhost
MYSQL_PASSWORD=secure_password

# Security
APP_SECRET_KEY=your-secret-key-here

# Never commit this file!
```

### 2. .gitignore Protection
**Files protected:**
```gitignore
# Environment files
.env
.envrc

# Kiro IDE settings with tokens
.kiro/settings/mcp.json

# Database files
*.db
*.sqlite3

# Logs that may contain sensitive data
*.log
```

### 3. Database Encryption
**Implementation:**
- Instagram account credentials stored encrypted in MySQL
- Uses `cryptography` library with Fernet encryption
- Encryption key from `APP_SECRET_KEY` environment variable
- Decryption only happens in memory, never logged

**Example:**
```python
from cryptography.fernet import Fernet

def encrypt_token(token: str, secret_key: str) -> str:
    """Encrypt token before storing in database"""
    f = Fernet(secret_key.encode())
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str, secret_key: str) -> str:
    """Decrypt token when needed"""
    f = Fernet(secret_key.encode())
    return f.decrypt(encrypted_token.encode()).decode()
```

### 4. GitHub Secrets
**For CI/CD:**
- Store secrets in GitHub Settings → Secrets → Actions
- Used in GitHub Actions workflows
- Never exposed in logs

**Current secrets:**
- `ANTHROPIC_API_KEY` - For Claude AI code reviews (optional)

### 5. Code Review Automation
**Bandit Security Scanner:**
- Runs on every PR
- Detects hardcoded secrets
- Flags security vulnerabilities
- Configured in `.github/workflows/code-quality.yml`

**GitHub Secret Scanning:**
- Automatically detects committed secrets
- Blocks pushes containing tokens
- Alerts on exposed credentials

## 🚨 What to Do If Secrets Are Exposed

### Immediate Actions:

1. **Revoke the exposed credential immediately**
   - GitHub tokens: https://github.com/settings/tokens
   - Instagram tokens: Regenerate in Facebook Developer Console
   - Database passwords: Change immediately

2. **Remove from git history**
   ```bash
   # If just committed (not pushed)
   git reset --soft HEAD~1
   git restore --staged <file>
   
   # If already pushed
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch <file>" \
     --prune-empty --tag-name-filter cat -- --all
   
   git push origin --force --all
   ```

3. **Update .gitignore**
   ```bash
   echo "<file-with-secret>" >> .gitignore
   git add .gitignore
   git commit -m "chore: Protect sensitive file"
   ```

4. **Generate new credentials**
   - Create new tokens/keys
   - Update in environment variables
   - Update in database (if applicable)

5. **Notify team**
   - Alert team members
   - Document the incident
   - Review access logs

## ✅ Best Practices

### For Developers

1. **Never hardcode secrets**
   ```python
   # ❌ BAD
   API_KEY = "sk-1234567890abcdef"
   
   # ✅ GOOD
   API_KEY = os.getenv("API_KEY")
   ```

2. **Use environment variables**
   ```python
   # ✅ GOOD
   from app.config import settings
   token = settings.instagram_page_access_token
   ```

3. **Never log sensitive data**
   ```python
   # ❌ BAD
   logger.info(f"Token: {token}")
   
   # ✅ GOOD
   logger.info(f"Account {account_id} authenticated")
   ```

4. **Use .env.example templates**
   ```bash
   # Copy template
   cp .env.example .env
   # Edit with your values
   nano .env
   ```

5. **Check before committing**
   ```bash
   # Review changes
   git diff
   
   # Check for secrets
   git diff | grep -i "token\|key\|password\|secret"
   ```

### For Database

1. **Encrypt credentials at rest**
   ```python
   account.access_token_encrypted = encrypt_token(token, secret_key)
   ```

2. **Decrypt only when needed**
   ```python
   # Decrypt in memory
   token = decrypt_token(account.access_token_encrypted, secret_key)
   # Use immediately
   response = api_call(token)
   # Don't store decrypted value
   ```

3. **Use parameterized queries**
   ```python
   # ✅ GOOD - Prevents SQL injection
   query = "SELECT * FROM accounts WHERE id = :id"
   result = await db.execute(query, {"id": account_id})
   ```

### For Deployment

1. **Use environment-specific configs**
   - Development: `.env.development`
   - Staging: `.env.staging`
   - Production: `.env.production`

2. **Use secret management services**
   - Railway: Built-in environment variables
   - AWS: AWS Secrets Manager
   - Azure: Azure Key Vault
   - GCP: Secret Manager

3. **Rotate credentials regularly**
   - Instagram tokens: Every 60 days
   - Database passwords: Every 90 days
   - API keys: Every 90 days

## 🔍 Security Checklist

### Before Every Commit
- [ ] No hardcoded secrets in code
- [ ] .env file not staged
- [ ] Sensitive files in .gitignore
- [ ] No tokens in comments
- [ ] No credentials in test files

### Before Every PR
- [ ] Security scan passes (Bandit)
- [ ] No secrets in diff
- [ ] Environment variables documented
- [ ] .env.example updated

### Before Deployment
- [ ] All secrets in environment variables
- [ ] Database credentials encrypted
- [ ] API tokens rotated
- [ ] Access logs reviewed
- [ ] Backup encryption verified

## 📚 Tools & Resources

### Security Scanning Tools
- **Bandit**: Python security linter (integrated in CI/CD)
- **git-secrets**: Prevents committing secrets
- **truffleHog**: Finds secrets in git history
- **detect-secrets**: Pre-commit hook for secrets

### Installation (Optional)
```bash
# Install git-secrets
brew install git-secrets  # macOS
# or
pip install detect-secrets

# Set up pre-commit hook
detect-secrets scan > .secrets.baseline
```

### Useful Commands
```bash
# Search for potential secrets in repo
git grep -i "password\|token\|key\|secret" | grep -v ".md"

# Check git history for secrets
git log -p | grep -i "password\|token\|key"

# Remove file from all git history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch <file>" \
  --prune-empty --tag-name-filter cat -- --all
```

## 🆘 Incident Response

### If You Discover an Exposed Secret:

1. **Don't panic** - Follow the process
2. **Assess impact** - What was exposed? For how long?
3. **Revoke immediately** - Disable the credential
4. **Remove from history** - Clean git history
5. **Generate new** - Create replacement credentials
6. **Update systems** - Deploy new credentials
7. **Monitor** - Watch for unauthorized access
8. **Document** - Record what happened and how it was fixed

### Contact
For security concerns, contact:
- **Email**: [Your security email]
- **GitHub**: Open a private security advisory

## 📖 Additional Resources

- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [12 Factor App - Config](https://12factor.net/config)
- [Instagram API Security](https://developers.facebook.com/docs/instagram-api/overview#security)

---

**Last Updated**: November 2, 2025  
**Version**: 1.0
