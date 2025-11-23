@echo off
REM Windows Build Script
REM Builds production frontend

setlocal enabledelayedexpansion

echo ========================================
echo  Building Production Frontend
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

echo [OK] Building frontend...
cd frontend
call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed
    cd ..
    exit /b 1
)
cd ..

echo.
echo ========================================
echo  Build Complete!
echo ========================================
echo.
echo Frontend built to: frontend\dist\
echo Served by backend at: http://localhost:8000/chat
echo.
echo To start production server: scripts\win\start.bat
echo.

endlocal
