@echo off
REM Windows Development All Services Script
REM Starts ngrok, backend, and frontend in development mode

setlocal enabledelayedexpansion

echo ========================================
echo  Starting All Development Services
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

echo.

echo [1/3] Starting backend server...
call venv\Scripts\activate.bat
start "backend" cmd /k "venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
echo [OK] Backend started (http://localhost:8000)

echo.
echo [2/3] Starting ngrok tunnel...
start "ngrok" ngrok http 8000
timeout /t 2 /nobreak >nul
echo [OK] ngrok started (UI at http://localhost:4040)

echo.
echo [3/3] Starting frontend server...
start "frontend" cmd /k "cd frontend && npm run dev"
timeout /t 2 /nobreak >nul
echo [OK] Frontend started (http://localhost:5173)
echo.
echo ========================================
echo  All Services Running
echo ========================================
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo  API Docs: http://localhost:8000/docs
echo  ngrok UI: http://localhost:4040
echo ========================================
echo.
echo All services are running in separate windows.
echo To stop all services, run: scripts\win\stop-all.bat
echo Or manually close the backend, ngrok, and frontend windows.

endlocal
