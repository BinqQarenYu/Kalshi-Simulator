@echo off
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
echo ================================================================
echo   Launching Kalshi BTC Simulator (Live Demo WebSocket + ONNX)
echo ================================================================
!PYTHON_CMD! -m kalshi_sim --simulate --timeframe 15m -v
pause
