@echo off
REM Windows Restart All Services Script
REM Stops all services, then starts them again

setlocal enabledelayedexpansion

echo ========================================
echo  Restarting All Development Services
echo ========================================
echo.

REM Step 1: Stop all services
echo [STEP 1/2] Stopping existing services...
echo.
call "%~dp0stop-all.bat"

echo.
echo Waiting 2 seconds before restart...
timeout /t 2 /nobreak >nul
echo.

REM Step 2: Start all services
echo [STEP 2/2] Starting services...
echo.
call "%~dp0dev-all.bat"

endlocal
