# Development Scripts Reference

Quick reference for all startup scripts across different platforms.

---

## Development Mode (Hot Reload)

Starts both FastAPI backend and Vue frontend with automatic reload on file changes.

| Platform | Script | Command |
|----------|--------|---------|
| **Linux/Mac** | `dev.sh` | `./dev.sh` |
| **Windows CMD** | `dev.bat` | `dev.bat` |
| **Windows PowerShell** | `dev.ps1` | `.\dev.ps1` |

**Access Points:**
- Frontend: http://localhost:5173 (Vite dev server with hot reload)
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

**When to use:**
- Local development
- Making changes to frontend or backend
- Testing UI changes instantly

---

## Production Build

Builds the Vue frontend for deployment (optimized, minified).

| Platform | Script | Command |
|----------|--------|---------|
| **Linux/Mac** | `build.sh` | `./build.sh` |
| **Windows CMD** | `build.bat` | `build.bat` |
| **Windows PowerShell** | `build.ps1` | `.\build.ps1` |

**Output:**
- Built files: `frontend/dist/`
- FastAPI serves from: http://localhost:8000/chat

**After building, run server:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**When to use:**
- Production deployment
- Testing production build locally
- Creating deployable artifact

---

## Manual Setup (Advanced)

If you prefer to run services manually:

### Development

**Terminal 1 - Backend:**
```bash
# All platforms
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
# Linux/Mac
cd frontend && npm run dev

# Windows
cd frontend
npm run dev
```

### Production

**Build:**
```bash
# All platforms
cd frontend
npm run build
cd ..
```

**Run:**
```bash
# All platforms
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Troubleshooting

### Windows: "Scripts are disabled"

If you get an execution policy error in PowerShell:

```powershell
# Option 1: Run with bypass (temporary)
powershell -ExecutionPolicy Bypass -File .\dev.ps1

# Option 2: Change policy (permanent, requires admin)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Port Already in Use

If port 8000 or 5173 is already in use:

**Find and kill process:**

```bash
# Linux/Mac
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# Windows (PowerShell)
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
Get-Process -Id (Get-NetTCPConnection -LocalPort 5173).OwningProcess | Stop-Process -Force
```

**Or change ports:**

```bash
# Backend: Different port
uvicorn app.main:app --reload --port 8080

# Frontend: Edit frontend/vite.config.js
server: {
  port: 5174  # Change this
}
```

### Frontend Not Found

If you get "Frontend not built" warning:

1. Run the build script first:
   ```bash
   ./build.sh    # or build.bat on Windows
   ```

2. Check `frontend/dist/` exists:
   ```bash
   ls frontend/dist/   # Should show index.html and assets/
   ```

### Dependencies Not Installed

**Backend dependencies:**
```bash
pip install -r requirements.txt
```

**Frontend dependencies:**
```bash
cd frontend
npm install
```

---

## What Each Script Does

### Development Scripts (`dev.*`)

1. ✅ Check if `frontend/node_modules` exists
2. ✅ Install npm dependencies if missing
3. ✅ Start FastAPI backend on port 8000
4. ✅ Start Vite dev server on port 5173
5. ✅ Enable hot reload for both

**Cleanup:**
- Linux/Mac: Press Ctrl+C (kills both processes)
- Windows CMD: Close windows manually
- Windows PowerShell: Press Ctrl+C (auto-cleanup)

### Build Scripts (`build.*`)

1. ✅ Check if `frontend/node_modules` exists
2. ✅ Install npm dependencies if missing
3. ✅ Run `npm run build` in frontend
4. ✅ Create optimized bundle in `frontend/dist/`
5. ✅ Display instructions for running server

**What gets built:**
- `frontend/dist/index.html` - Entry point
- `frontend/dist/assets/` - JS, CSS, images
- All optimized, minified, tree-shaken

---

## Quick Command Reference

| Task | Linux/Mac | Windows |
|------|-----------|---------|
| Start dev servers | `./dev.sh` | `dev.bat` |
| Build for production | `./build.sh` | `build.bat` |
| Install frontend deps | `cd frontend && npm install` | `cd frontend && npm install` |
| Install backend deps | `pip install -r requirements.txt` | `pip install -r requirements.txt` |
| Run backend only | `uvicorn app.main:app --reload` | `uvicorn app.main:app --reload` |
| Run frontend only | `cd frontend && npm run dev` | `cd frontend && npm run dev` |
| Check backend | `curl http://localhost:8000/health` | `curl http://localhost:8000/health` |

---

## Environment-Specific Notes

### Linux/Mac (Bash)
- Scripts use `/bin/bash` shebang
- `trap` for cleanup on Ctrl+C
- `&` for background processes

### Windows CMD (`.bat`)
- Uses `start` for background processes
- `timeout /t 2` for delays
- Must close windows manually on exit

### Windows PowerShell (`.ps1`)
- Colored output with `Write-Host`
- Process management with `Start-Process`
- Automatic cleanup with `try/finally`
- May require execution policy change

---

## Production Deployment

For production servers (Linux):

```bash
# Build frontend
./build.sh

# Run with Gunicorn (multiple workers)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Or use systemd service (recommended)
sudo systemctl start insta-messaging
```

For Windows servers:

```powershell
# Build frontend
.\build.ps1

# Run with Waitress (Windows WSGI server)
pip install waitress
waitress-serve --host 0.0.0.0 --port 8000 app.main:app
```

---

## See Also

- [UI_SETUP.md](UI_SETUP.md) - Complete UI setup guide
- [README.md](README.md) - Main project documentation
- [UI_DESIGN_PROPOSAL.md](UI_DESIGN_PROPOSAL.md) - Design rationale
