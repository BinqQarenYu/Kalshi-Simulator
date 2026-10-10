@echo off
title Kalshi Bot 1 V4 - Floating Desktop Widget
echo ===============================================================================
echo   Kalshi Bot 1 V4 -- Floating Desktop Widget Launcher
echo   Mode: 24/7 Autonomous Live Trading Telemetry
echo   View: Chromeless Always-on-Top Floating Windows Widget (Port 8000)
echo ===============================================================================

setlocal enabledelayedexpansion
if exist "C:\Python314\python.exe" (
    set "PYTHON_CMD=C:\Python314\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else (
    set "PYTHON_CMD=python"
)

set PYTHONPATH=src
echo [INFO] Launching Bot 1 V4 Floating Desktop Widget...
"%PYTHON_CMD%" bot1_v4_widget.py
pause
