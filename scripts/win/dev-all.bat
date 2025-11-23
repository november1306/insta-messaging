@echo off
REM Windows Development All Services Script
REM Starts ngrok, backend, and frontend in development mode

setlocal enabledelayedexpansion

echo ========================================
echo  Starting All Development Services
echo ========================================
echo.

REM Check if venv exists
if not exist "venv\" (
    echo [ERROR] Virtual environment not found
    echo Please run 'scripts\win\install.bat' first
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo [ERROR] .env file not found
    echo Please run 'scripts\win\install.bat' or copy .env.example to .env
    exit /b 1
)

REM Check if frontend dependencies are installed
if not exist "frontend\node_modules\" (
    echo [ERROR] Frontend dependencies not installed
    echo Please run 'scripts\win\install.bat' first
    exit /b 1
)

REM Check if ngrok is installed
where ngrok >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ngrok is not installed or not in PATH
    echo.
    echo ngrok is required for Instagram webhook testing.
    echo Please install from: https://ngrok.com/download
    echo.
    echo After installation, add ngrok to your PATH or place it in the project directory.
    exit /b 1
)

REM Check if ports are available
netstat -ano | findstr ":8000" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] Port 8000 is already in use
    echo Please stop any services using this port
    exit /b 1
)

netstat -ano | findstr ":5173" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] Port 5173 is already in use
    echo Please stop any services using this port
    exit /b 1
)

echo [1/3] Starting ngrok tunnel...
start "ngrok" ngrok http 8000
timeout /t 2 /nobreak >nul
echo [OK] ngrok started (UI at http://localhost:4040)

echo.
echo [2/3] Starting backend server...
call venv\Scripts\activate.bat
start "backend" cmd /k "venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
echo [OK] Backend started (http://localhost:8000)

echo.
echo [3/3] Starting frontend server...
echo [OK] Frontend will start on http://localhost:5173
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
echo Press Ctrl+C to stop all services
echo NOTE: You may need to manually close backend/ngrok windows
echo.

cd frontend
call npm run dev

REM When frontend stops, inform user
echo.
echo [INFO] Frontend stopped
echo Please manually close the backend and ngrok windows
echo Or use Task Manager to kill: uvicorn, ngrok, node

cd ..
endlocal
