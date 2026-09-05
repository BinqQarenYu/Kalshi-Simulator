# 📈 Bot 3: Macro Trend Dominion Bot (`MacroTrendDominionBot`)

> **Strategy ID**: `macro_onnx` / `macro_trend_dominion`
> **Source File**: `src/kalshi_sim/ml/macro_trend_dominion_bot.py`
> **Target Asset**: Kalshi 15-Minute Bitcoin Binary Prediction Contracts (`KXBTC15M`)

---

## 1. What It Is
The **Macro Trend Dominion Bot** (Macro Trend Following & Asymmetric Capital Preservation Engine) is designed specifically to eliminate the #1 failure mode in binary contract trading: fighting the macro trend during Bitcoin bull/bear trend expansions.

It combines a multi-scale macro trend classification engine with Bayesian ONNX Bitcoin microstructure order flow fusion, enforcing strict trend alignment gates and micro-bankroll capital preservation rules.

---

## 2. How It Works

The engine tracks rolling 1-hour ($R_{1h}$) and 15-minute ($R_{15m}$) percentage returns of the underlying Bitcoin spot index to classify the market regime into **MACRO_BULL**, **MACRO_BEAR**, or **MACRO_CHOP**.

```
                           [ Rolling Spot Ticks (2 Hours Buffer) ]
                                            │
                                            ▼
                           [ Compute 1-Hour & 15-Min Returns ]
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               ▼                            ▼                            ▼
        [ MACRO_BULL ]               [ MACRO_BEAR ]               [ MACRO_CHOP ]
      R_1h >= +0.15%               R_1h <= -0.15%               -0.15% < R_1h < +0.15%
  Exclusively Trades YES       Exclusively Trades NO       Requires |Diff| >= $50.00
  Counter NO Vetoed (100%)    Counter YES Vetoed (100%)    Enforces strict barrier
```

### Macro Regime Rules
1. **MACRO_BULL** ($R_{1h} \ge +0.15\%$ or $R_{1h} > +0.05\%$ with $R_{15m} \ge +0.10\%$): Exclusively trades **YES**. Counter-trend NO bets are 100% vetoed.
2. **MACRO_BEAR** ($R_{1h} \le -0.15\%$ or $R_{1h} < -0.05\%$ with $R_{15m} \le -0.10\%$): Exclusively trades **NO**. Counter-trend YES bets are 100% vetoed.
3. **MACRO_CHOP** (Ranging market): Enforces a strict $\$50.00$ spot-strike separation barrier before allowing trades on either side.

### Bayesian ONNX Microstructure Order Flow Fusion
Moneyness probability derived from digital option CDF ($\Phi(z)$) is fused with real-time Bitcoin L2 microstructure order flow inference from the ONNX neural network:

$$W_{\text{ONNX}} = 0.35 \quad (35\% \text{ weight for ONNX order flow})$$
$$P_{\text{fused}}(\text{YES}) = (1 - W_{\text{ONNX}}) \cdot P_{\text{moneyness}}(\text{YES}) + W_{\text{ONNX}} \cdot P_{\text{ONNX}}(\text{LONG})$$
$$P_{\text{fused}}(\text{NO}) = (1 - W_{\text{ONNX}}) \cdot P_{\text{moneyness}}(\text{NO}) + W_{\text{ONNX}} \cdot P_{\text{ONNX}}(\text{SHORT})$$

---

## 3. Configuration Settings & Hyperparameters

| Parameter | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `strategy_id` | `str` | `"macro_onnx"` | Strategy ID string identifier |
| `strategy_name` | `str` | `"Macro ONNX Bot"` | Human-readable strategy name |
| `min_edge_pct` | `float` | `0.06` (6.0%) | Minimum statistical edge post-fee required to enter |
| `min_ev_dollars` | `Decimal` | `Decimal("0.02")` | Minimum net Expected Value ($0.02/contract) required |
| `vpin_toxic_threshold` | `float` | `0.60` | Maximum VPIN score allowed before entry veto |
| `vpin_safe_threshold` | `float` | `0.35` | Safe VPIN threshold for full Kelly sizing |
| `default_btc_1m_volatility`| `float` | `14.0` | Expected $1-minute BTC spot standard deviation ($14) |
| `take_profit_price_threshold`| `Decimal` | `Decimal("0.95")` | Profit harvest ceiling ($0.95) |
| `min_take_profit_roi` | `float` | `0.20` (+20%) | Minimum ROI target for mid-cycle exit |
| `late_cycle_roi` | `float` | `0.15` (+15%) | Minimum ROI target in late cycle |
| `fee_per_contract` | `Decimal` | `Decimal("0.01")` | Exchange taker fee per contract |
| `min_spot_diff` | `float` | `35.0` | Minimum Spot-Strike distance ($35.00) in trend regimes |
| `chop_spot_diff` | `float` | `50.0` | Strict Spot-Strike distance ($50.00) required in MACRO_CHOP |
| `min_entry_price` | `float` | `0.30` | Floor entry price cap ($0.30) to eliminate low-probability traps |
| `max_entry_price` | `float` | `0.62` | Standard maximum entry price cap |
| `hard_kill_price` | `float` | `0.68` | Absolute hard kill price ceiling |
| `macro_bull_threshold_pct` | `float` | `0.15` (+0.15%) | 1-hour return threshold to classify MACRO_BULL |
| `macro_bear_threshold_pct` | `float` | `-0.15` (-0.15%) | 1-hour return threshold to classify MACRO_BEAR |
| `max_spot_history_seconds` | `float` | `7200.0` (2 hours)| Rolling spot tick buffer size |
| `onnx_orderflow_weight` | `float` | `0.35` (35%) | Weight assigned to ONNX microstructure order flow probability |

---

## 4. Buy / Sell Entry Conditions & Trigger Points

### Entry Trigger Criteria
A trade entry is triggered if **ALL** of the following conditions pass simultaneously:
1. **Positive Net EV**: Net $\mathbb{E}[V] \ge +\$0.02$ per contract.
2. **Statistical Edge**: Edge $\alpha \ge 6.0\%$ post-fee.
3. **Macro Trend Alignment**:
   - In **MACRO_BULL**: Only **YES** entries permitted.
   - In **MACRO_BEAR**: Only **NO** entries permitted.
   - In **MACRO_CHOP**: $|S_t - K| \ge \$50.00$ required.
4. **Price Corridor Gate**: Ask price is bounded between $\$0.30$ and $\$0.62$ (or up to $\$0.68$ if deep spot diff $\ge \$80.00$).
5. **Micro-Bankroll Sizing Cap**: Position size is strictly **1 contract** when total equity $< \$50.00$ (and max 2 contracts above $\$50.00$).

### Vetoes & Protection Filters

| Filter / Veto Name | Trigger Condition | Action / Result |
| :--- | :--- | :--- |
| **VPIN Toxicity Veto** | $\text{VPIN} > 0.60$ | Vetoes all new orders to prevent adverse selection by informed whales. |
| **Counter-Trend Veto** | Betting NO in MACRO_BULL or YES in MACRO_BEAR | 100% veto on counter-trend entries to eliminate fighting macro momentum. |
| **MACRO_CHOP Barrier Veto** | $|S_t - K| < \$50.00$ in MACRO_CHOP regime | Blocks entries in ranging markets unless spot is far from strike. |
| **Price Floor Veto** | $\text{Ask} < \$0.30$ | Vetoes cheap lottery traps under 30¢. |
| **Price Ceiling Veto** | $\text{Ask} > \$0.68$ (or $> \$0.62$ when $|S_t - K| < \$80$) | Vetoes high-cost entries to protect risk-reward. |

---

## 5. Exit Conditions, Take-Profit & Stop-Loss / Salvage Triggers

### 1. Take-Profit Price Ceiling (`TAKE_PROFIT_CEILING`)
* **Trigger**: Best Bid $\ge \$0.95$ and Net PnL $> \$0.00$.
* **Rationale**: Locks profit at 95¢ to eliminate late-cycle reversal risk.

### 2. Late-Cycle Harvest (`LATE_CYCLE_HARVEST`)
* **Trigger**: $T \le 120\text{s}$, Best Bid $\ge \$0.85$, and Net ROI $\ge +15\%$.
* **Rationale**: Locks gains in final 2 minutes.

### 3. Target ROI Harvest (`TAKE_PROFIT_ROI`)
* **Trigger**: Net ROI $\ge +20\%$ and Best Bid $\ge \$0.80$.
* **Rationale**: Secures returns when gain target is reached.

### 4. Cut-Loss Loss Salvage (`CUT_LOSS_SALVAGE`)
* **Trigger**: Position is held, $T \le 90\text{s}$ remaining, spot diff is adversely out-of-the-money ($< -\$50$ for YES or $> +\$50$ for NO), and Best Bid $\ge \$0.10$.
* **Rationale**: Salvages $10\text{c} - 20\text{c}$ residual capital on failing trades rather than taking a total loss at expiration.

---

## 6. Capital Allocation & Risk Management

1. **Micro-Bankroll Equity Guardrail**: Exactly **1 contract** per trade while total account balance $< \$50.00$ (max 2 contracts when $\ge \$50.00$).
2. **Fractional Kelly Criterion ($0.15 \cdot f^*$)**:
   $$f^* = \frac{p \cdot b - (1 - p)}{b}$$
3. **Daily Circuit Breaker**: Auto-trips and halts trading if cumulative drawdown exceeds **15%**.
