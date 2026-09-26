@echo off
title Deer Family - Nightly Goal Runner (Dual-Engine)
echo =========================================================================
echo Activating Deer Family Autonomous Goal Runner
echo Primary Brain: Google Gemini Free Tier
echo Fallback Brain: Local Ollama (localhost:11434)
echo =========================================================================
echo.
echo Please ensure your tasks are listed in docs\audits\NIGHTLY_GOALS.md
echo.

python -u scripts\self_healing\nightly_goal_runner.py
pause
