# Development startup script for Instagram Messenger Automation (PowerShell)
# Starts both FastAPI backend and Vue frontend in parallel

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 Starting Instagram Messenger Automation (Development Mode)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if frontend dependencies are installed
if (-Not (Test-Path "frontend\node_modules")) {
    Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location frontend
    npm install
    Set-Location ..
}

Write-Host ""
Write-Host "Starting servers:" -ForegroundColor Cyan
Write-Host "  - Backend (FastAPI):  http://localhost:8000"
Write-Host "  - Frontend (Vue):     http://localhost:5173"
Write-Host "  - API Docs:           http://localhost:8000/docs"
Write-Host "  - Chat UI (dev):      http://localhost:5173"
Write-Host "  - Chat UI (prod URL): http://localhost:8000/chat (after build)"
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Start FastAPI backend in background
Write-Host "🐍 Starting FastAPI backend..." -ForegroundColor Green
$backend = Start-Process -FilePath "uvicorn" -ArgumentList "app.main:app --reload --port 8000" -PassThru -NoNewWindow

# Wait a moment for backend to start
Start-Sleep -Seconds 2

# Start Vue frontend dev server
Write-Host "⚡ Starting Vue frontend..." -ForegroundColor Green
try {
    Set-Location frontend
    npm run dev
} finally {
    # Cleanup: Kill backend process when frontend stops
    if ($backend -and !$backend.HasExited) {
        Write-Host ""
        Write-Host "🛑 Shutting down backend..." -ForegroundColor Yellow
        Stop-Process -Id $backend.Id -Force
    }
    Set-Location ..
}
