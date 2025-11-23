@echo off
REM Windows Stop All Services Script
REM Stops all development services (ngrok, backend, frontend)

setlocal enabledelayedexpansion

echo ========================================
echo  Stopping All Development Services
echo ========================================
echo.

set FOUND_PROCESS=0

REM Stop frontend (Vite on port 5173)
echo [1/3] Stopping frontend server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do (
    set PID=%%a
    if not "!PID!"=="0" (
        taskkill /F /PID !PID! >nul 2>&1
        if not errorlevel 1 (
            echo [OK] Frontend stopped (PID: !PID!)
            set FOUND_PROCESS=1
        )
    )
)
if %FOUND_PROCESS%==0 echo [INFO] Frontend not running

set FOUND_PROCESS=0

REM Stop backend (uvicorn on port 8000)
echo.
echo [2/3] Stopping backend server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    set PID=%%a
    if not "!PID!"=="0" (
        taskkill /F /PID !PID! >nul 2>&1
        if not errorlevel 1 (
            echo [OK] Backend stopped (PID: !PID!)
            set FOUND_PROCESS=1
        )
    )
)
if %FOUND_PROCESS%==0 echo [INFO] Backend not running

set FOUND_PROCESS=0

REM Stop ngrok (on port 4040)
echo.
echo [3/3] Stopping ngrok tunnel...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":4040.*LISTENING"') do (
    set PID=%%a
    if not "!PID!"=="0" (
        taskkill /F /PID !PID! >nul 2>&1
        if not errorlevel 1 (
            echo [OK] ngrok stopped (PID: !PID!)
            set FOUND_PROCESS=1
        )
    )
)
if %FOUND_PROCESS%==0 echo [INFO] ngrok not running

REM Also kill any stray processes by name
taskkill /F /IM ngrok.exe >nul 2>&1
taskkill /F /IM node.exe /FI "WINDOWTITLE eq frontend*" >nul 2>&1

echo.
echo ========================================
echo  All Services Stopped
echo ========================================
echo.

endlocal
