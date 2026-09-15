@echo off
setlocal enabledelayedexpansion
title Kalshi Macro Trend Dominion Standalone (Port 8003)

echo =======================================================================
echo    KALSHI MACRO TREND DOMINION — AUTONOMOUS STANDALONE ENGINE (PORT 8003)
echo =======================================================================
echo.

:: 1. Safely terminate any process listening on port 8003 (leaves 8000, 8001, 8002 untouched)
echo [INFO] Checking port 8003 for existing bot instances...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8003 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host '[INFO] Terminated existing instance on port 8003 (PID:' $_.OwningProcess ')' }"

:: 2. Set PYTHONPATH
set PYTHONPATH=src

echo [INFO] Standalone multi-port engines have been consolidated into Mother Server (Port 8000).
echo [INFO] Redirecting to unified engine...
call "kalshi_Bitcoin Bot.bat"
exit /b 0

if %errorlevel% neq 0 (
    echo.
    echo =======================================================================
    echo [WARNING] Standalone Macro Bot exited with code %errorlevel%.
    echo =======================================================================
    pause
)
