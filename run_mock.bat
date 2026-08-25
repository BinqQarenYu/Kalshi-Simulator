@echo off
set PYTHONPATH=src
echo ================================================================
echo   Launching Kalshi BTC Simulator (Mock Mode + ONNX AI Engine)
echo ================================================================
python -m kalshi_sim --simulate --mock -v
pause
