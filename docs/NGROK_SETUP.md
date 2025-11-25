# ngrok Setup Guide

## Why ngrok is Required

Instagram webhooks require a **public HTTPS URL** to receive messages. During development and testing, ngrok creates a secure tunnel from the internet to your local machine, allowing Instagram to send webhook events to your development server.

**ngrok is mandatory until you deploy to a server with a real domain name.**

## Getting Started

### 1. Create ngrok Account

1. Go to https://ngrok.com/
2. Sign up for a free account
3. Navigate to https://dashboard.ngrok.com/get-started/your-authtoken
4. Copy your auth token

### 2. Install ngrok

**Linux:**
```bash
# Download and install
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

**Windows:**
```powershell
# Download from https://ngrok.com/download
# Or use chocolatey:
choco install ngrok
```

**macOS:**
```bash
brew install ngrok/ngrok/ngrok
```

### 3. Configure Authentication

#### Local Development

Add your auth token to `.env`:
```bash
NGROK_AUTHTOKEN=your_ngrok_authtoken_here
```

When you run `scripts/linux/install.sh` or `scripts/win/install.bat`, the script will automatically configure ngrok with your token.

#### GitHub Actions / CI/CD

If you're using GitHub Actions or other CI/CD platforms:

1. **Add Secret to GitHub:**
   - Go to your repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `NGROK_AUTHTOKEN`
   - Value: Your ngrok auth token
   - Click "Add secret"

2. **Use in GitHub Actions:**
   ```yaml
   - name: Configure ngrok
     env:
       NGROK_AUTHTOKEN: ${{ secrets.NGROK_AUTHTOKEN }}
     run: |
       echo "NGROK_AUTHTOKEN=$NGROK_AUTHTOKEN" >> .env
       ./scripts/linux/install.sh
   ```

#### DigitalOcean / Other Hosting

For servers:

1. **SSH into your server**
2. **Add to .env file:**
   ```bash
   echo "NGROK_AUTHTOKEN=your_token_here" >> /path/to/project/.env
   ```
3. **Run install script:**
   ```bash
   ./scripts/linux/install.sh
   ```

## Using ngrok

### Starting ngrok

The development scripts automatically start ngrok for you:

```bash
# Linux
./scripts/linux/dev-all.sh

# Windows
scripts\win\dev-all.bat
```

### Manual Start (if needed)

```bash
ngrok http 8000
```

### Access ngrok Dashboard

When ngrok is running, visit http://localhost:4040 to:
- See your public URL
- Monitor incoming requests
- Inspect request/response details

## Configuring Instagram Webhooks

1. **Get your ngrok URL:**
   - Start your dev server: `./scripts/linux/dev-all.sh`
   - Visit http://localhost:4040
   - Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

2. **Configure Facebook App:**
   - Go to https://developers.facebook.com/apps/
   - Select your app → Products → Webhooks
   - For Instagram, add callback URL: `https://abc123.ngrok.io/webhooks/instagram`
   - Use your `FACEBOOK_VERIFY_TOKEN` from `.env` as the verify token
   - Subscribe to `messages` events

3. **Test webhook:**
   - Instagram will send a verification request
   - Check ngrok dashboard at http://localhost:4040 to see the request
   - Once verified, send a test message to your Instagram business account

## Free vs Paid ngrok

### Free Plan (sufficient for development)
- ✅ Random URL each time you restart (e.g., `https://abc123.ngrok.io`)
- ✅ 60-minute session timeout
- ✅ 1 online ngrok process
- ✅ HTTPS support
- ❌ Cannot use custom domains
- ❌ Must reconfigure webhook URL on each restart

### Paid Plans (recommended for continuous testing)
- ✅ Reserved domains (static URLs that don't change)
- ✅ No session timeouts
- ✅ Multiple simultaneous tunnels
- ✅ Custom domains
- ✅ No need to reconfigure webhooks

## Troubleshooting

### "Authtoken not found"
**Solution:** Make sure `NGROK_AUTHTOKEN` is in your `.env` file and run the install script.

### "Tunnel not found"
**Solution:** ngrok free plan only allows 1 tunnel. Stop other ngrok processes:
```bash
pkill ngrok
./scripts/linux/dev-all.sh
```

### "Session expired" (after 60 minutes on free plan)
**Solution:** Restart your dev server to get a new tunnel:
```bash
# Press Ctrl+C to stop
./scripts/linux/dev-all.sh  # Start again
```
Then update your webhook URL in Facebook Developer Portal with the new ngrok URL.

### Instagram webhooks not receiving messages
1. Check ngrok is running: http://localhost:4040
2. Check webhook is subscribed in Facebook Developer Portal
3. Check Instagram business account is connected
4. Test webhook with "Send Test Request" in Facebook Developer Portal
5. Monitor ngrok dashboard for incoming requests

## Production Deployment

Once you deploy to production with a real domain (e.g., `https://yourdomain.com`):
- You no longer need ngrok
- Configure Instagram webhooks to use your domain: `https://yourdomain.com/webhooks/instagram`
- Remove `NGROK_AUTHTOKEN` from production `.env`
- ngrok is ONLY for development/testing

## Security Notes

- ✅ **DO** add `NGROK_AUTHTOKEN` to `.gitignore` (already done)
- ✅ **DO** store token in GitHub Secrets for CI/CD
- ✅ **DO** use HTTPS URLs only for Instagram webhooks
- ❌ **DON'T** commit auth tokens to git
- ❌ **DON'T** share your ngrok auth token publicly
- ❌ **DON'T** use ngrok in production (use real domain instead)
