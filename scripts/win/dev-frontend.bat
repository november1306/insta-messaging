@echo off
REM Windows Development Frontend Script
REM Starts Vue/Vite frontend development server

setlocal enabledelayedexpansion

echo ========================================
echo  Starting Frontend Development Server
echo ========================================
echo.

REM Check if frontend directory exists
if not exist "frontend\" (
    echo [ERROR] Frontend directory not found
    exit /b 1
)

REM Check if node_modules exists
if not exist "frontend\node_modules\" (
    echo [ERROR] Frontend dependencies not installed
    echo Please run 'scripts\win\install.bat' first
    exit /b 1
)

echo [OK] Starting Vite frontend on http://localhost:5173
echo [OK] Make sure backend is running on port 8000 for API calls
echo.
echo Press Ctrl+C to stop the server
echo.

REM Change to frontend directory and start dev server
cd frontend
call npm run dev

cd ..
endlocal
