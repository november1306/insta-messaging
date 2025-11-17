# Production build script for Instagram Messenger Automation (PowerShell)
# Builds the Vue frontend and prepares for deployment

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "🏗️  Building Instagram Messenger Automation" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if frontend dependencies are installed
if (-Not (Test-Path "frontend\node_modules")) {
    Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location frontend
    npm install
    Set-Location ..
}

# Build frontend
Write-Host "⚡ Building Vue frontend..." -ForegroundColor Green
Set-Location frontend
npm run build
Set-Location ..

Write-Host ""
Write-Host "✅ Build complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Frontend built to: frontend\dist\" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run in production mode:" -ForegroundColor Yellow
Write-Host "  uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "Access points:" -ForegroundColor Cyan
Write-Host "  - API:      http://localhost:8000/api/v1"
Write-Host "  - Chat UI:  http://localhost:8000/chat"
Write-Host "  - Docs:     http://localhost:8000/docs"
Write-Host "  - Webhooks: http://localhost:8000/webhooks/instagram"
Write-Host ""
