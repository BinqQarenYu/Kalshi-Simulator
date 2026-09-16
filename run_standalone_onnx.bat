@echo off
setlocal enabledelayedexpansion
title Kalshi Dual-Brain ONNX Standalone (Port 8002)

echo =======================================================================
echo    KALSHI DUAL-BRAIN ONNX — AUTONOMOUS STANDALONE ENGINE (PORT 8002)
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

:: 2. Safely terminate any process listening on port 8002 (leaves Mother 8000 and Dominion 8001 untouched)
echo [INFO] Checking port 8002 for existing bot instances...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8002 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host '[INFO] Terminated existing instance on port 8002 (PID:' $_.OwningProcess ')' }"

:: 3. Set PYTHONPATH
set PYTHONPATH=src

echo [INFO] Standalone multi-port engines have been consolidated into Mother Server (Port 8000).
echo [INFO] Redirecting to unified engine...
call "kalshi_Bitcoin Bot.bat"
exit /b 0

if %errorlevel% neq 0 (
    echo.
    echo =======================================================================
    echo [WARNING] Standalone ONNX Bot exited with code %errorlevel%.
    echo =======================================================================
    pause
)
