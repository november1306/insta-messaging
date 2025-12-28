@echo off
REM Windows Development All Services Script (Background Mode)
REM Starts ngrok, backend, and frontend WITHOUT separate windows
REM Logs are written to .logs\ directory

setlocal enabledelayedexpansion

echo ========================================
echo  Starting Development Services
echo  (Background Mode - No Windows)
echo ========================================
echo.

echo [CHECK] Verifying environment...
echo.

REM Check if venv exists
if not exist "venv\" (
    echo [ERROR] Virtual environment not found
    echo Please run 'scripts\win\install.bat' first
    exit /b 1
)
echo [OK] Virtual environment found

REM Check if .env exists
if not exist ".env" (
    echo [ERROR] .env file not found
    echo Please run 'scripts\win\install.bat' or copy .env.example to .env
    exit /b 1
)
echo [OK] .env file found

REM Check if frontend dependencies are installed
if not exist "frontend\node_modules\" (
    echo [ERROR] Frontend dependencies not installed
    echo Please run 'scripts\win\install.bat' first
    exit /b 1
)
echo [OK] Frontend dependencies installed

REM Create logs directory
if not exist ".logs\" mkdir .logs
echo.

echo [1/3] Starting backend server (background)...
REM Use PowerShell to start process in background without window
powershell -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > .logs\backend.log 2>&1' -WindowStyle Hidden"
timeout /t 3 /nobreak >nul
echo [OK] Backend started (http://localhost:8000)
echo      Logs: .logs\backend.log

echo.
echo [2/3] Starting ngrok tunnel (background)...
powershell -Command "Start-Process -FilePath 'ngrok.exe' -ArgumentList 'http', '8000' -WindowStyle Hidden -RedirectStandardOutput '.logs\ngrok.log' -RedirectStandardError '.logs\ngrok-error.log'"
timeout /t 2 /nobreak >nul
echo [OK] ngrok started (UI at http://localhost:4040)
echo      Logs: .logs\ngrok.log

echo.
echo [3/3] Starting frontend server (background)...
powershell -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'cd frontend && npm run dev > ..\.logs\frontend.log 2>&1' -WindowStyle Hidden"
timeout /t 2 /nobreak >nul
echo [OK] Frontend started (http://localhost:5173)
echo      Logs: .logs\frontend.log

echo.
echo ========================================
echo  All Services Running (Background)
echo ========================================
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo  API Docs: http://localhost:8000/docs
echo  ngrok UI: http://localhost:4040
echo ========================================
echo.
echo  Log Files:
echo  - Backend:  .logs\backend.log
echo  - Frontend: .logs\frontend.log
echo  - ngrok:    .logs\ngrok.log
echo ========================================
echo.
echo Services are running in background (no windows).
echo To stop all services, run: scripts\win\stop-all.bat
echo To view logs: type .logs\backend.log (or frontend.log, ngrok.log)
echo.

endlocal
