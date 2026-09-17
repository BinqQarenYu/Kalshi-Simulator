@echo off
setlocal enabledelayedexpansion
title Kalshi Simulator - Web Dashboard
cd /d "%~dp0"
echo =====================================================================
echo   Launching Kalshi BTC Overhauled Web Dashboard + ONNX Engine
echo   Frontend: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo =====================================================================

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"
)
set "PYTHON_CMD=python"
python --version >nul 2>&1
if !errorlevel! neq 0 (
    py --version >nul 2>&1
    if !errorlevel! equ 0 set "PYTHON_CMD=py"
)

set PYTHONPATH=src

rem Check if frontend is built
if not exist "frontend\dist\index.html" (
    echo Building React Frontend...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

echo Starting Python FastAPI + WebSocket Server on Port 8000...
start "" http://localhost:8000
!PYTHON_CMD! -m kalshi_sim.server
pause
