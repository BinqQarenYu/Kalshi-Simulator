@echo off
title Kalshi 3-Step Dominion - Floating Desktop Widget
echo ===============================================================================
echo   Kalshi 3-Step Dominion -- Floating Desktop Widget Launcher
echo   Mode: 24/7 Autonomous Live Trading
echo   View: Chromeless Always-on-Top Floating Windows Widget (Port 8001)
echo ===============================================================================

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
!PYTHON_CMD! -m kalshi_sim.standalone_bot --port 8001 --live --force --widget
pause
