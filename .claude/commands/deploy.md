# Deploy to Production VPS

Deploy the current changes to the production server at 185.156.43.172.

## Deployment Steps:

1. **Ensure local changes are committed** - Check git status locally
2. **Push to origin** if not already pushed
3. **Connect to VPS** and pull latest changes:
   ```bash
   ssh -i "C:\Users\tol13\.ssh\id_ed25519" root@185.156.43.172 "cd /opt/insta-messaging && git pull origin main"
   ```
4. **Restart the service** if needed:
   ```bash
   ssh -i "C:\Users\tol13\.ssh\id_ed25519" root@185.156.43.172 "systemctl restart insta-messaging || supervisorctl restart insta-messaging"
   ```
5. **Verify deployment**:
   ```bash
   ssh -i "C:\Users\tol13\.ssh\id_ed25519" root@185.156.43.172 "cd /opt/insta-messaging && git log -1 --oneline && ps aux | grep uvicorn | grep -v grep"
   ```

Provide clear feedback about each step and any errors encountered.
