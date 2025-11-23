@echo off
REM Windows Development Backend Script
REM Starts FastAPI backend server in development mode

setlocal enabledelayedexpansion

echo ========================================
echo  Starting Backend Development Server
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

REM Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    exit /b 1
)

REM Check if port 8000 is available
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8000 is already in use
    echo Please stop any services using this port or change PORT in .env
    pause
    exit /b 1
)

echo [OK] Starting FastAPI backend on http://localhost:8000
echo [OK] API documentation: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start uvicorn with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

endlocal
