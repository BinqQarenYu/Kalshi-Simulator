# 24/7 Standalone Baby Bot & Pocket Cockpit Runbook

This runbook is the definitive operational manual for the **Kalshi 3-Step Dominion Standalone Engine** (`src/kalshi_sim/standalone_bot.py`) and its ultra-lean **Pocket Cockpit Web UI** running on port `8001`.

---

## 1. Executive Summary & Design Rationale

In high-frequency binary option trading on Kalshi, running live capital inside an all-in-one development terminal creates severe architectural risks:
- Memory leaks from live chart renderers and WebCLOB depth ladders.
- Event-loop starvation caused by large historical backtests or machine learning re-training routines.
- Accidental routing of test/mock orders to live exchange endpoints.

To guarantee institutional execution integrity, the platform implements the **Two-Tier Architecture**:
1. **Mother Server (Port 8000)**: Serves as the "Strategy Factory / Lab" where new algorithms are cooked, backtested, and paper-traded.
2. **Standalone Baby Bot (Port 8001)**: An isolated, lightweight Python execution daemon dedicated 100% to live capital execution with zero chart rendering overhead and zero paper trading interference.

---

## 2. Hard Invariants & Quantitative Safeguards

The Standalone Engine enforces strict mathematical and operational invariants that cannot be bypassed:

| Rule / Invariant | Hard Limit | Enforcement Mechanism |
| :--- | :--- | :--- |
| **Max Contracts / Trade** | **Strictly 1 Contract** | `AgentGuardrails.validate_pre_trade_intent()` hard caps order size to 1. |
| **Max Exposure / Cycle** | **Strictly 2 Contracts** | Total contracts bought in a 15-minute event cannot exceed 2 ($0.96 max risk). |
| **Maker Price Ceiling** | **$0.48** | Resting limit orders are placed at $0.48 or lower to guarantee **$0.00 maker fees**. |
| **Sole Live Bot** | **3-Step Dominion Only** | Only `ThreeStepDominationBot` is authorized to place live orders. All other bots are locked out. |
| **Loss Streak Breaker** | **3 Consecutive Losses** | Automatic engine disarm to STANDBY after 3 losses in a session. Orders cancelled. |
| **Anti-Burst Mutex** | **1 Evaluation at a Time** | `asyncio.Lock()` ensures sequential market evaluation. |
| **Pre-Flight Lock** | **Synchronous Intent Tag** | `_in_flight_locks` reserves capacity before network I/O, preventing double-fills. |
| **Pre-Expiry Dead Zone** | **$T_{\text{rem}} \le 45\text{s}$** | Zero new orders submitted within 45 seconds of expiration. |
| **Post-Expiry Cooldown** | **$T_{\text{rem}} \ge 855\text{s}$** | 45-second buffer after cycle open allows L2 order book spreads to settle. |
| **Order Sweeper** | **30s Periodic Check** | Automated watchdog cancels lingering resting orders from expired events. |
| **Process Lock** | **1 Live Process** | `data/trading_engine.lock` prevents concurrent port 8000 and 8001 live trading. |
| **Financial Math** | **`decimal.Decimal`** | Absolute prohibition of IEEE 754 floating-point arithmetic. |

---

## 3. Pocket Cockpit UI Guide

The Pocket Cockpit is accessible at **`http://localhost:8001`**. It supports two distinct visual modes:

### Mode A: Minimized Mode (Compact Desktop Cockpit)
Designed for distraction-free 24/7 monitoring in a tiny desktop window (~500px × 220px):
1. **Top Header**:
   - `⚡ 3-STEP DOMINION (24/7 Standalone Engine)`
   - View mode toggle button: `[⤢ Expand]`
   - Live status pill: `[ARMED / LIVE]` (green) vs `[STANDBY / SAFE]` (muted)
2. **Multi-Asset Switcher Bar**:
   - Instant 1-click switching between `[₿ BTC]`, `[Ξ ETH]`, `[● SOL]`, and `[Ð DOGE]`.
   - Active asset is highlighted with dark elevated styling and asset-specific ticker branding.
3. **Master Execution Controls**:
   - `[● ARMED / EXECUTE LIVE ORDERS]`: Arms engine to place authenticated live orders.
   - `[○ DISARMED / STANDBY / SAFE MODE]`: Disarms engine into observation mode without killing the server.
   - `[🔴 EMERGENCY PANIC: CANCEL ALL ORDERS & STOP]`: Disarms engine and sends bulk cancel requests to Kalshi API.
4. **Collapsible Drawer Toggle**:
   - Sleek subtle handle `[▾ Show Institutional Telemetry & Parameters]` at the bottom.

### Mode B: Expanded Institutional Mode
Clicking `[⤢ Expand]` or the drawer handle reveals the full quantitative dashboard:
1. **Primary KPI Cards**:
   - **Kalshi Live Balance**: Total portfolio cash balance and Shard 2 sub-allocation.
   - **Today's Realized PnL**: Total realized profit/loss, settled cycle count, win/loss record, and win rate %.
   - **Target Strike (TO BEAT)**: Target expiration price $K$ and target expiration timestamp (ET).
   - **Spot Index (NOW)**: CME CF Benchmarks 5Hz spot index price $S_t$ and moneyness diff ($S_t - K$).
   - **Active Countdown**: Real-time sub-second countdown timer to event boundary (:00, :15, :30, :45 ET).
2. **Strategy Parameters & Guardrails Panel**:
   - Interactive inputs to modify Discount Limit Price, Min Edge %, Min Net EV, Min Spot Distance, and VPIN threshold.
   - `[💾 Apply & Save]`: Instantly validates and commits new parameters to the running engine.
   - `[🧹 Sweep Expired Event Orders]`: Manually triggers resting order garbage collection.
3. **Microstructure Telemetry Panel**:
   - Active position status (`FLAT`, `MAKER RESTING`, or `IN CYCLE TRADE`).
   - Kalshi Inside Touch quotes (Best YES Bid/Ask and Best NO Bid/Ask).
   - Statistical Edge % and Net Expected Value ($/contract).
   - Real-time VPIN toxicity score and adverse selection safety flag.
   - Active Playbook indicator (`EARLY_MOMENTUM`, `MID_DRIFT`, `LATE_GAMMA`, or `NONE`).
4. **Today's Settled Cycles Mini-Journal**:
   - Audit trail of recent 15-minute event outcomes, contracts traded, and dollar PnL.
5. **Live Execution Log**:
   - Real-time event tape displaying state transitions, order placements, fills, and guardrail blocks.
6. **Health Badges**:
   - WebSocket connection status, BRTI index sync, Guardrail invariant checks, and Windows Away Mode.

---

## 4. REST API Reference (Port 8001)

| Method | Endpoint | Description | Sample Request / Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Serves the Pocket Cockpit HTML UI. | HTML content |
| `GET` | `/api/state` | Real-time state payload (balance, PnL, spot, strike, countdown, telemetry). | See schema below |
| `GET` | `/api/assets` | Supported crypto assets and live CF Benchmarks prices. | `{"assets": [...], "active_asset": "BTC"}` |
| `POST` | `/api/assets/select` | Switches the active trading asset. | `{"asset": "ETH"}` |
| `POST` | `/api/bot/arm` | Arms the bot for live order placement and resets loss streak. | `{"status": "ARMED", "armed": true}` |
| `POST` | `/api/bot/disarm` | Disarms bot into safe standby mode. | `{"status": "DISARMED", "armed": false}` |
| `POST` | `/api/bot/panic` | Emergency halt: disarms bot and cancels all resting orders on Kalshi. | `{"status": "PANIC_EXECUTED", "cancelled_orders": 2}` |
| `GET` | `/api/bot/parameters` | Returns active strategy parameters and risk thresholds. | `{"discount_limit_price": 0.48, ...}` |
| `POST` | `/api/bot/parameters` | Dynamically updates parameters and guardrail thresholds. | `{"min_edge_pct": 6.5, "min_ev_dollars": 0.03}` |
| `POST` | `/api/bot/sweep-orders` | Manually sweeps resting orders for finished events. | `{"status": "SWEEP_COMPLETE", "cancelled_orders": 1}` |

---

## 5. Multi-Asset Configuration & Constraints

When switching assets via the UI or API, the engine automatically adjusts market discovery tickers and strike distance filters:

```python
ASSET_SPECS = {
    "BTC": {
        "series_15m": "KXBTC15M",
        "series_5m": "KXBTC5M",
        "cf_index_id": "BRTI",
        "strike_step": 25.0,
        "min_spot_diff": 35.0,  # $35.00 distance avoids coin-flip chop
        "price_decimals": 2,
    },
    "ETH": {
        "series_15m": "KXETH15M",
        "series_5m": "KXETH5M",
        "cf_index_id": "ETHUSD_RTI",
        "strike_step": 2.50,
        "min_spot_diff": 2.50,
        "price_decimals": 2,
    },
    "SOL": {
        "series_15m": "KXSOL15M",
        "series_5m": "KXSOL5M",
        "cf_index_id": "SOLUSD_RTI",
        "strike_step": 0.50,
        "min_spot_diff": 0.50,
        "price_decimals": 2,
    },
    "DOGE": {
        "series_15m": "KXDOGE15M",
        "series_5m": "KXDOGE5M",
        "cf_index_id": "DOGEUSD_RTI",
        "strike_step": 0.001,
        "min_spot_diff": 0.0005,
        "price_decimals": 4,
    },
}
```

---

## 6. Windows 24/7 Power Management & Daemon Resilience

To prevent Windows from sleeping or suspending network threads when running unattended:
1. **Windows Away Mode**:
   ```python
   # Calls Win32 kernel32.SetThreadExecutionState
   ES_CONTINUOUS = 0x80000000
   ES_SYSTEM_REQUIRED = 0x00000001
   ES_AWAYMODE_REQUIRED = 0x00000040
   ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
   ```
2. **Crash Recovery & Heartbeat**:
   - The engine automatically reconnects to Kalshi WebSocket and CF Benchmarks feeds with exponential backoff if disconnected.
   - Periodic watchdogs reconcile portfolio balances, settlements, and resting orders every 15–30 seconds.

---

## 7. Operational Checklist & Incident Response

### Daily Pre-Trading Checklist
1. Verify Kalshi balance on `http://localhost:8001`.
2. Confirm active asset (`BTC`, `ETH`, `SOL`, or `DOGE`).
3. Ensure the countdown timer matches the official Kalshi web clock.
4. Verify BRTI spot price and target strike show realistic moneyness diff.
5. Click `[● ARMED]` to initiate trading.

### Emergency Incident Procedures
- **Unintended resting orders or unexpected market movement**:
  1. Click `[🔴 EMERGENCY PANIC: CANCEL ALL ORDERS & STOP]`.
  2. Confirm the alert prompt.
  3. All open resting orders on Kalshi are cancelled immediately via `/trade-api/v2/portfolio/events/orders/{order_id}` and the engine switches to `STANDBY`.
- **Port Conflict / Lock Error (`ProcessLockError`)**:
  - Check if another bot is running: `tasklist | findstr python`.
  - To safely restart with force override:
    `python -m kalshi_sim.standalone_bot --port 8001 --live --force`
