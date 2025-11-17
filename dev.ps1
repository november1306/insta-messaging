# Development startup script for Instagram Messenger Automation (PowerShell)
# Starts FastAPI backend, Vue frontend, and ngrok tunnel in parallel

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 Starting Instagram Messenger Automation (Development Mode)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if ngrok is installed
$ngrokInstalled = Get-Command ngrok -ErrorAction SilentlyContinue
if (-Not $ngrokInstalled) {
    Write-Host "⚠️  WARNING: ngrok not found!" -ForegroundColor Yellow
    Write-Host "   Instagram webhooks require ngrok for local development." -ForegroundColor Yellow
    Write-Host "   Download from: https://ngrok.com/download" -ForegroundColor Yellow
    Write-Host ""
}

# Check if frontend dependencies are installed
if (-Not (Test-Path "frontend\node_modules")) {
    Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location frontend
    npm install
    Set-Location ..
}

Write-Host ""
Write-Host "Starting servers:" -ForegroundColor Cyan
Write-Host "  - Backend (FastAPI):  http://localhost:8000" -ForegroundColor White
Write-Host "  - Frontend (Vue):     http://localhost:5173" -ForegroundColor White
Write-Host "  - API Docs:           http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - Chat UI (dev):      http://localhost:5173" -ForegroundColor White
Write-Host "  - Chat UI (prod):     http://localhost:8000/chat (after build)" -ForegroundColor White
if ($ngrokInstalled) {
    Write-Host "  - ngrok tunnel:       Starting... (check logs for URL)" -ForegroundColor White
}
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Start ngrok tunnel in background (if installed)
$ngrok = $null
if ($ngrokInstalled) {
    Write-Host "🌐 Starting ngrok tunnel..." -ForegroundColor Green
    $ngrok = Start-Process -FilePath "ngrok" -ArgumentList "http 8000" -PassThru -NoNewWindow
    Start-Sleep -Seconds 3
    Write-Host "   ✓ ngrok started (check http://localhost:4040 for tunnel URL)" -ForegroundColor Green
    Write-Host ""
}

# Start FastAPI backend in background
Write-Host "🐍 Starting FastAPI backend..." -ForegroundColor Green
$backend = Start-Process -FilePath "uvicorn" -ArgumentList "app.main:app --reload --port 8000" -PassThru -NoNewWindow

# Wait a moment for backend to start
Start-Sleep -Seconds 2

# Start Vue frontend dev server
Write-Host "⚡ Starting Vue frontend..." -ForegroundColor Green
Write-Host ""
try {
    Set-Location frontend
    npm run dev
} finally {
    # Cleanup: Kill all background processes when frontend stops
    Write-Host ""
    Write-Host "🛑 Shutting down all services..." -ForegroundColor Yellow
    
    if ($backend -and !$backend.HasExited) {
        Write-Host "   Stopping FastAPI backend..." -ForegroundColor Yellow
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
    
    if ($ngrok -and !$ngrok.HasExited) {
        Write-Host "   Stopping ngrok tunnel..." -ForegroundColor Yellow
        Stop-Process -Id $ngrok.Id -Force -ErrorAction SilentlyContinue
    }
    
    Set-Location ..
    Write-Host "✓ All services stopped" -ForegroundColor Green
}
