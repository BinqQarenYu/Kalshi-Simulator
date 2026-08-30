# REST & WebSocket API Reference

The simulator exposes a high-throughput async FastAPI REST API and real-time WebSocket streams on port `8000`.

---

## 📡 WebSocket Stream: `/ws`

Connect via `ws://localhost:8000/ws` to receive high-frequency binary state updates.

### Broadcast Payload Schema
```json
{
  "timestamp": "2026-08-30T16:45:00.000Z",
  "mode": "live",
  "market": {
    "ticker": "KXBTC15M-26AUG301300-00",
    "target_strike": 79152.12,
    "current_btc_price": 79174.00,
    "expiry_seconds": 540,
    "time_window_str": "August 30, 12:45 – 1:00 PM ET",
    "target_time_str": "1:00pm ET"
  },
  "portfolio": {
    "balance": 14.85,
    "equity": 15.22,
    "realized_pnl": 0.35,
    "unrealized_pnl": 0.37,
    "drawdown_pct": 2.1,
    "win_rate": 66.7,
    "total_trades": 6
  },
  "live_portfolio": {
    "balance_dollars": 15.2841,
    "available_margin": 15.2841,
    "positions_count": 0
  },
  "ai_prediction": {
    "p_up": 0.74,
    "p_down": 0.22,
    "p_wait": 0.04,
    "vpin": 0.18,
    "ev_yes": 0.065,
    "ev_no": 0.0,
    "recommended_side": "yes",
    "rationale": "[Playbook 2] Mid-Cycle Trend Drift | Diff: +$21.88"
  },
  "settings": {
    "ai_auto_trade": true,
    "active_strategy_bot": "3_step_domination_bot",
    "active_timeframe": "15m"
  }
}
```

---

## 🔌 REST Endpoints

### 1. Market & State
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/state` | Returns the complete server and portfolio state snapshot. |
| `GET` | `/api/timeframes` | Returns supported timeframes and active contract series. |
| `POST` | `/api/settings` | Updates runtime configurations (`ai_auto_trade`, `active_strategy_bot`, `active_timeframe`). |

### 2. Strategy Bots & Multi-Bot Arena
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/bot/strategies` | Retrieves metadata, badges, and features for all quantitative bots. |
| `POST` | `/api/bot/strategy/select` | Switches active strategy bot (`3_step_domination_bot` vs `onnx_microstructure_bot`). |
| `GET` | `/api/bot/forward-validation-status` | Returns forward validation metrics, win rates, and recent cycle reports. |

### 3. Orders & Portfolio
| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/orders` | Places a manual or simulated virtual market/limit order. |
| `POST` | `/api/positions/close` | Liquidates/clears an open position (supports paper and live modes). |
| `POST` | `/api/reset` | Resets paper simulated bankrolls to specified capital (e.g. `{"capital": 15.0}`). |
| `POST` | `/api/bot/kill-switch` | Emergency Kill Switch: Trips circuit breaker and halts trading. |
| `POST` | `/api/circuit-breaker/reset` | Resets the drawdown circuit breaker to resume execution. |

### 4. Historical Analytics & Database Queries
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/history/trades` | Retrieves trade fills filtered by `bot_type` and `execution_mode`. |
| `GET` | `/api/history/settlements` | Retrieves contract expiration settlements with P&L and ROI. |
| `GET` | `/api/history/metrics` | Computes aggregate performance metrics (Win Rate, Net P&L, Sharpe, Drawdown). |
| `GET` | `/api/history/equity-curve` | Returns high-resolution time-series equity snapshots. |
| `GET` | `/api/history/ai-predictions` | Returns historical AI probability predictions and VPIN scores. |

### 5. Integrity & Compliance
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/integrity/status` | Runs mathematical invariant and clock parity audits. |
| `GET` | `/api/compliance/status` | Returns CFTC compliance rules, position caps, and wash-sale shields. |
| `GET` | `/api/system/status` | Returns CPU, memory, and GC telemetry from SystemResourceGovernor. |
