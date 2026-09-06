@echo off
setlocal enabledelayedexpansion
title Kalshi BTC Autonomous Trading Terminal (Standalone)

cd /d "%~dp0"

echo ===============================================================================
echo   KALSHI BITCOIN TRADING TERMINAL ^| AUTONOMOUS QUANTITATIVE BOT
echo   Standalone Execution Engine ^| Multi-Timeframe Microstructure ONNX CLOB
echo ===============================================================================
echo.

rem 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.11+ is not found in your PATH.
    echo Please install Python and ensure "Add Python to PATH" is checked.
    echo.
    pause
    exit /b 1
)

rem 2. Set PYTHONPATH to src
set PYTHONPATH=src

rem 3. Check for ONNX AI Model
if not exist "models\nano_microscope_overhauled.onnx" (
    echo [WARNING] ONNX model 'models\nano_microscope_overhauled.onnx' missing.
    echo Attempting model synchronization...
    python -m kalshi_sim.gdrive_sync --pull-models
)

rem 4. Check Frontend Build Distribution
if not exist "frontend\dist\index.html" (
    echo [INFO] Frontend production build not found. Building React dashboard...
    cd frontend
    call npm install
    call npm run build
    cd /d "%~dp0"
)

rem 5. Check if port 8000 is already in use
set OLD_PID=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    set OLD_PID=%%a
)

if defined OLD_PID (
    echo [NOTICE] An existing server is already running on port 8000 (PID !OLD_PID!).
    echo [INFO] Opening dashboard in your default browser at http://localhost:8000 ...
    start "" http://localhost:8000
    echo.
    echo Options:
    echo   [Enter] Keep existing background server running
    echo   [R]     Restart: Stop previous server and start a fresh terminal instance
    echo.
    set /p USER_CHOICE="Select option (Enter/R): "
    if /i "!USER_CHOICE!"=="R" (
        echo Stopping PID !OLD_PID!...
        taskkill /F /PID !OLD_PID! >nul 2>&1
        timeout /t 2 /nobreak >nul
        goto start_server
    )
    goto finish
)

:start_server
echo [INFO] Starting FastAPI + WebSocket Trading Server at http://localhost:8000 ...
echo [INFO] WebCLOB Dashboard: http://localhost:8000
echo [INFO] API Documentation: http://localhost:8000/docs
echo.
rem Launch default browser
start "" http://localhost:8000

rem Start Python server with unbuffered console output
python -u -m kalshi_sim.server

:finish
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Server process exited with code %errorlevel%.
    pause
)
