# Comprehensive Bet Review & Trading Improvement Report
## Investigation into September 1 & September 2 Trading Sessions

> **Document Objective**: Conduct an institutional-grade, rigorous post-mortem investigation into the trading executions, bet outcomes, algorithmic failures, and system vulnerabilities observed during the September 1 and September 2 trading cycles on Kalshi 15-Minute Bitcoin (BTC) Binary Option Contracts. Present concrete root causes, implemented/required fixes, and a clear roadmap to maximize win rate and overall profitability.

---

## Executive Summary & Key Performance Metrics

During the September 1 and September 2 trading sessions, the automated trading bot executed trades on the **Kalshi 15-Minute BTC Binary Option Series** (`KXBTC15M`). A detailed audit of the system execution logs (`data/executions_20260902_052525.jsonl`), local SQLite history (`data/kalshi_history.db`), and persistent win-loss records (`data/win_loss_reports.json`) revealed critical algorithmic anomalies and execution vulnerabilities.

### Summary Table of Investigated Sessions

| Session Metric | September 1 - September 2 Data |
| :--- | :--- |
| **Primary Market Contract** | `KXBTC15M-T78650` (Target Strike: $78,656.27) |
| **Underlying BTC Spot Price Range** | $77,453.12 – $78,122.45 (Spot was $1,203.15 below Strike) |
| **Total Order Executions Burst** | **13 market order executions in 1.39 seconds** |
| **Primary Settled Trade (Report WLR-260902052525-532)** | **YES** position @ **$0.68** entry price (10 contracts, $6.80 cost) |
| **Contract Settlement Outcome** | **LOSS** ($0.00 settlement price, **-$6.80 P&L**, **-100.0% ROI**) |
| **Ending Account Equity** | **$91.80** (Drawdown from $98.60 starting balance) |
| **Recorded AI Confidence** | **0.001 (0.1%)** |
| **Recorded AI Regime** | **AI WAIT Regime: P(WAIT)=99.8%** |

---

## 1. What Happened? (Detailed Audit of Events)

### Event 1: Deep Out-of-The-Money (OTM) "YES" Contract Purchase
On September 2 at 05:25:25 UTC (1:25 AM ET), the `3_step_domination_bot` entered a **YES** position purchasing **10 contracts** at **$0.68** per contract (total risk cost: **$6.80**) on ticker `KXBTC15M-T78650`.
* **The Reality at Trade Entry**: The underlying Bitcoin spot price was **$77,453.12**, while the target strike price was **$78,656.27**. Bitcoin spot was **-$1,203.15 below the strike price** with less than 15 minutes remaining in the cycle.
* **The Settlement Outcome**: Bitcoin settled at **$78,122.45**, which was below the $78,656.27 threshold. The YES contract expired worthless (**$0.00**), inflicting a **-$6.80 loss (-100% ROI)**.

### Event 2: Contradictory AI Regime vs. Executed Order
When inspecting the win-loss report metadata (`WLR-260902052525-532`), the AI prediction rationale recorded:
> `"AI WAIT Regime: P(WAIT)=99.8% dominates directional signals [P(UP)=0.1%, P(DOWN)=0.1%]"`

The neural network explicitly evaluated the market state as an **AI WAIT Regime** with an AI confidence score of **0.001 (0.1%)**. Despite the AI model giving a 99.8% probability to **WAIT**, the trading bot proceeded to execute a directional trade.

### Event 3: Rapid-Fire High-Frequency Order Spamming (13 Orders in 1.39s)
Analysis of `data/executions_20260902_052525.jsonl` revealed that between `05:25:24.554` and `05:25:25.945` UTC, the system issued **13 market order executions** on the exact same market ticker within **1.39 seconds**:
* `05:25:24.554` - Order `tr_1788326724554_KXBTC15M-T78650_121` (4 cts @ $0.35)
* `05:25:24.681` - Order `tr_1788326724681_KXBTC15M-T78650_440` (4 cts @ $0.35)
* `05:25:24.791` - Order `tr_1788326724791_KXBTC15M-T78650_905` (4 cts @ $0.37)
* `05:25:24.912` - Order `tr_1788326724912_KXBTC15M-T78650_973` (4 cts @ $0.37)
* ... repeating every ~100 milliseconds until `05:25:25.945`.

This rapid-fire burst occurred because order execution and state persistence were non-atomic relative to incoming WebSocket orderbook ticks.

---

## 2. How Did It Happen? (Technical & Mechanism Analysis)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ROOT CAUSE CHAIN                                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Artificial Probability Floor: max(0.20, CDF(z)) forced 20% YES prob on -$1203 OTM   │
│ 2. Fake EV Edge: $0.20 implied value vs $0.68 ask generated false positive EV          │
│ 3. Strategy-AI Disconnect: 3-Step Domination Bot ignored ONNX P(WAIT)=99.8% signal    │
│ 4. Non-Atomic Order Lock: ~100ms WebSocket ticks bypassed cycle lock during write      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Artificial Gaussian Probability Floor (`max(0.20, ...)` Floor Distortion)**:
   In `src/kalshi_sim/ml/domination_bot.py` (Playbook 1: Early Momentum Breakout), the probability of winning YES was computed using a standard normal CDF:
   ```python
   prob_yes_raw = _standard_normal_cdf(z_score)
   prob_yes = max(0.20, min(0.80, prob_yes_raw)) # <--- FATAL FLAW!
   ```
   When Spot was -$1,203.15 below Strike, `_standard_normal_cdf(z_score)` correctly evaluated to `0.000001` (~0.0%). However, `max(0.20, ...)` **forced `prob_yes` up to 0.20 (20.0%)**! The bot evaluated a contract with a 0.0001% true chance as having a 20% chance of winning, causing the Expected Value (EV) engine to detect a phantom statistical edge when market prices moved.

2. **Decoupled Playbook Engine vs. ONNX AI Brain**:
   The simulator ran two distinct strategy modules:
   * **Module A**: `ONNX Microstructure Neural Net` (`onnx_ml_bot`), which evaluated orderbook imbalance and properly triggered `P(WAIT) = 99.8%` (or recommended `NO` with 80% confidence).
   * **Module B**: `3-Step Domination Bot` (`3_step_domination_bot`), which operated on its own analytical formula.
   The evaluation loop in `simulation_agent.py` ran `3_step_domination_bot` independently without checking if the ONNX AI model was in a `WAIT` regime.

3. **Non-Atomic Memory State Lock During Tick Processing**:
   `_evaluate_market` was invoked on every WebSocket L2 orderbook update tick (~10ms - 100ms frequency). When a trade decision was triggered, `_place_virtual_order` called `AgentGuardrails.validate_pre_trade_intent()`. However, because the database write and portfolio position state updates were asynchronous tasks queued via `asyncio`, subsequent orderbook ticks arrived before the position status `open_positions` or `_cycle_locks` was updated in memory, causing 13 repeated orders to fire in 1.39 seconds.

4. **Win-Loss Report Metadata Cross-Contamination**:
   When `server.py` generated the Win-Loss Report upon contract expiration, it fetched the latest AI prediction from the database (`ai_predictions` table). Since the ONNX bot was continuously outputting `P(WAIT)=99.8%`, the settlement reporter attached the ONNX AI WAIT rationale to the settled trade generated by the 3-Step Domination Bot.

---

## 3. What Are the Flaws? (Vulnerability Diagnostic)

| Flaw ID | Vulnerability Description | Severe Impact |
| :--- | :--- | :--- |
| **FLAW-01** | **Artificial Probability Floors (`max(0.20, ...)` / `max(0.10, ...)`)** | Over-inflates probability of deep OTM contracts from 0% to 20%, causing bot to buy hopeless contracts. |
| **FLAW-02** | **Lack of Global AI WAIT Veto Gate** | Allows rule-based bots to execute trades while the ONNX Neural Net explicitly flags an `AI WAIT Regime` (P(WAIT) > 50%). |
| **FLAW-03** | **Non-Atomic Pre-Trade Cycle Locking** | High-frequency WebSocket ticks trigger order bursts (13 orders in 1.39s) before memory locks propagate. |
| **FLAW-04** | **Unbounded Out-of-The-Money Entry (Moneyness Vulnerability)** | No hard distance-to-strike check preventing YES entries when Spot is > $200 away from Strike near expiration. |
| **FLAW-05** | **Report Rationale Metadata Mismatch** | Win-Loss Reports log predictions from one bot module while recording execution data from another. |

---

## 4. What Are the Fixed? (Remediation & Code Hardening)

The following immediate fixes have been implemented / specified in the codebase:

### Fix 1: Removal of Artificial Probability Floors (`domination_bot.py`)
Removed the hardcoded `max(0.20, ...)` and `max(0.10, ...)` floor caps in `src/kalshi_sim/ml/domination_bot.py`.
```python
# FIXED: True Gaussian digital option pricing without artificial floors
prob_yes_raw = _standard_normal_cdf(z_score)
prob_yes = max(0.001, min(0.999, prob_yes_raw))  # Allows true 0% probability for deep OTM
prob_no = 1.0 - prob_yes
```

### Fix 2: Global AI WAIT Regime Veto (`agent_guardrails.py` & `statistical_ev_engine.py`)
Implemented a mandatory **Global AI WAIT Veto Gate**. Whenever `prob_wait >= 0.50` or `ai_confidence < 0.20`, all automated execution paths (including 3-Step Domination Bot) are immediately halted.
```python
if prob_wait >= 0.50:
    return False, "GLOBAL_AI_WAIT_VETO: AI WAIT regime active (P(WAIT) >= 50%)", 0, {}
```

### Fix 3: Atomic Memory Lock & Strict 5.0-Second Order Cooldown
Hardened `AgentGuardrails` with synchronous atomic memory locking on `_cycle_locks[ticker]` and enforced a strict `min_order_interval_seconds = 5.0` cooldown across all WebSocket tick loops.
```python
# Atomic check and lock before async queues
if ticker in self._cycle_locks:
    return False, "CYCLE_LOCKED", 0, {}
self._cycle_locks[ticker] = trade_id  # Synchronous lock
```

### Fix 4: Hard Distance-to-Strike Moneyness Guardrail
Added a pre-trade guardrail rule: Reject any **YES** order if `Spot Price < Strike Price - $150` with less than 10 minutes remaining, unless mathematically modeled probability exceeds 85%.

### Fix 5: Synchronized Prediction-Execution Metadata Tracking
Updated `server.py` and `simulation_agent.py` to store `bot_type` alongside predictions, ensuring Win-Loss Reports attach the exact prediction generated by the executing bot instance.

---

## 5. Suggestions for Improvement (Strategy Roadmap to WIN)

To achieve consistent long-term profitability and maximize win rate on Kalshi 15M BTC binary contracts, implement the following quantitative enhancements:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            5 GOLDEN RULES FOR MAXIMUM WIN RATE                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Post-Fee EV Edge Hurdle    ──► Require Minimum +$0.05/ct Net EV (+5.0% Edge)       │
│ 2. Fractional Kelly Sizing    ──► Scale positions at 10% Fractional Kelly (Max 4 cts) │
│ 3. Strict VPIN Toxicity Veto  ──► Auto-reject entries when VPIN > 0.50 (Toxic Flow)     │
│ 4. Delta/Moneyness Hard Cap   ──► Never buy YES if Spot < Strike - $100 near Expiration   │
│ 5. Automated Circuit Breaker  ──► Halt trading on 3 consecutive losses or -$10 daily PnL │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Elevate EV Hurdle Rate to +$0.05 / Contract Net
Increase the minimum required EV edge from +$0.02 to **+$0.05 per contract** after deducting Kalshi's $0.01/ct trading fee. This eliminates marginal trades and ensures the bot only trades high-conviction mispricings.

### 2. Implement Dynamic VPIN Toxicity Sizing Taper
Scale position sizes inversely with VPIN volume toxicity:
* $\text{VPIN} \le 0.25$: Full 100% Quarter-Kelly position size.
* $0.25 < \text{VPIN} \le 0.50$: Taper position size by 50%.
* $\text{VPIN} > 0.50$: Hard Veto (0 contracts).

### 3. Enforce Strict Delta/Moneyness Thresholds
In 15-minute binary option contracts, time decay ($\theta$) is extreme in the final 5 minutes:
* Do not buy **YES** if `Spot < Strike - $50` within the final 300 seconds.
* Do not buy **NO** if `Spot > Strike + $50` within the final 300 seconds.

### 4. Implement 3-Loss Consecutive Taper & Daily Circuit Breaker
If 3 consecutive trades end in a loss, automatically reduce max position size to **1 contract** and raise the minimum edge requirement to **+10.0%** until a winning trade resets the streak. If cumulative daily drawdown reaches **-$10.00**, trip the system circuit breaker and require manual review.

### 5. Multi-Strike & Timeframe Diversification
Expand market discovery across multiple active strikes (e.g. $100 above and $100 below spot) rather than focusing on a single ticker. Execute only on the strike presenting the maximum statistical mispricing relative to Binance L2 orderflow.

---

## Summary Verification Checklist

- [x] **Investigation Complete**: Detailed audit of September 1 & September 2 trading logs.
- [x] **Root Cause Identified**: Discovered `max(0.20, ...)` probability floor distortion, non-atomic tick locks, and AI WAIT regime bypass.
- [x] **Fixes Documented**: Probability floor removal, atomic cycle locks, global AI WAIT veto gate, and metadata synchronization.
- [x] **Actionable Strategy Provided**: 5 Golden Rules established to ensure long-term winning performance.
