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
1. **MACRO_BULL** ($R_{1h} \ge +0.15\%$): Exclusively trades **YES**. Counter-trend NO bets are 100% vetoed.
2. **MACRO_BEAR** ($R_{1h} \le -0.15\%$): Exclusively trades **NO**. Counter-trend YES bets are 100% vetoed.
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
| `macro_bull_threshold_pct` | `float` | `0.15` (+0.15%) | 1-hour spot return threshold for MACRO_BULL regime |
| `macro_bear_threshold_pct` | `float` | `-0.15` (-0.15%) | 1-hour spot return threshold for MACRO_BEAR regime |
| `min_edge_pct` | `float` | `0.06` (6.0%) | Minimum statistical edge required |
| `min_ev_dollars` | `Decimal` | `Decimal("0.02")` | Minimum net EV per contract after fees ($0.02) |
| `vpin_toxic_threshold` | `float` | `0.60` | Maximum VPIN toxicity score before trade veto |
| `vpin_safe_threshold` | `float` | `0.35` | Safe VPIN threshold |
| `default_btc_1m_volatility`| `float` | `14.0` | Expected 1-min BTC spot std dev ($14) |
| `take_profit_price_threshold`| `Decimal` | `Decimal("0.95")` | Profit harvest ceiling ($0.95) |
| `min_take_profit_roi` | `float` | `0.20` (+20%) | Minimum ROI target for profit harvest |
| `late_cycle_roi` | `float` | `0.15` (+15%) | Minimum ROI target in final 120 seconds |
| `fee_per_contract` | `Decimal` | `Decimal("0.01")` | Exchange taker fee per contract |
| `min_spot_diff` | `float` | `35.0` | Minimum Spot-Strike distance in directional regimes ($35) |
| `chop_spot_diff` | `float` | `50.0` | Minimum Spot-Strike distance in MACRO_CHOP regime ($50) |
| `min_entry_price` | `float` | `0.30` | Price floor ($0.30) — avoids low-probability lottery traps |
| `max_entry_price` | `float` | `0.62` | Standard price ceiling ($0.62) |
| `hard_kill_price` | `float` | `0.68` | Absolute hard ceiling ($0.68) — hard kill on inverted R:R |
| `onnx_orderflow_weight` | `float` | `0.35` (35%) | Bayesian weight assigned to ONNX order flow model |

---

## 4. Buy / Sell Entry Conditions & Trigger Points

### Entry Trigger Criteria
A trade entry is triggered if **ALL** of the following conditions pass simultaneously:
1. **Macro Regime Gate**: Side aligns with regime (YES in BULL, NO in BEAR, $|S_t - K| \ge \$50$ in CHOP).
2. **ONNX Order Flow Concordance**: ONNX model does NOT contradict trade direction (e.g., if buying YES, ONNX signal cannot be SHORT with confidence $\ge 55\%$).
3. **Price Sweet Spot Gate**: Contract ask price is between $\$0.30$ (floor) and $\$0.62$ (standard cap; up to $\$0.68$ hard kill only if deep ITM $|S_t - K| \ge \$80.00$).
4. **Positive Net EV**: Net $\mathbb{E}[V] \ge +\$0.02$ per contract post-fee.
5. **Statistical Edge**: Statistical Edge $\alpha \ge 6.0\%$.
6. **VPIN Order Flow Safety**: VPIN Score $\le 0.60$.

### Guardrail Veto Matrix

| Veto Name | Trigger Condition | Action / Result |
| :--- | :--- | :--- |
| **Macro Trend Veto** | Bet NO in `MACRO_BULL` or YES in `MACRO_BEAR` | 100% hard veto on counter-trend trades. |
| **ONNX Contradiction Veto**| Bet YES when ONNX says `SHORT` (Conf $\ge 55\%$) or bet NO when ONNX says `LONG` | Vetoes trades fighting incoming Bitcoin microstructure order flow. |
| **ONNX Neutral Veto** | ONNX $P(\text{WAIT}) \ge 0.70$ and $\|S_t - K\| < \$50.00$ | Suppresses trade during high order flow uncertainty in chop zone. |
| **Price Floor Veto** | Market Ask $< \$0.30$ | Vetoes cheap lottery tickets with low win probability. |
| **Price Cap Hard Kill** | Market Ask $> \$0.68$ | Vetoes contracts over 68¢ (prevents asymmetric risk). |
| **Price Cap Standard** | Market Ask $> \$0.62$ and $\|S_t - K\| < \$80.00$ | Vetoes contracts over 62¢ unless deep spot separation exists. |
| **VPIN Toxicity Veto** | $\text{VPIN} > 0.60$ | Vetoes entries during toxic order flow. |

---

## 5. Exit Conditions, Take-Profit & Stop-Loss / Salvage Triggers

```
  Position Entry ──► Monitor Best Bid ──┬── Bid >= $0.95 ──────────────────────► [ TAKE PROFIT CEILING ]
                                       ├── T <= 120s & Bid >= 0.85 & ROI >= 15%─► [ LATE CYCLE HARVEST ]
                                       ├── ROI >= +20% & Bid >= $0.80 ─────────► [ TARGET ROI HARVEST ]
                                       ├── T <= 90s & Adverse Diff > $50 ──────► [ CUT LOSS SALVAGE ]
                                       └── Hold to Expiry ─────────────────────► [ AUTOMATED SETTLEMENT ]
```

### 1. Take-Profit Ceiling (`TAKE_PROFIT_CEILING`)
* **Trigger**: Best Bid $\ge \$0.95$ and Net PnL $> \$0.00$.
* **Rationale**: Liquidates early to lock in 95%+ maximum potential profit.

### 2. Late-Cycle Harvest (`LATE_CYCLE_HARVEST`)
* **Trigger**: Remaining Time $T \le 120\text{s}$, Best Bid $\ge \$0.85$, and Net ROI $\ge +15\%$.
* **Rationale**: Secures gains before final settlement volatility.

### 3. Target ROI Harvest (`TAKE_PROFIT_ROI`)
* **Trigger**: Net ROI $\ge +20\%$ and Best Bid $\ge \$0.80$.
* **Rationale**: Harvests profits when target ROI is reached.

### 4. Cut-Loss Salvage (`CUT_LOSS_SALVAGE`)
* **Trigger**: Remaining Time $T \le 90\text{s}$, position is severely adverse ($S_t - K \le -\$50.00$ for YES, or $S_t - K \ge +\$50.00$ for NO), and Best Bid $\ge \$0.08$.
* **Rationale**: Liquidates failing position at 8¢–20¢ bid to salvage capital instead of expiring at $0\phi$.

### 5. Automated Expiry Settlement
* **Trigger**: Contract expires ($T = 0$).
* **Payout**: $\$1.00$ per contract if $S_{\text{expiry}} > K$ (for YES) or $S_{\text{expiry}} \le K$ (for NO); otherwise $\$0.00$.

---

## 6. Capital Allocation & Risk Management

1. **Micro-Bankroll Sizing Rule**:
   - Total Equity $< \$50.00 \implies$ Strictly **1 contract** per trade ($0.30 – $0.62 max risk).
   - Total Equity $\ge \$50.00 \implies$ Capped at **2 contracts** max.
2. **Fractional Kelly Capital Sizing ($0.15 \cdot f^*$)**: Enforces strict portfolio risk caps ($\le 5\%$ of equity per event).
3. **Cut-Loss Salvage Protocol**: Salvages $8\phi–20\phi$ per contract on hopeless OTM trades in the final 90 seconds.
