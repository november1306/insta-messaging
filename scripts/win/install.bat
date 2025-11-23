@echo off
REM Windows Installation Script
REM Idempotent setup script for fresh or existing environments

setlocal enabledelayedexpansion

echo ========================================
echo  Instagram Auto - Installation Script
echo ========================================
echo.

REM Check Python installation
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.11 or higher from python.org
    exit /b 1
)

REM Check Python version (3.11+)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if %MAJOR% LSS 3 (
    echo [ERROR] Python version is too old: %PYTHON_VERSION%
    echo Please install Python 3.11 or higher
    exit /b 1
)
if %MAJOR% EQU 3 if %MINOR% LSS 11 (
    echo [ERROR] Python version is too old: %PYTHON_VERSION%
    echo Please install Python 3.11 or higher
    exit /b 1
)
echo [OK] Python %PYTHON_VERSION% detected

REM Create virtual environment
echo.
echo [2/6] Setting up Python virtual environment...
if exist "venv\" (
    echo [OK] Virtual environment already exists
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
    echo [OK] Virtual environment created
)

REM Activate virtual environment and install dependencies
echo.
echo [3/6] Installing Python dependencies...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    exit /b 1
)

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARNING] pip upgrade failed, continuing with existing pip version
)
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies
    exit /b 1
)
echo [OK] Python dependencies installed

REM Create .env file if it doesn't exist
echo.
echo [4/6] Setting up environment configuration...
if exist ".env" (
    echo [OK] .env file already exists
) else (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] Created .env from .env.example
        echo [WARNING] Please edit .env file with your configuration
    ) else (
        echo [ERROR] .env.example file not found
        exit /b 1
    )
)

REM Run database migrations
echo.
echo [5/6] Running database migrations...
alembic upgrade head
if errorlevel 1 (
    echo [ERROR] Database migration failed
    exit /b 1
)
echo [OK] Database migrations completed

REM Install frontend dependencies
echo.
echo [6/6] Installing frontend dependencies...
if not exist "frontend\" (
    echo [ERROR] Frontend directory not found
    exit /b 1
)

cd frontend
if exist "node_modules\" (
    echo [OK] Frontend dependencies already installed
) else (
    call npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install frontend dependencies
        exit /b 1
    )
    echo [OK] Frontend dependencies installed
)
cd ..

echo.
echo ========================================
echo  Installation Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Edit .env file with your configuration
echo   2. Run 'scripts\win\dev-all.bat' to start development server
echo   3. Or run individual components:
echo      - scripts\win\dev-backend.bat (backend only)
echo      - scripts\win\dev-frontend.bat (frontend only)
echo.

endlocal
