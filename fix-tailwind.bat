@echo off
REM Fix Tailwind CSS v4 to v3 - Windows CMD version

echo ========================================
echo Fixing Tailwind CSS Installation
echo ========================================
echo.

cd frontend

echo Removing old node_modules...
if exist node_modules (
    rmdir /s /q node_modules
    echo OK: node_modules removed
) else (
    echo SKIP: node_modules doesn't exist
)

echo.
echo Removing package-lock.json...
if exist package-lock.json (
    del package-lock.json
    echo OK: package-lock.json removed
) else (
    echo SKIP: package-lock.json doesn't exist
)

echo.
echo Installing dependencies with Tailwind v3...
call npm install

echo.
echo ========================================
echo Done! Tailwind v3 should now be installed.
echo ========================================
echo.
echo You can now run: dev.bat
echo.
pause
