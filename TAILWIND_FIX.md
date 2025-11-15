# Fix for Tailwind CSS v4 PostCSS Error

## The Problem
Your `package-lock.json` still has Tailwind CSS v4.1.17 locked in, even though `package.json` was updated to v3.4.1.

## The Solution

Run these commands in your `frontend` directory on Windows:

### PowerShell:
```powershell
cd frontend

# Remove old dependencies
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json

# Reinstall with Tailwind v3
npm install

cd ..
```

### CMD:
```cmd
cd frontend

REM Remove old dependencies
rmdir /s /q node_modules
del package-lock.json

REM Reinstall with Tailwind v3
npm install

cd ..
```

## What This Does

1. **Removes `node_modules`** - Deletes all installed packages (including Tailwind v4)
2. **Removes `package-lock.json`** - Deletes the lock file that has v4 locked in
3. **Runs `npm install`** - Reinstalls everything based on `package.json` (which specifies v3.4.1)

## After Running

The error should be gone and you'll see:
- `tailwindcss@3.4.1` in your `node_modules`
- Updated `package-lock.json` with v3 dependencies

Then run `dev.bat` or `.\dev.ps1` again and it should work!

## Why This Happened

When npm installs packages, it creates a `package-lock.json` that locks the exact versions. Even if you change `package.json`, npm uses the lock file unless you delete it and reinstall.
