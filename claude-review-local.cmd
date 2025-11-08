@echo off
REM Local Claude Code Review Script (CMD/Batch)
REM Uses Claude Code CLI to review changes before pushing

setlocal enabledelayedexpansion

set "STAGED=0"
set "BRANCH="

REM Parse arguments
:parse_args
if "%1"=="" goto check_claude
if /i "%1"=="--staged" (
    set "STAGED=1"
    shift
    goto parse_args
)
if /i "%1"=="-s" (
    set "STAGED=1"
    shift
    goto parse_args
)
if /i "%1"=="--branch" (
    set "BRANCH=%2"
    shift
    shift
    goto parse_args
)
if /i "%1"=="-b" (
    set "BRANCH=%2"
    shift
    shift
    goto parse_args
)
echo Unknown option: %1
echo Usage: %0 [--staged] [--branch branch-name]
exit /b 1

:check_claude
echo.
echo [96m🤖 Claude Code Review - Local[0m
echo [96m================================[0m
echo.

REM Check if Claude CLI is installed
where claude >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [91m❌ Claude CLI not found![0m
    echo.
    echo [93mInstall it with:[0m
    echo   npm install -g @anthropics/claude-code
    echo.
    echo [93mOr download from: https://docs.claude.com/en/docs/claude-code/installation[0m
    exit /b 1
)

REM Determine what to review
if "%STAGED%"=="1" (
    echo [92m📝 Reviewing staged changes...[0m
    set "DIFF_CMD=git diff --cached"
) else if not "%BRANCH%"=="" (
    echo [92m📝 Reviewing changes in branch: %BRANCH%[0m
    set "DIFF_CMD=git diff main..%BRANCH%"
) else (
    echo [92m📝 Reviewing uncommitted changes...[0m
    set "DIFF_CMD=git diff HEAD"
)

REM Get the diff and save to temp file
set "TEMP_DIFF=%TEMP%\claude_review_diff.txt"
set "TEMP_PROMPT=%TEMP%\claude_review_prompt.txt"

%DIFF_CMD% > "%TEMP_DIFF%"

REM Check if there are changes
for %%A in ("%TEMP_DIFF%") do set "FILE_SIZE=%%~zA"
if "%FILE_SIZE%"=="0" (
    echo [92m✅ No changes to review![0m
    del "%TEMP_DIFF%" 2>nul
    exit /b 0
)

echo.
echo [96mRunning Claude review...[0m
echo.

REM Create the review prompt
(
echo Review the following code changes focusing on:
echo.
echo **Critical Issues:**
echo - Security vulnerabilities and data integrity issues
echo - Bugs that will cause runtime failures
echo - Missing error handling for production deployment
echo - Configuration issues that break first launch
echo.
echo **Code Quality:**
echo - YAGNI violations ^(unnecessary complexity^)
echo - DRY violations ^(code duplication^)
echo - KISS violations ^(overcomplicated solutions^)
echo - Inconsistencies between models and migrations
echo.
echo **Project Context:**
echo - Python/FastAPI Instagram messaging automation
echo - MVP in active development - NO test coverage required yet
echo - Prefer minimal, working code over comprehensive edge cases
echo - Focus on deployment readiness and clear error messages
echo.
echo **Review Style:**
echo - Skip praise - go straight to issues
echo - Be clear, concise, and constructive
echo - Flag only what truly matters for production
echo.
echo Here are the changes:
echo.
echo ```diff
type "%TEMP_DIFF%"
echo ```
) > "%TEMP_PROMPT%"

REM Run Claude review
type "%TEMP_PROMPT%" | claude --print --model sonnet --allowed-tools "Bash(git:*)"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [91m❌ Claude review failed![0m
    del "%TEMP_DIFF%" "%TEMP_PROMPT%" 2>nul
    exit /b 1
)

echo.
echo [96m================================[0m
echo [92m✅ Review complete![0m

REM Cleanup
del "%TEMP_DIFF%" "%TEMP_PROMPT%" 2>nul

endlocal
