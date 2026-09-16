@echo off
setlocal enabledelayedexpansion
title Kalshi Simulator - Unattended Laptop Mode Setup

echo ===============================================================================
echo   CONFIGURING LAPTOP FOR UNATTENDED 24/7 OPERATION
echo   Sleep Prevention ^| Network Persistence ^| Process Armor
echo ===============================================================================
echo.

:: Check for Administrative privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Administrative permissions required for network adapter and throttling policies.
    echo [INFO] Requesting Administrator elevation (click 'Yes' on the UAC prompt)...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd.exe -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:: Run the PowerShell configuration script
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\configure_laptop_night_mode.ps1"

echo.
echo Setup completed. Press any key to exit...
pause >nul
