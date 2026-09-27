@echo off
REM =========================================================================
REM start_perpetual_sentinel.bat — 24/7 Autonomous DeerFamily Watchman
REM Strictly Bounded to: perpetualtrading branch vertical
REM =========================================================================

echo [*] Initializing 24/7 DeerFamily Autonomous Perpetual Sentinel (30-min cadence)...
cd /d "C:\Users\Admin\OneDrive\Documents\GitHub\Kalshi-Simulator"

REM Run sentinel daemon with 30-minute cadence, clamped to IDLE priority
python scripts/self_healing/sentinel_daemon.py
pause
