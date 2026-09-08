# REST & WebSocket API Reference

This document provides a comprehensive reference for both API tiers in the ecosystem:
1. **Mother Server API (Port 8000)**: Strategy research, backtesting, and full WebCLOB streaming.
2. **Standalone Bot API (Port 8001)**: Dedicated execution daemon and Pocket Cockpit telemetry.

---

## 🏛 Tier 1: Mother Server API (Port 8000)

### 📡 WebSocket Stream: `/ws`
Connect via `ws://localhost:8000/ws` to receive high-frequency state updates.

#### Broadcast Payload Schema
```json
{
  "timestamp": "2026-09-07T16:45:00.000Z",
  "mode": "live",
  "market": {
    "ticker": "KXBTC15M-26SEP071700-00",
    "target_strike": 79152.12,
    "current_btc_price": 79174.00,
    "expiry_seconds": 540,
    "time_window_str": "September 7, 4:45 – 5:00 PM ET",
    "target_time_str": "5:00pm ET"
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

### 🔌 REST Endpoints (Port 8000)

#### 1. Market & State
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/state` | Returns the complete server and portfolio state snapshot. |
| `GET` | `/api/timeframes` | Returns supported timeframes (`5m`, `15m`) and active contract series. |
| `POST` | `/api/settings` | Updates runtime configurations (`ai_auto_trade`, `active_strategy_bot`, `active_timeframe`). |

#### 2. Strategy Bots & Multi-Bot Arena
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/bot/strategies` | Retrieves metadata, badges, and features for all quantitative bots. |
| `POST` | `/api/bot/strategy/select` | Switches active strategy bot (`3_step_domination_bot`, `dominion_2`, `onnx_microstructure_bot`). |
| `GET` | `/api/bot/forward-validation-status` | Returns forward validation metrics, win rates, and recent cycle reports. |

#### 3. Orders & Portfolio
| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/orders` | Places a manual or simulated virtual order. |
| `POST` | `/api/positions/close` | Liquidates/clears an open position (supports paper and live modes). |
| `POST` | `/api/reset` | Resets paper simulated bankrolls to specified capital (e.g. `{"capital": 15.0}`). |
| `POST` | `/api/bot/kill-switch` | Emergency Kill Switch: Trips circuit breaker and halts trading. |
| `POST` | `/api/circuit-breaker/reset` | Resets the drawdown circuit breaker to resume execution. |

#### 4. Historical Analytics & Database Queries
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/history/trades` | Retrieves trade fills filtered by `bot_type` and `execution_mode`. |
| `GET` | `/api/history/settlements` | Retrieves contract expiration settlements with P&L and ROI. |
| `GET` | `/api/history/metrics` | Computes aggregate performance metrics (Win Rate, Net P&L, Sharpe, Drawdown). |
| `GET` | `/api/history/equity-curve` | Returns high-resolution time-series equity snapshots. |
| `GET` | `/api/history/ai-predictions` | Returns historical AI probability predictions and VPIN scores. |

#### 5. Integrity & Compliance
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/integrity/status` | Runs mathematical invariant and clock parity audits. |
| `GET` | `/api/compliance/status` | Returns CFTC compliance rules, position caps, and wash-sale shields. |
| `GET` | `/api/system/status` | Returns CPU, memory, and GC telemetry from SystemResourceGovernor. |

---

## ⚡ Tier 2: Standalone Engine API (Port 8001)

The Standalone Engine (`standalone_bot.py`) serves the ultra-lean Pocket Cockpit and dedicated live trading controls on port `8001`.

### 🔌 REST Endpoints (Port 8001)

#### 1. Core State & Cockpit UI
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the single-page HTML Pocket Cockpit UI with Minimized and Expanded modes. |
| `GET` | `/api/state` | Real-time state payload (balance, realized PnL, spot, strike, countdown, telemetry). |

##### Sample Response (`GET /api/state`):
```json
{
  "armed": true,
  "balance": 15.28,
  "shard2_balance": 15.28,
  "today_pnl": 0.52,
  "settled_cycles": 1,
  "today_wins": 1,
  "today_losses": 0,
  "today_win_rate": 100.0,
  "consecutive_losses": 0,
  "max_consecutive_losses": 3,
  "active_asset": "BTC",
  "active_asset_name": "Bitcoin",
  "series_ticker": "KXBTC15M",
  "active_ticker": "KXBTC15M-26SEP071700-00",
  "time_remaining_str": "08:42",
  "target_time_str": "5:00pm ET",
  "time_window_str": "September 7, 4:45 – 5:00 PM ET",
  "position_str": "FLAT",
  "position_sub": "0 contracts active",
  "spot_price": 79215.50,
  "spot_price_str": "$79,215.50",
  "target_strike": 79150.00,
  "target_strike_str": "$79,150.00",
  "spot_diff": 65.50,
  "spot_diff_pct": 0.083,
  "moneyness_diff_str": "+$65.50 (+0.083%)",
  "is_above_strike": true,
  "playbook": "mid_drift",
  "edge_pct": 0.082,
  "ev": 0.041,
  "vpin": 0.14,
  "vpin_is_safe": true,
  "kalshi_ws_connected": true,
  "spot_connected": true
}
```

#### 2. Asset Switching
| Method | Path | Description | Request Body |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/assets` | Returns all supported crypto assets with live CF Benchmarks prices. | None |
| `POST` | `/api/assets/select` | Switches active trading asset (`BTC`, `ETH`, `SOL`, `DOGE`). | `{"asset": "ETH"}` |

#### 3. Master Controls & Circuit Breakers
| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/bot/arm` | Arms the bot for live order routing and resets consecutive loss streak counter. |
| `POST` | `/api/bot/disarm` | Disarms bot into standby mode without killing the server. |
| `POST` | `/api/bot/panic` | Emergency Panic: Cancels all resting orders on Kalshi exchange and disarms bot. |

#### 4. Strategy Parameters & Watchdog
| Method | Path | Description | Request Body |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/bot/parameters` | Returns current strategy parameters and guardrail thresholds. | None |
| `POST` | `/api/bot/parameters` | Dynamically updates parameters and risk thresholds. | `{"discount_limit_price": 0.48, "min_edge_pct": 6.0, "min_spot_diff": 35.0}` |
| `POST` | `/api/bot/sweep-orders`| Manually triggers a resting order sweep for finished events. | None |
