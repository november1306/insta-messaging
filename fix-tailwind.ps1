# Fix Tailwind CSS v4 to v3 - PowerShell version

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Fixing Tailwind CSS Installation" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location frontend

Write-Host "Removing old node_modules..." -ForegroundColor Yellow
if (Test-Path "node_modules") {
    Remove-Item -Recurse -Force node_modules
    Write-Host "OK: node_modules removed" -ForegroundColor Green
} else {
    Write-Host "SKIP: node_modules doesn't exist" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Removing package-lock.json..." -ForegroundColor Yellow
if (Test-Path "package-lock.json") {
    Remove-Item package-lock.json
    Write-Host "OK: package-lock.json removed" -ForegroundColor Green
} else {
    Write-Host "SKIP: package-lock.json doesn't exist" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Installing dependencies with Tailwind v3..." -ForegroundColor Yellow
npm install

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Done! Tailwind v3 should now be installed." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now run: .\dev.ps1" -ForegroundColor Cyan
Write-Host ""
