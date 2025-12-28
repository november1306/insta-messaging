# SESSION_SECRET Security Guide

## Overview

`SESSION_SECRET` is a **critical security configuration** that serves two purposes in this application:

1. **JWT Token Signing** - Signs authentication tokens for the web UI
2. **OAuth Token Encryption** - Encrypts Instagram OAuth access tokens stored in the database

⚠️ **CRITICAL**: Changing or losing `SESSION_SECRET` after deploying to production will make all encrypted OAuth tokens undecryptable, requiring all users to re-authenticate their Instagram accounts.

## Setup

### 1. Generate a Secure Secret

Use Python's built-in `secrets` module to generate a cryptographically secure random value:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Example output:
```
siYC7x-RtyWUk73DECXc6SNmXowUMWZag7ZQUPGQKBI
```

### 2. Add to Environment

Add the generated secret to your `.env` file:

```bash
SESSION_SECRET=siYC7x-RtyWUk73DECXc6SNmXowUMWZag7ZQUPGQKBI
```

### 3. Protect the Secret

- ✅ **DO**: Store in `.env` file (already in `.gitignore`)
- ✅ **DO**: Use environment variables in production (GitHub Secrets, AWS Secrets Manager, etc.)
- ✅ **DO**: Backup the secret securely (encrypted password manager, secure vault)
- ❌ **DON'T**: Commit to git
- ❌ **DON'T**: Share in plain text (Slack, email, etc.)
- ❌ **DON'T**: Change after storing encrypted data in production

## How It Works

### Encryption Process

When an Instagram account is connected via OAuth:

1. User completes Instagram OAuth flow
2. Instagram returns long-lived access token (60-day validity)
3. Application encrypts token using `SESSION_SECRET` as master key
4. Encrypted token stored in `accounts.access_token_encrypted` column
5. Original token is discarded from memory

### Decryption Process

When sending a message via Instagram API:

1. Application reads `access_token_encrypted` from database
2. Decrypts using `SESSION_SECRET`
3. Uses decrypted token to call Instagram Graph API
4. Token remains encrypted in database

### Encryption Details

- **Algorithm**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Key Derivation**: PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Salt**: Static (`instagram-oauth-encryption-v1`) for deterministic keys
- **Library**: Python `cryptography` package (industry-standard)

See `app/services/encryption_service.py` for implementation.

## Development vs Production

### Development Mode (`ENVIRONMENT=development`)

**Without SESSION_SECRET:**
- Application generates random secret on each startup
- ⚠️ Warning displayed in logs (large red box)
- JWT tokens invalidated on restart (users logged out)
- **CRITICAL**: OAuth tokens become undecryptable on restart
- Runtime check warns if encrypted data exists with ephemeral secret

**With SESSION_SECRET:**
- Uses provided secret consistently
- Tokens persist across restarts
- Safe to store OAuth data

### Production Mode (`ENVIRONMENT=production`)

- `SESSION_SECRET` is **REQUIRED** (application won't start without it)
- Must be set via environment variable
- No auto-generation fallback

## Common Scenarios

### Scenario 1: First-Time Setup (Development)

**Recommended Approach:**

1. Clone repository
2. Run install script: `scripts\win\install.bat`
3. Generate secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
4. Add to `.env`: `SESSION_SECRET=<generated-secret>`
5. Start application

**Lazy Approach (NOT recommended):**

1. Clone repository
2. Run install script
3. Start application without `SESSION_SECRET`
4. See big warning box ⚠️
5. Application works but tokens won't persist

### Scenario 2: Lost SESSION_SECRET (Production)

**Symptoms:**
- Application starts successfully
- Users can log in to UI
- Instagram accounts shown in UI
- **BUT**: All API calls fail with "decryption error"
- Cannot send messages to Instagram

**Solution:**

**Option A - Restore Original Secret (Recommended):**
1. Find original `SESSION_SECRET` from:
   - Production `.env` backup
   - Secrets manager (AWS Secrets Manager, GitHub Secrets)
   - Password manager
   - Server backup
2. Restore to production environment
3. Restart application
4. Verify accounts can authenticate

**Option B - Reset All Accounts (Data Loss):**
1. Notify all users their Instagram connections will be reset
2. Back up database: `cp instagram_automation.db instagram_automation.db.backup`
3. Delete encrypted tokens:
   ```sql
   UPDATE accounts SET access_token_encrypted = NULL, token_expires_at = NULL;
   ```
4. Generate new `SESSION_SECRET`
5. Update production environment
6. Restart application
7. Have all users re-authenticate via OAuth

### Scenario 3: Planned SESSION_SECRET Rotation (Advanced)

**When to Rotate:**
- Compliance requirements (annual rotation)
- Security incident (suspected compromise)
- Migrating to new secrets management system

**Process:**

1. **Preparation:**
   ```bash
   # Generate new secret
   NEW_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   echo "New secret: $NEW_SECRET"
   ```

2. **Create Migration Script:**
   ```python
   # scripts/rotate_session_secret.py
   import asyncio
   from app.config import settings
   from app.db.connection import get_db_session
   from app.db.models import Account
   from app.services.encryption_service import get_encryption_service
   from sqlalchemy import select

   async def rotate_secret(old_secret: str, new_secret: str):
       """Re-encrypt all tokens with new secret"""
       old_encryption = get_encryption_service(old_secret)
       new_encryption = get_encryption_service(new_secret)

       async for db in get_db_session():
           result = await db.execute(
               select(Account).where(Account.access_token_encrypted.isnot(None))
           )
           accounts = result.scalars().all()

           for account in accounts:
               try:
                   # Decrypt with old secret
                   token = old_encryption.decrypt(account.access_token_encrypted)
                   # Re-encrypt with new secret
                   account.access_token_encrypted = new_encryption.encrypt(token)
                   print(f"✅ Re-encrypted token for account {account.username}")
               except Exception as e:
                   print(f"❌ Failed to re-encrypt {account.username}: {e}")

           await db.commit()
           break

   # Usage:
   # OLD_SECRET="..." NEW_SECRET="..." python scripts/rotate_session_secret.py
   ```

3. **Execute Rotation (with downtime):**
   ```bash
   # Stop application
   systemctl stop insta-messaging

   # Backup database
   cp instagram_automation.db instagram_automation.db.pre-rotation

   # Run migration
   OLD_SECRET="old-secret-here" NEW_SECRET="new-secret-here" python scripts/rotate_session_secret.py

   # Update environment variable
   sed -i 's/SESSION_SECRET=.*/SESSION_SECRET=new-secret-here/' .env

   # Restart application
   systemctl start insta-messaging

   # Verify accounts work
   curl -H "Authorization: Bearer $API_KEY" http://localhost:8000/api/v1/accounts
   ```

4. **Verification:**
   - Test message sending to Instagram
   - Check error logs for decryption failures
   - Have users verify their accounts still work

## Security Best Practices

### ✅ DO

1. **Generate strong secrets:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"  # 256-bit entropy
   ```

2. **Store securely:**
   - Development: `.env` file (gitignored)
   - Production: Environment variables from secrets manager
   - Backup: Encrypted password manager (1Password, Bitwarden, etc.)

3. **Monitor access:**
   - Audit logs for who accesses production secrets
   - Use role-based access control (RBAC)
   - Rotate on team member departure

4. **Plan for disasters:**
   - Document recovery procedures
   - Maintain secure backups
   - Test recovery process periodically

### ❌ DON'T

1. **Don't use weak secrets:**
   ```bash
   # ❌ BAD
   SESSION_SECRET=password123
   SESSION_SECRET=my-app-secret
   SESSION_SECRET=test
   ```

2. **Don't commit to git:**
   ```bash
   # ❌ BAD - This is in .gitignore, but double check!
   git add .env
   ```

3. **Don't share insecurely:**
   - ❌ Slack messages
   - ❌ Email
   - ❌ Unencrypted documents
   - ❌ Screenshots with secrets visible

4. **Don't change without migration:**
   ```bash
   # ❌ BAD - This will break all existing encrypted tokens!
   SESSION_SECRET=new-secret-here
   systemctl restart insta-messaging
   ```

## Troubleshooting

### Problem: "Invalid token" errors when accessing encrypted tokens

**Symptoms:**
```
ERROR - Failed to decrypt access token for account acc_xxx: [decryption error]
```

**Cause:** `SESSION_SECRET` doesn't match the secret used to encrypt the tokens.

**Solution:** Restore original `SESSION_SECRET` or reset all accounts (see Scenario 2).

### Problem: Users logged out after restart (development)

**Symptoms:**
- Users must re-login to UI after every restart
- No error messages
- Application works otherwise

**Cause:** Using ephemeral `SESSION_SECRET` (auto-generated on startup).

**Solution:** Set permanent `SESSION_SECRET` in `.env` file.

### Problem: Big red warning box on startup

**Symptoms:**
```
╔════════════════════════════════════════════════════════════════════════════╗
║  ⚠️  CRITICAL SECURITY WARNING: No SESSION_SECRET configured               ║
╠════════════════════════════════════════════════════════════════════════════╣
...
```

**Cause:** `SESSION_SECRET` not set in `.env` file.

**Solution:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Add output to .env as SESSION_SECRET=...
```

### Problem: Cannot decrypt existing tokens after restart

**Symptoms:**
```
╔════════════════════════════════════════════════════════════════════════════╗
║  🚨 DATA LOSS WARNING: Encrypted tokens found with ephemeral secret!      ║
╠════════════════════════════════════════════════════════════════════════════╣
```

**Cause:** Previously had `SESSION_SECRET` set, stored OAuth tokens, then removed it.

**Solution:**
1. **Preferred**: Restore original `SESSION_SECRET` from backup
2. **Nuclear**: Delete database and start fresh: `rm instagram_automation.db`

## Compliance & Auditing

### Logging

The application automatically redacts `SESSION_SECRET` from logs:

```python
# ✅ SAFE - SensitiveDataFilter removes actual secret
logger.info(f"Config loaded with SESSION_SECRET")

# ✅ SAFE - Only metadata logged
logger.info(f"Encryption service initialized")

# ❌ Would be caught by filter
logger.info(f"Secret: {settings.session_secret}")  # Redacted to [REDACTED]
```

### Audit Trail

Monitor who accesses `SESSION_SECRET`:

- **Development**: `.env` file access (file permissions)
- **Production**: Secrets manager access logs (AWS CloudTrail, GitHub audit log)

### Rotation Policy

Recommended rotation schedule:

- **Normal**: Every 12 months
- **After incident**: Immediately
- **Team changes**: Within 24 hours of departure

## References

- [Fernet Specification](https://github.com/fernet/spec/)
- [OWASP Key Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)
- [NIST SP 800-57: Key Management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- Python `cryptography` library: https://cryptography.io/

## Related Files

- `app/config.py` - Configuration loading and validation
- `app/services/encryption_service.py` - Encryption implementation
- `app/db/models.py` - Database schema with `access_token_encrypted` column
- `.env.example` - Template with `SESSION_SECRET` documentation
