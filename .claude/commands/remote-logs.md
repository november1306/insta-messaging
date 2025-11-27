# View Remote Application Logs

Display logs from the production server.

## VPS Connection
- **Host**: 185.156.43.172
- **SSH Key**: `C:\Users\tol13\.ssh\id_ed25519`

## Logs to Check:

1. **Application logs** (uvicorn/FastAPI):
   ```bash
   ssh -i "C:\Users\tol13\.ssh\id_ed25519" root@185.156.43.172 "tail -n 50 /opt/insta-messaging/backend.log"
   ```

2. **System service logs** (if using systemd):
   ```bash
   ssh -i "C:\Users\tol13\.ssh\id_ed25519" root@185.156.43.172 "journalctl -u insta-messaging -n 50 --no-pager"
   ```

3. **nginx logs** (if applicable):
   ```bash
   ssh -i "C:\Users\tol13\.ssh\id_ed25519" root@185.156.43.172 "tail -n 30 /var/log/nginx/error.log"
   ```

Display the logs in a readable format. If a specific log file doesn't exist, skip it and try the next one.
