---
trigger: always_on
glob: "**/*"
description: Branch Freeze Protocol for focus_on_gold_onnx_bot — strictly lock all components not related to ONNX 3 / Brain 3 / Gold ONNX Bot.
---

# 5. Branch Freeze Protocol: Focus on ONNX 3 / Brain 3 / Gold ONNX Bot

## 1. Absolute Scope Freeze & Component Lock
On this branch (`focus_on_gold_onnx_bot`), **ALL subsystems, UI/UX panels, and bot engines NOT directly related to ONNX 3 / Brain 3 / Gold ONNX Bot are STRICTLY FROZEN and LOCKED**.
- **No agent or assistant may edit, refactor, reorganize, or tamper with frozen modules.**
- Any proposed diff touching a frozen module must be rejected immediately.

## 2. Frozen & Locked Modules (FORBIDDEN TO EDIT)
The following components are read-only and locked against any modifications:
1. **Mother Dash & General UI/UX**:
   - `frontend/src/components/ParentHub.tsx` (general layout, Bot 1/2 sections, account tabs)
   - `frontend/src/components/EngineRoomMatrix.tsx`
   - `frontend/src/components/ArbitrageRadarView.tsx`
   - `frontend/src/components/TradeTape.tsx`
   - `frontend/src/components/AIMicrostructureCard.tsx`
   - `frontend/src/components/Header.tsx`, `Sidebar.tsx`, `LiveTickerBanner.tsx`, `App.tsx`
2. **Bot 1 & Bot 2 Engines**:
   - `src/kalshi_sim/ml/domination_bot.py` / `standalone_bot.py` (Bot 1)
   - `src/kalshi_sim/ml/continuous_trainer.py` (Bot 1/2 trainer)
   - `src/kalshi_sim/standalone_onnx.py` (Bot 2)
3. **Cross-Exchange & Ancillary Infrastructure**:
   - `src/kalshi_sim/arbitrage_scanner.py`
   - `src/kalshi_sim/atomic_router.py`
   - `src/kalshi_sim/polymarket_client.py`
   - `src/kalshi_sim/clock_sync.py`
   - `src/kalshi_sim/server.py` (Port 8000 server endpoints for Bot 1/2)

## 3. Active & Permitted Scope (ONNX 3 / Brain 3 / Gold ONNX ONLY)
Work on this branch is strictly confined to the following active files:
1. **Bot 3 / Gold ONNX Decision Engines**:
   - `src/kalshi_sim/ml/macro_trend_dominion_bot.py`
   - `src/kalshi_sim/ml/gold_onnx_bot.py`
   - `src/kalshi_sim/ml/gold_inversion_bot.py`
   - `src/kalshi_sim/ml/quolas_core/hmm_brain.py` (Brain 3 HMM module)
2. **Gold ONNX Model, Dataset & Continuous Training**:
   - `src/kalshi_sim/ml/gold_continuous_trainer.py`
   - `src/kalshi_sim/ml/gold_dataset_builder.py`
   - `src/kalshi_sim/ml/gold_feature_extractor.py`
   - `src/kalshi_sim/ml/gold_model.py`
   - `src/kalshi_sim/ml/export_gold_onnx.py`
3. **Execution Runners & Dedicated Cockpits**:
   - `src/kalshi_sim/standalone_macro.py` (Bot 3 Standalone Runner on Port 8003)
   - `src/kalshi_sim/shadow_gold_runner.py` (Lane 2 Gold Incubator Runner)
   - `src/kalshi_sim/templates/pocket_cockpit_macro.html` (Bot 3 Mobile Cockpit)
   - The dedicated Bot 3 Triple-Brain section inside `frontend/src/components/BabyBotConsole.tsx`
4. **Dedicated Verification Test Suites**:
   - `tests/test_macro_trend_dominion.py`
   - `tests/test_gold_onnx_bot.py`
   - `tests/test_gold_trainer.py`
   - `tests/test_gold_dataset_builder.py`
   - `tests/test_gold_onnx.py`
   - `tests/test_shadow_gold_runner.py`

## 4. Verification Invariant
All changes within the permitted scope must continue to pass the ASVL verification loop:
- `py -m pytest tests/test_gold*.py tests/test_macro*.py -v`
- `py -m pytest tests/ -q` (all 495+ tests must pass with 0 regressions)
- `npm run typecheck` & `npm run build`
