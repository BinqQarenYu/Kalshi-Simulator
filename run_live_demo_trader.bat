@echo off
title Kalshi Simulator - Live Demo Paper Trading
cd /d "%~dp0"
echo =====================================================================
echo   Starting Kalshi Demo Paper Trading Bot (Live Demo Orders + ONNX)
echo   Connecting to Kalshi Demo: https://external-api.demo.kalshi.co
echo =====================================================================
setlocal enabledelayedexpansion
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
!PYTHON_CMD! -m kalshi_sim --live-demo --timeframe 15m -v
pause
