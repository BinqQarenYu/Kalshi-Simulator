@echo off
set PYTHONPATH=src
echo ================================================================
echo   Launching Kalshi BTC Simulator (Live Demo WebSocket + ONNX)
echo ================================================================
python -m kalshi_sim --simulate --timeframe 15m -v
pause
