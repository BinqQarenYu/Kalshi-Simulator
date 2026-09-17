# WF-004: Multi-Bot Coordination & Anti-Cannibalism Shield

> **Workflow ID:** WF-004  
> **Classification:** Concurrency Arbitration & CFTC Section 4c Compliance  
> **Frequency:** Continuous (Real-time active loop on Port 8000)  
> **Prerequisites:** Monolithic LiveCoordinator lock, unified Mother Server.

---

## 1. Overview & Objective

When multiple autonomous bots (Bot 1: 3_step_domination_bot, Bot 2: dual_onnx, Bot 3: macro_trend_dominion) operate simultaneously on the same portfolio, coordination guards are required to prevent:
1. **Directional Cannibalism**: Bot A buying YES while Bot B buys NO on the same 15M cycle.
2. **Negative-Arbitrage Loss Trap**: Holding opposing binary positions (e.g. paying 52c YES + 52c NO = .04 total cost for a guaranteed .00 payout, locking in a -.04 loss).
3. **CFTC Wash-Trading Liability**: Matching opposing orders on the same account under CFTC Section 4c(a)(1).

---

## 2. Coordination Architecture

All autonomous strategies route order intentions through the synchronized LiveCoordinator singleton (src/kalshi_sim/live_coordinator.py).

---

## 3. Operational Rules & Invariants

1. **Monolithic Port 8000 Binding**:
   - All multi-bot arbitration runs strictly inside the Port 8000 Mother Server (server.py).
   - Standalone multi-port servers (8001, 8002, 8003) and .bat subprocess wrappers are permanently retired.
2. **Synchronous Intent Lock**:
   - The intent lock is reserved before awaiting any async network I/O. If two bots signal within the same millisecond, FIFO sequence ordering determines authorization.
3. **Micro-Bankroll Sizing Cap**:
   - Sizing is hard-capped at 1 contract per asset (BTC, ETH, SOL, DOGE) across all bots.
4. **1-Trade-Per-Cycle Rule**:
   - Once a bot submits an order for the active 15M cycle, no further additions or modifications are allowed for that contract.

---

## 4. Verification & Health Monitoring

To verify coordination integrity:
`ash
python -m pytest tests/test_live_coordinator.py -v
`

Monitor live arbitration state:
- Live telemetry endpoint: GET http://localhost:8000/api/coordinator/state
- Active cycle lock file: data/active_cycle_coordination.json
