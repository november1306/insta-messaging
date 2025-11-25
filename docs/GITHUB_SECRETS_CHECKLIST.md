# GitHub Secrets Checklist

Quick reference for setting up GitHub Secrets for automated deployment.

## Location

```
https://github.com/YOUR_USERNAME/insta-messaging/settings/secrets/actions
```

Click **"New repository secret"** for each item below.

---

## Required Secrets

### 🖥️ VPS Connection (4 secrets)

| Name | Value | How to Get |
|------|-------|------------|
| ✅ `VPS_HOST` | `123.45.67.89` or `api.yourdomain.com` | Your VPS IP address or domain |
| ✅ `VPS_USER` | `root` | SSH username (usually `root` or `deploy`) |
| ✅ `VPS_SSH_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Run: `cat ~/.ssh/github-actions-vps` |
| ⚙️ `VPS_PORT` | `22` | SSH port (optional, defaults to 22) |

**Getting SSH Key:**
```bash
# Generate new key pair
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github-actions-vps

# Copy public key to VPS
ssh-copy-id -i ~/.ssh/github-actions-vps.pub root@YOUR_VPS_IP

# Display private key (copy entire output)
cat ~/.ssh/github-actions-vps
```

---

### 📱 Instagram/Facebook (5 secrets)

| Name | Value | How to Get |
|------|-------|------------|
| ✅ `FACEBOOK_VERIFY_TOKEN` | `my_secure_token_123` | Create any random string (remember it!) |
| ✅ `FACEBOOK_APP_SECRET` | `abc123...` | Facebook Developers → App → Settings → Basic |
| ✅ `INSTAGRAM_APP_SECRET` | `def456...` | Instagram settings in Facebook App |
| ✅ `INSTAGRAM_PAGE_ACCESS_TOKEN` | `EAA...` | Graph API Explorer (see below) |
| ✅ `INSTAGRAM_BUSINESS_ACCOUNT_ID` | `123456789` | Graph API (see below) |

#### Getting Facebook/Instagram Secrets:

1. **Go to Facebook Developers**: https://developers.facebook.com/apps/
2. **Select your app** (or create one)
3. **Add Instagram Product**: Products → Add Product → Instagram

**App Secret:**
```
Your App → Settings → Basic → App Secret → Show → Copy
```

**Page Access Token:**
```
Tools → Graph API Explorer
→ Select your app
→ User or Page: "Get Page Access Token"
→ Select your Instagram page
→ Copy the token
```

**Instagram Business Account ID:**
```
Tools → Graph API Explorer
→ GET: /me/accounts
→ Find your page ID
→ GET: /{PAGE_ID}?fields=instagram_business_account
→ Copy the "instagram_business_account" ID
```

---

### 🗄️ CRM MySQL (Optional - 5 secrets)

Only needed if you want to sync messages to external CRM database.

| Name | Value | Default |
|------|-------|---------|
| ⚙️ `CRM_MYSQL_ENABLED` | `true` or `false` | `false` |
| ⚙️ `CRM_MYSQL_HOST` | `mysql.example.com` | - |
| ⚙️ `CRM_MYSQL_USER` | `myuser` | - |
| ⚙️ `CRM_MYSQL_PASSWORD` | `securepass123` | - |
| ⚙️ `CRM_MYSQL_DATABASE` | `crm_database` | - |

If you don't use CRM integration, **skip these** or set `CRM_MYSQL_ENABLED=false`.

---

## Setup Steps

### 1. Generate SSH Key

```bash
# On your local machine
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github-actions-vps

# Copy public key to VPS
ssh-copy-id -i ~/.ssh/github-actions-vps.pub root@YOUR_VPS_IP

# Test connection
ssh -i ~/.ssh/github-actions-vps root@YOUR_VPS_IP
```

### 2. Add to GitHub

Go to repository settings:
```
https://github.com/YOUR_USERNAME/insta-messaging/settings/secrets/actions
```

Click **"New repository secret"** and add:

#### VPS_HOST
```
Name: VPS_HOST
Value: 123.45.67.89
```

#### VPS_USER
```
Name: VPS_USER
Value: root
```

#### VPS_SSH_KEY
```
Name: VPS_SSH_KEY
Value: (paste entire output of: cat ~/.ssh/github-actions-vps)
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
... (all lines)
-----END OPENSSH PRIVATE KEY-----
```

**Important**: Copy the ENTIRE key including the BEGIN and END lines!

#### Instagram/Facebook Secrets

Get from Facebook Developers Console and add each one.

### 3. Verify Secrets

After adding all secrets, your secrets page should show:

```
✅ VPS_HOST
✅ VPS_USER
✅ VPS_SSH_KEY
✅ FACEBOOK_VERIFY_TOKEN
✅ FACEBOOK_APP_SECRET
✅ INSTAGRAM_APP_SECRET
✅ INSTAGRAM_PAGE_ACCESS_TOKEN
✅ INSTAGRAM_BUSINESS_ACCOUNT_ID
```

### 4. Test Deployment

Push to main:
```bash
git add .
git commit -m "Test deployment"
git push origin main
```

Watch deployment:
```
https://github.com/YOUR_USERNAME/insta-messaging/actions
```

---

## Verification Checklist

Before first deployment, verify:

- [ ] VPS is accessible via SSH
- [ ] SSH key pair generated
- [ ] Public key added to VPS (`~/.ssh/authorized_keys`)
- [ ] Private key added to GitHub Secrets (`VPS_SSH_KEY`)
- [ ] All Instagram/Facebook secrets obtained
- [ ] All secrets added to GitHub
- [ ] Firewall allows SSH (port 22)
- [ ] Domain DNS configured (optional)

---

## Security Notes

### ✅ Safe to Store in GitHub Secrets:
- SSH private keys
- API tokens
- Database passwords
- All application secrets

GitHub Secrets are:
- ✅ Encrypted at rest
- ✅ Only exposed during workflow execution
- ✅ Never shown in logs (redacted)
- ✅ Only accessible to repository admins

### ❌ Never Commit to Git:
- `.env` files
- SSH private keys
- Any secrets or tokens
- Database passwords

These are already in `.gitignore` ✅

---

## Updating Secrets

To update a secret:

1. Go to repository secrets
2. Click on the secret name
3. Click "Update secret"
4. Paste new value
5. Click "Update secret"

Next deployment will use the new value automatically.

---

## Troubleshooting

### "Missing required secret: VPS_HOST"

**Fix**: Add the secret in GitHub repository settings.

### "Permission denied (publickey)"

**Fix**:
1. Verify `VPS_SSH_KEY` contains the ENTIRE private key
2. Check public key is in VPS `~/.ssh/authorized_keys`
3. Test manually: `ssh -i ~/.ssh/github-actions-vps root@YOUR_VPS_IP`

### "Secret is empty"

**Fix**: Make sure you clicked "Add secret" after pasting the value.

### Deployment fails with "invalid token"

**Fix**:
1. Check Facebook/Instagram tokens haven't expired
2. Regenerate tokens in Facebook Developers
3. Update GitHub Secrets
4. Re-run deployment

---

## Quick Reference Commands

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github-actions-vps

# Copy public key to VPS
ssh-copy-id -i ~/.ssh/github-actions-vps.pub root@YOUR_VPS_IP

# Display private key (for VPS_SSH_KEY secret)
cat ~/.ssh/github-actions-vps

# Display public key
cat ~/.ssh/github-actions-vps.pub

# Test SSH connection
ssh -i ~/.ssh/github-actions-vps root@YOUR_VPS_IP

# Check VPS IP
curl ifconfig.me  # From VPS
```

---

## Next Steps

After setting up secrets:

1. ✅ Push to main branch
2. ✅ Check GitHub Actions tab
3. ✅ Watch deployment logs
4. ✅ Verify app is running on VPS
5. ✅ Configure Instagram webhooks
6. ✅ Test with real messages

---

## Resources

- **GitHub Secrets Docs**: https://docs.github.com/en/actions/security-guides/encrypted-secrets
- **Facebook Developers**: https://developers.facebook.com/apps/
- **Graph API Explorer**: https://developers.facebook.com/tools/explorer/
- **Deployment Guide**: See `docs/DEPLOYMENT_GUIDE.md`
