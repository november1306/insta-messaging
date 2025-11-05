@echo off
echo ========================================
echo Instagram Messenger Automation
echo ========================================
echo.

echo Activating conda environment...
call conda activate insta-auto
if errorlevel 1 (
    echo.
    echo Error: Environment 'insta-auto' not found!
    echo Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting FastAPI server...
echo Server will be available at: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
