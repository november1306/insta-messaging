# Security Setup Guide

Complete guide for setting up secure development environment.

## 🚀 Quick Setup (5 minutes)

### 1. Install Pre-Commit Hook (Recommended)

```bash
# Copy the pre-commit hook
cp .github/hooks/pre-commit.sample .git/hooks/pre-commit

# Make it executable (Linux/Mac)
chmod +x .git/hooks/pre-commit

# Windows (Git Bash)
# The hook will work automatically
```

This hook will:
- ✅ Scan for hardcoded secrets before each commit
- ✅ Prevent committing .env files
- ✅ Block credential files
- ✅ Warn about potential sensitive data

### 2. Configure Environment Variables

```bash
# Copy the template
cp .env.example .env

# Edit with your credentials
# Windows: notepad .env
# Linux/Mac: nano .env
```

**Required variables:**
```env
# Database
MYSQL_HOST=localhost
MYSQL_DATABASE=instagram_automation
MYSQL_USERNAME=your_username
MYSQL_PASSWORD=your_secure_password

# Security
APP_SECRET_KEY=generate-a-random-32-character-key

# For MVP (will be moved to database later)
FACEBOOK_VERIFY_TOKEN=your_verify_token
FACEBOOK_APP_SECRET=your_app_secret
INSTAGRAM_PAGE_ACCESS_TOKEN=your_instagram_token
```

### 3. Configure Kiro IDE MCP Settings

```bash
# Copy the template
cp .kiro/settings/mcp.json.example .kiro/settings/mcp.json

# Edit with your GitHub token
# Get token from: https://github.com/settings/tokens
```

### 4. Verify Protection

```bash
# Check .env is ignored
git check-ignore .env
# Should output: .env

# Check mcp.json is ignored
git check-ignore .kiro/settings/mcp.json
# Should output: .kiro/settings/mcp.json

# Verify nothing sensitive is staged
git status
```

## 🔐 Generating Secure Keys

### APP_SECRET_KEY (for encryption)

```python
# Python
import secrets
print(secrets.token_urlsafe(32))
```

```bash
# Linux/Mac
openssl rand -base64 32

# Windows PowerShell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

### Database Password

```python
# Python - Generate strong password
import secrets
import string
alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
password = ''.join(secrets.choice(alphabet) for i in range(20))
print(password)
```

## 🛡️ Security Layers

### Layer 1: .gitignore
**Purpose**: Prevent files from being tracked by git

**Protected files:**
- `.env` - Environment variables
- `.kiro/settings/mcp.json` - Kiro IDE tokens
- `*.pem`, `*.key` - Private keys
- `credentials.json` - Service account keys

### Layer 2: Pre-Commit Hook
**Purpose**: Scan staged changes before commit

**Checks:**
- Hardcoded secrets in code
- Forbidden file patterns
- Common credential files
- Sensitive data patterns

### Layer 3: GitHub Secret Scanning
**Purpose**: Detect secrets in pushed commits

**Features:**
- Automatic detection
- Push protection
- Alert notifications
- Partner patterns (AWS, Azure, etc.)

### Layer 4: CI/CD Security Scan
**Purpose**: Automated security testing

**Tools:**
- Bandit (Python security linter)
- Safety (dependency vulnerability check)
- Ruff (code quality)

### Layer 5: Database Encryption
**Purpose**: Encrypt sensitive data at rest

**Implementation:**
- Instagram tokens encrypted with Fernet
- Encryption key from environment
- Decryption only in memory

## 📋 Security Checklist for New Developers

### Initial Setup
- [ ] Clone repository
- [ ] Copy `.env.example` to `.env`
- [ ] Add your credentials to `.env`
- [ ] Copy `mcp.json.example` to `mcp.json`
- [ ] Add your GitHub token to `mcp.json`
- [ ] Install pre-commit hook
- [ ] Verify `.env` is in `.gitignore`
- [ ] Test that secrets aren't committed

### Daily Development
- [ ] Never hardcode secrets
- [ ] Use `settings` object for config
- [ ] Don't log sensitive data
- [ ] Review diffs before committing
- [ ] Run security checks locally

### Before PR
- [ ] Security scan passes
- [ ] No secrets in diff
- [ ] .env.example updated (without real values)
- [ ] Documentation updated

## 🔧 Troubleshooting

### "I accidentally committed a secret!"

**If not pushed yet:**
```bash
git reset --soft HEAD~1
git restore --staged <file>
# Fix the file, then commit again
```

**If already pushed:**
1. Revoke the credential immediately
2. Contact team lead
3. Follow incident response in SECURITY.md

### "Pre-commit hook is blocking my commit"

**Review the warning:**
- Is it a false positive? Add `# nosec` comment
- Is it real? Remove the secret
- Need to commit anyway? Use `git commit --no-verify` (NOT RECOMMENDED)

### "How do I share credentials with team?"

**Never commit them!** Instead:
- Use secure password manager (1Password, LastPass)
- Share via encrypted channel (Signal, encrypted email)
- Use secret management service (AWS Secrets Manager)
- Document in team wiki (not in repo)

## 📚 Additional Resources

- [Full Security Policy](../SECURITY.md)
- [Contributing Guidelines](../CONTRIBUTING.md)
- [GitHub Secret Scanning Docs](https://docs.github.com/en/code-security/secret-scanning)

---

**Questions?** Ask in team chat or open a GitHub Discussion.
