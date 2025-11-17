@echo off
REM Development startup script for Instagram Messenger Automation (Windows CMD)
REM Starts both FastAPI backend and Vue frontend in parallel

echo ============================================================
echo 🚀 Starting Instagram Messenger Automation (Development Mode)
echo ============================================================
echo.

REM Check if frontend dependencies are installed
if not exist "frontend\node_modules" (
    echo 📦 Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo.
echo Starting servers:
echo   - Backend (FastAPI):  http://localhost:8000
echo   - Frontend (Vue):     http://localhost:5173
echo   - API Docs:           http://localhost:8000/docs
echo   - Chat UI (dev):      http://localhost:5173
echo   - Chat UI (prod URL): http://localhost:8000/chat (after build)
echo.
echo Press Ctrl+C to stop all servers
echo ============================================================
echo.

REM Start FastAPI backend in background
echo 🐍 Starting FastAPI backend...
start "FastAPI Backend" cmd /c "uvicorn app.main:app --reload --port 8000"

REM Wait a moment for backend to start
timeout /t 2 /nobreak >nul

REM Start Vue frontend dev server
echo ⚡ Starting Vue frontend...
cd frontend
call npm run dev
cd ..
