@echo off
setlocal enabledelayedexpansion
title Kalshi BTC Institutional Trading Simulator

cd /d "%~dp0"

echo ===============================================================================
echo   KALSHI BTC QUANTITATIVE TRADING SIMULATOR
echo   Multi-Timeframe Microstructure ONNX Engine ^| WebCLOB Dashboard
echo ===============================================================================
echo.

rem Check for Python installation and prioritize Python 3.12
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"
)

set "PYTHON_CMD=python"
python --version >nul 2>&1
if !errorlevel! neq 0 (
    py --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py"
    ) else (
        echo [ERROR] Python is not found in PATH. Please install Python 3.10+ and add it to PATH.
        pause
        exit /b 1
    )
)

set PYTHONPATH=src

rem Check if ONNX model exists
if not exist "models\nano_microscope_overhauled.onnx" (
    echo [WARNING] ONNX model 'models\nano_microscope_overhauled.onnx' not found.
    echo Attempting to pull model from Google Drive via rclone...
    !PYTHON_CMD! -m kalshi_sim.gdrive_sync --pull-models
)

rem Check if React frontend is built
if not exist "frontend\dist\index.html" (
    echo [INFO] Frontend build not found. Building React dashboard...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

echo [INFO] Starting FastAPI + WebSocket Trading Server at http://localhost:8000 ...
echo [INFO] API Swagger Documentation available at http://localhost:8000/docs
echo.

rem Launch browser after a brief pause
start "" http://localhost:8000

!PYTHON_CMD! -m kalshi_sim.server
pause
