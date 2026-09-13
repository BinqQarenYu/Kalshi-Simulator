# Institutional Archive Ledger — 2026-09-11 (ET)
*Audited & Compiled by Agent QuoQuo (Repository Archivist & Institutional Librarian)*

---

## 1. Fleet Operational Status & Process Authority

| Port | Strategy Name | Mode | Status | Active Lock | Target Assets / Basket |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **8001** | `ThreeStepDominationBot` (Bot 1) | **LIVE REAL MONEY** | **ARMED** | `trading_engine.lock` | Multi-Asset Basket (`BTC`, `GOLD`, `DOGE`) |
| **8002** | `OnnxExecutionStrategy` (Bot 2) | **SHADOW / INCUBATOR** | ONLINE | `trading_engine_onnx.lock` | Dual-ONNX L2/Microstructure Model |
| **8003** | `MacroExecutionStrategy` (Bot 3) | **SHADOW / PAPER** | ONLINE | `trading_engine_macro.lock` | Macro Trend 52¢ Order Flow Model |
| **8000** | Mother Server / Telemetry CLOB | **READ-ONLY TELEMETRY** | ONLINE | None (Simulation Only) | Global Multi-Feed Monitor & Engine Room |

> **Process Authority Check**: PASS. Only Port 8001 holds the live execution token. Port 8000 is isolated in read-only telemetry mode.

---

## 2. Quantitative Architecture & Parameter Census

### Active Parameter File: `data/bot_parameters_domination.json`
- **Sizing Armor**: Strictly capped at **1 contract per trade** for micro-bankroll preservation.
- **Entry Timing Envelopes (Option C Calibration)**:
  - `BTC`: $12.0\text{ min} \to 4.5\text{ min}$ remaining
  - `GOLD`: $7.0\text{ min} \to 2.0\text{ min}$ remaining
  - `DOGE`: $8.0\text{ min} \to 3.0\text{ min}$ remaining
- **Maker Pricing Depth**: $\$0.48$ target resting price (Maker limit order yielding $\$0.00$ Kalshi taker fee).
- **Dead-Zone Filtering**: Spot price drift $< \text{Threshold}$ strictly vetoed against Brownian noise coin-flip traps.

---

## 3. Daily Codebase Milestones Completed

1. **Option C Calibrated Entry Timing**:
   - Enforced asset-specific expiration countdown windows in [`three_step_domination.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/strategies/three_step_domination.py) and verified across live tick loops.
2. **Engine Room Telemetry Matrix**:
   - Added the visual 3-brain engine parameter matrix to the UI Cockpit ([`standalone_pocket_cockpit.html`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/standalone_pocket_cockpit.html)), providing transparent parameter state, input/output flow, and weakness/strength profiles.
3. **Live Fleet Arming**:
   - Resumed and confirmed live armed trading for Bot 1 on port 8001. Verified balance sync and zero-conflict multi-asset order routing.
4. **Agent QuoQuo Formalization**:
   - Formalized QuoQuo as the read-only institutional archivist, librarian, and ground-truth oracle.
   - Enshrined [`.agents/skills/agent-quoquo/SKILL.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/.agents/skills/agent-quoquo/SKILL.md).
   - Configured once-a-day EOD census and daily ledger archiving.

---

## 4. Invariant Compliance Audit (Shelf 1 & Shelf 3)

- **Strict Decimal Financial Math**: 100% PASS across models, pricing, and balances.
- **Micro-Bankroll Sizing Armor**: 100% PASS (1 contract maximum).
- **Anti-Wash Trading & Self-Crossing Shield**: 100% PASS via `LiveCoordinator`.
- **In-Flight Intent Locks**: 100% PASS (synchronous pre-reservation before async network I/O).

---

## 5. Shelf 4 Graveyard & Cleanup Radar

- **Superseded Config**: `data/bot_parameters.json` (single-asset) is deprecated in favor of `data/bot_parameters_domination.json`.
- **Scratch Inspection Scripts**: The following temporary scripts in `scratch/` have fulfilled their purpose and are designated for archival/clean-up:
  - `scratch/check_kxgold.py`
  - `scratch/check_pyth_gold.py`
  - `scratch/check_kxgold_fields.py`
  - `scratch/check_kalshi_markets.py`
  - `scratch/analyze_trades.py`
