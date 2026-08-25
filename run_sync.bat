@echo off
set PYTHONPATH=src
echo ================================================================
echo   Syncing Kalshi Simulator with Google Drive
echo ================================================================
python -m kalshi_sim.gdrive_sync --all
pause
