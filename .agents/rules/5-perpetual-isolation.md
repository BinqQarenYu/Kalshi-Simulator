---
trigger: always_on:glob: "**/*"
description: Strict physical and code isolation boundary for perpetual trading vertical.
---

# MANDATORY PERPETUAL TRADING ISOLATION ARMOR (BRANCH: perpetualtrading)

## 1. Prime Directive
On the `perpetualtrading` branch, all feature development, quantitative modeling, bot development, and UI design are STRICTLY ISOLATED to the perpetual trading vertical.

## 2. Sacred Binary Core Protected Zone (TOUCHING STRICTLY FORBIDDEN)
Autonomous AI agents, subagents, and automated workflows are STRICTLY FORBIDDEN from editing, mutating, refactoring, or deleting any file within the sacred binary options core:
- `src/kalshi_sim/ml/domination_bot.py`
-`src/kalshi_sim/ml/macro_trend_dominion_bot.py`
-`src/kalshi_sim/ml/dual_onnx.py`
- `src/kalshi_sim/standalone_bot.py`
-`src/kalshi_sim/standalone_bot_modules/**`
- `src/kalshi_sim/live_coordinator.py`
- `src/kalshi_sim/cfbenchmarks_sync.py`
-`src/kalshi_sim/bot_deployment_auditor.py`
- `src/kalshi_sim/server_settlements.py`
-`src/kalshi_sim/server_feeds.py`
- `frontend/src/components/ClobTerminalView.tsx`
-`frontend/src/components/analytics/**`
-`data/seal_of_excellence.json`
-`data/bot_parameters_domination.json`

## 3. Authorized Sandbox Permitted Zone
All modifications, feature additions, multi-asset bots, and UI polishing MUST be strictly contained inside:
1. `src/kalshi_sim/perpetuals/**` (Perpetual engines, margin math, multi-asset bots)
2. `src/kalshi_sim/routers/perpetuals.py` (FastAPI endpoints)
3. `frontend/src/components/perpetual/**` (Perpetual terminal views, charts, tickets, bot panels)
4. `frontend/src/context/PerpetualTradingContext.tsx` (Perpetual state management)
5. `tests/test_perpetuals.py` (Dedicated perpetual verification test suite)

## 4. Blast-Radius Invariant
The perpetual engine operates purely as a **Read-Only Consumer** of spot feeds and ONNX tensors. It MUST NEVER mutate binary option state (`state.active_market`, `state.settlements`, `LiveCoordinator`).
