@echo off
title Kalshi 3-Step Dominion - Floating Desktop Widget
echo ===============================================================================
echo   Kalshi 3-Step Dominion -- Floating Desktop Widget Launcher
echo   Mode: 24/7 Autonomous Live Trading
echo   View: Chromeless Always-on-Top Floating Windows Widget (Port 8001)
echo ===============================================================================

set PYTHONPATH=src
python -m kalshi_sim.standalone_bot --port 8001 --live --force --widget
pause
