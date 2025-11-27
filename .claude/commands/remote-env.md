# Remote Environment Information

Connect to the production VPS and display environment status.

## VPS Connection Details
- **Host**: 185.156.43.172
- **User**: root
- **SSH Key**: `C:\Users\tol13\.ssh\id_ed25519`
- **App Path**: `/opt/insta-messaging/`
- **Service User**: insta-messaging

## Commands to run:

Check the remote environment status by running these commands via SSH:

```bash
ssh -i "C:\Users\tol13\.ssh\id_ed25519" root@185.156.43.172 "cd /opt/insta-messaging && git status && git log -1 --oneline && ps aux | grep uvicorn | grep -v grep"
```

Display this information to the user in a clear format showing:
1. Current git branch and status
2. Last commit deployed
3. Running processes (uvicorn status)
4. Any uncommitted changes on the server
