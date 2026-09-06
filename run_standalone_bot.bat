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

:: 3. Launch Standalone Engine on Port 8001
echo [INFO] Starting Standalone 3-Step Domination Bot on port 8001...
echo [INFO] Pocket Cockpit will open automatically at http://localhost:8001
echo [INFO] Note: Mother Dashboard remains on http://localhost:8000
echo.
python -u -m kalshi_sim.standalone_bot --port 8001 --live

if %errorlevel% neq 0 (
    echo.
    echo =======================================================================
    echo [WARNING] Standalone Bot exited with code %errorlevel%.
    echo =======================================================================
    pause
)
