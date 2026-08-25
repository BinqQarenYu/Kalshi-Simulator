@echo off
title Kalshi Simulator - Live Demo Paper Trading
cd /d "%~dp0"
echo =====================================================================
echo   Starting Kalshi Demo Paper Trading Bot (Live Demo Orders + ONNX)
echo   Connecting to Kalshi Demo: https://external-api.demo.kalshi.co
echo =====================================================================
set PYTHONPATH=src
python -m kalshi_sim --live-demo --timeframe 15m -v
pause
