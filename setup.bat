@echo off
echo ========================================
echo Instagram Messenger Automation Setup
echo ========================================
echo.

echo [1/4] Creating conda environment...
call conda env create -f environment.yml
if errorlevel 1 (
    echo Error: Failed to create conda environment
    pause
    exit /b 1
)

echo.
echo [2/4] Activating environment...
call conda activate insta-auto
if errorlevel 1 (
    echo Error: Failed to activate environment
    pause
    exit /b 1
)

echo.
echo [3/4] Checking for .env file...
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit .env file and add your credentials!
    echo.
) else (
    echo .env file already exists
)

echo.
echo [4/4] Running database migrations...
call alembic upgrade head
if errorlevel 1 (
    echo Error: Failed to run migrations
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env file with your credentials
echo 2. Run: conda activate insta-auto
echo 3. Run: uvicorn app.main:app --reload
echo.
echo See SETUP.md for detailed instructions
echo.
pause
