@echo off
REM Production build script for Instagram Messenger Automation (Windows CMD)
REM Builds the Vue frontend and prepares for deployment

echo ============================================
echo 🏗️  Building Instagram Messenger Automation
echo ============================================
echo.

REM Check if frontend dependencies are installed
if not exist "frontend\node_modules" (
    echo 📦 Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

REM Build frontend
echo ⚡ Building Vue frontend...
cd frontend
call npm run build
cd ..

echo.
echo ✅ Build complete!
echo.
echo Frontend built to: frontend\dist\
echo.
echo To run in production mode:
echo   uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo Access points:
echo   - API:      http://localhost:8000/api/v1
echo   - Chat UI:  http://localhost:8000/chat
echo   - Docs:     http://localhost:8000/docs
echo   - Webhooks: http://localhost:8000/webhooks/instagram
echo.
pause
