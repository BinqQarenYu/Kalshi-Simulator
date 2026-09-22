# 🏛️ PROJECT APEX PERPETUAL — Continuous Autonomous Evolution Charter

## 1. Prime Mission
Transform the `perpetualtrading` branch into an institutional-grade, TradingView + Hyperliquid-caliber perpetual trading platform through continuous 30-minute autonomous evolution cycles by the **Deer Family** (Lead Deer & Deer Architect).

## 2. Benchmark Gold Standards
1. **Frontend Benchmark (TradingView & Hyperliquid WebCLOB)**:
   - Institutional dark WebCLOB palette (`#0c0f12`, `slate-950`, emerald/crimson/amber).
   - Glanceable telemetry with mandatory `font-mono tabular-nums` (zero tick jitter).
   - High-precision order ticket: Market/Limit/Stop/TP, dynamic leverage slider (1x–50x), real-time liquidation distance indicator.
   - Interactive candlestick chart with multi-timeframe candles, dynamic volume, crosshairs, and position markers.
   - Responsive multi-pane layout (Chart, Orderbook Depth, Order Ticket, Positions Matrix, Bot Panel).

2. **Backend Benchmark (Institutional Quant Microstructure)**:
   - 100% strict `Decimal` financial arithmetic (zero IEEE-754 float drift).
   - Isolated margin math, leverage ratios, and bankruptcy liquidation engines.
   - Dynamic 8-hour TWAP funding rate accrual and settlement mechanism.
   - Multi-asset perpetual contract support: BTC-PERP, ETH-PERP, SOL-PERP, DOGE-PERP.

## 3. Strict Boundary & Quarantine Invariant
The Deer Family operates **STRICTLY** within the perpetual vertical:
- **Permitted**: `src/kalshi_sim/perpetuals/**`, `src/kalshi_sim/routers/perpetuals.py`, `frontend/src/components/perpetual/**`, `frontend/src/context/PerpetualTradingContext.tsx`, `tests/test_perpetuals*.py`.
- **Sacred Binary Core Forbidden**: Zero modifications to binary options bots (`domination_bot`, `macro_trend`), binary servers, or settlement engines.

## 4. The 5 Maturity Horizons
- [ ] **Horizon 1: Mathematical Decimal Armor** (Eliminate all float casts & divisions in perpetual router).
- [ ] **Horizon 2: TradingView Chart Parity** (Multi-timeframe, crosshair telemetry, volume profile, liquidation lines).
- [ ] **Horizon 3: Advanced Order Suite** (Stop-Market, Take-Profit, Trailing Stops, isolated margin validation).
- [ ] **Horizon 4: Real-Time Funding & Liquidation Engine** (8-hour funding countdown, maintenance margin brackets).
- [ ] **Horizon 5: Multi-Asset Perpetual Autonomous Bots** (Trend-following & mean-reversion perpetual strategies).

## 5. Kaizen Loop Governance
- **Cadence**: Exactly 30 minutes (1,800 seconds) between alternating shifts.
- **Verification Gate (ASVL)**: 100% pass on pytest perpetual suite + zero TypeScript compiler errors before any step is finalized.
- **Journal**: All progress logged in `docs/audits/PERPETUAL_KAIZEN_JOURNAL.md`.
