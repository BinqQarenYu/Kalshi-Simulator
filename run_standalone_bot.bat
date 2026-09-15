@echo off
setlocal enabledelayedexpansion
title Kalshi 3-Step Dominion BTC Standalone (Port 8001)

echo =======================================================================
echo    KALSHI 3-STEP DOMINION — BITCOIN STANDALONE ENGINE (PORT 8001)
echo =======================================================================
echo.

:: 1. Safely terminate any process listening on port 8001 (leaves Mother on 8000 untouched)
echo [INFO] Checking port 8001 for existing bot instances...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host '[INFO] Terminated existing instance on port 8001 (PID:' $_.OwningProcess ')' }"

:: 2. Set PYTHONPATH
set PYTHONPATH=src

echo [INFO] Standalone multi-port engines have been consolidated into Mother Server (Port 8000).
echo [INFO] Redirecting to unified engine...
call "kalshi_Bitcoin Bot.bat"
exit /b 0

if %errorlevel% neq 0 (
    echo.
    echo =======================================================================
    echo [WARNING] Standalone Bot exited with code %errorlevel%.
    echo =======================================================================
    pause
)
