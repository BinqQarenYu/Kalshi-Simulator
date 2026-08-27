@echo off
title Kalshi Simulator - Web Dashboard
cd /d "%~dp0"
echo =====================================================================
echo   Launching Kalshi BTC Overhauled Web Dashboard + ONNX Engine
echo   Frontend: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo =====================================================================

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
python -m kalshi_sim.server
pause
