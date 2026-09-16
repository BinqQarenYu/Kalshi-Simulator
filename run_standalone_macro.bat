@echo off
setlocal enabledelayedexpansion
title Kalshi Macro Trend Dominion Standalone (Port 8003)

echo =======================================================================
echo    KALSHI MACRO TREND DOMINION — AUTONOMOUS STANDALONE ENGINE (PORT 8003)
echo =======================================================================
echo.

:: 1. Prioritize Python 3.12 in PATH before WindowsApps stub
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"
)

set "PYTHON_CMD=python"
python --version >nul 2>&1
if !errorlevel! neq 0 (
    py --version >nul 2>&1
    if !errorlevel! equ 0 set "PYTHON_CMD=py"
)

:: 2. Safely terminate any process listening on port 8003 (leaves 8000, 8001, 8002 untouched)
echo [INFO] Checking port 8003 for existing bot instances...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8003 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host '[INFO] Terminated existing instance on port 8003 (PID:' $_.OwningProcess ')' }"

:: 3. Set PYTHONPATH
set PYTHONPATH=src

:: 4. Launch Standalone Macro Engine on Port 8003 in Lane 2 Incubator (Paper Mode)
echo [INFO] Starting Standalone Macro Trend Dominion Bot on port 8003...
echo [INFO] Macro Pocket Cockpit will open automatically at http://localhost:8003
echo [INFO] Note: Mother Dashboard (8000), 3-Step Bot (8001), ONNX Bot (8002) remain untouched.
echo.
!PYTHON_CMD! -u -m kalshi_sim.standalone_macro --port 8003 --paper

if %errorlevel% neq 0 (
    echo.
    echo =======================================================================
    echo [WARNING] Standalone Macro Bot exited with code %errorlevel%.
    echo =======================================================================
    pause
)
