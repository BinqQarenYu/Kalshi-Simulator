# 🦌 Deer Family Nightly Goals

This file is automatically processed by `run_nightly_goals.bat` while you sleep.
Write your tasks below using standard markdown checkboxes `- [ ]`.
When the Deer Family finishes a task and verifies it via ASVL, it will check it off `- [x]`.

## Pending Tasks (Full MoE App Separation - Granular Execution)

**PHASE 1: Dual ONNX Arbitrage Bot**
- [x] 1A: Create `frontend/src/components/parenthub/DualOnnxView.tsx`. Write only the `DualOnnxViewProps` interface and export an empty `div` wrapper.
- [x] 1B: Inside `DualOnnxView.tsx`, write and inject the function to render the top KPI Summary Cards (Win Rate, Total Trades, Net P&L).
- [x] 1C: Inside `DualOnnxView.tsx`, write and inject the function to render a CSS grid showing the specific "ONNX Brain Dials" (Volatility Floor, Moat Multiplier).
- [x] 1D: Inside `DualOnnxView.tsx`, write and inject the function to render the Trade History Table, filtering `reports` specifically for this bot.

**PHASE 2: Macro Trend Dominion Bot**
- [x] 2A: Create `frontend/src/components/parenthub/MacroDominionView.tsx`. Write only the `MacroDominionViewProps` interface and export an empty wrapper.
- [x] 2B: Inside `MacroDominionView.tsx`, write and inject the function to render its KPI Summary Cards.
- [x] 2C: Inside `MacroDominionView.tsx`, write and inject the function to render its specific parameters grid (Brier Score, HMM Regime, Decile Pruning).
- [x] 2D: Inside `MacroDominionView.tsx`, write and inject the Trade History Table renderer for this bot.

**PHASE 3: Dominion V2 Bot**
- [x] 3A: Create `frontend/src/components/parenthub/DominionV2View.tsx`. Write only the `DominionV2ViewProps` interface and export an empty wrapper.
- [x] 3B: Inside `DominionV2View.tsx`, write and inject the function to render its KPI Summary Cards.
- [x] 3C: Inside `DominionV2View.tsx`, write and inject the function to render its specific V2 strategic divergence parameters grid.
- [x] 3D: Inside `DominionV2View.tsx`, write and inject the Trade History Table renderer for this bot.

**PHASE 4: Bot1 V4 Domination Engine**
- [x] 4A: Create `frontend/src/components/parenthub/V4DominationView.tsx`. Write only the `V4DominationViewProps` interface and export an empty wrapper.
- [x] 4B: Inside `V4DominationView.tsx`, write and inject the function to render its KPI Summary Cards.
- [x] 4C: Inside `V4DominationView.tsx`, write and inject the function to render its specific parameters grid (P1, P2, P3 Phase locking thresholds).
- [x] 4D: Inside `V4DominationView.tsx`, write and inject the Trade History Table renderer for this bot.

**PHASE 5: Master Routing & UI Integration (ParentHub.tsx)**
- [x] 5A: Open `frontend/src/components/ParentHub.tsx`. Modify the `PrimaryNav` type definition to include `'dual_onnx'`, `'macro_dominion'`, `'dominion_v2'`, and `'v4_domination'`.
- [x] 5B: In `ParentHub.tsx`, add the 4 `import` statements at the top for the newly created view components.
- [x] 5C: In `ParentHub.tsx`, inject the sidebar navigation button specifically for `'dual_onnx'`.
- [x] 5D: In `ParentHub.tsx`, inject the sidebar navigation button specifically for `'macro_dominion'`.
- [x] 5E: In `ParentHub.tsx`, inject the sidebar navigation buttons for `'dominion_v2'` and `'v4_domination'`.
- [x] 5F: In `ParentHub.tsx`, update the main dynamic rendering body to actually mount `<DualOnnxView />`, `<MacroDominionView />`, etc., when their tab is selected.

**PHASE 6: Backend Telemetry Isolation (server_state_payload.py)**
- [x] 6A: Audit `src/kalshi_sim/server_state_payload.py`. Ensure the `dual_telemetry` dictionary strictly reads from `state.dual_onnx_bot` and formats perfectly.
- [x] 6B: Audit `src/kalshi_sim/server_state_payload.py`. Ensure the `macro_telemetry` dictionary strictly reads from `state.macro_trend_bot` and formats perfectly.
- [x] 6C: Audit `src/kalshi_sim/server_state_payload.py`. Ensure the `dominion2_telemetry` dictionary strictly reads from `state.dominion2_bot`. Create it if it is missing.
- [x] 6D: Audit `src/kalshi_sim/server_state_payload.py`. Ensure the `v4_telemetry` dictionary strictly reads from `state.bot1_v4_engine`. Create it if it is missing.

**PHASE 7: ASVL Verification**
- [ ] 7A: Execute `npm run typecheck` in the frontend directory. If there are missing props in `ParentHub.tsx`, fix them.
- [ ] 7B: Execute `pytest tests/ -q` to verify the backend payload isolation didn't break any core structural tests.

**PHASE 8: Live Trading Master Guardrails & Execution**
- [ ] 8A: Audit `src/kalshi_sim/virtual_order_router.py`. Ensure the absolute live trading guardrails ("1-contract maximum per event", "anti-kamikaze sizing", and "circuit breakers") are globally enforced for all bots attempting live execution.
- [ ] 8B: Update `ParentHub.tsx` to insert a global Master "LIVE TRADING" badge and Kill Switch status indicator in the top navbar.
- [ ] 8C: Audit `run_live.bat` and `server.py` to ensure the production environment `.env` keys are securely loaded and `execution_mode` defaults safely.

## Completed Tasks
*(The system will move checked-off tasks here)*