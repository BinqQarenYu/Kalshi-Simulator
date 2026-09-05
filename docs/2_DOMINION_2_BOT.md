# 🎯 Bot 2: Dominion 2 Bot (`Dominion2Bot`)

> **Strategy ID**: `dominion_2_bot`
> **Source File**: `src/kalshi_sim/ml/dominion_2_bot.py`
> **Target Asset**: Kalshi 15-Minute Bitcoin Binary Prediction Contracts (`KXBTC15M`)

---

## 1. What It Is
The **Dominion 2 Bot** (Anti-Pin Asymmetric Scalper Engine) is an institutional quantitative strategy designed specifically to exploit asymmetric pricing sweet spots and Kalshi's unique settlement rules while actively shielding capital against late-cycle price pinning.

It incorporates the empirical winning pillars identified during live exchange execution audits:
1. Hard Entry Price Ceiling ($\le \$0.55$) to guarantee favorable risk-reward ratios ($\ge 1.22:1$).
2. Asymmetric Pricing Sweet Spot ($\$0.25 - \$0.45$) targeting high-payout discount contracts.
3. Exploitation of Kalshi's Tie Settlement Invariant ($\text{Spot} \le \text{Strike} \implies \text{NO}$ wins $\$1.00$).
4. Anti-Pin / Anti-Tie Defense to veto coin-flip trades near the strike price in final minutes.
5. Capital Loss Salvage to recover residual equity on failing positions before expiration.

---

## 2. How It Works

The engine categorizes market regimes based on remaining time to expiry, spot-strike separation, and order flow toxicity (VPIN).

```
  0m (Cycle Start)       5m (Mid-Cycle)        11m (Late-Cycle)      12m 15m (Expiry)
  │─────────────────────│─────────────────────│─────────────────────│───│
  ▲                     ▲                     ▲                     ▲
  │                     │                     │                     │
  [ PLAYBOOK 1 ]        [ PLAYBOOK 2 ]        [ PLAYBOOK 3 ]        [ SETTLEMENT ]
  Asymmetric Momentum   Kalshi Tie / NO       Moneyness Snub        Automatic Payout
  Breakout (T >= 600s)  Exploiter (T 240-600s)(T 60-240s)           ($1.00 or $0.00)
```

### The 3 Core Playbooks

#### Playbook 1: Asymmetric Momentum Breakout ($T \ge 600\text{s}$ / $10\text{m} - 15\text{m}$ Remaining)
* **Objective**: Buy momentum breakouts when spot moves decisively away from strike ($\text{Diff} \ge +\$30.00$ for YES, $\text{Diff} \le -\$25.00$ for NO).
* **Price Filter**: Contract ask price MUST be $\le \$0.55$. If ask $\le \$0.45$ (asymmetric sweet spot), size is boosted by +1 contract.

#### Playbook 2: Kalshi Tie / NO Exploiter ($240\text{s} \le T < 600\text{s}$ / $4\text{m} - 10\text{m}$ Remaining)
* **Objective**: Exploit Kalshi's settlement tie rule ($\text{Spot} \le \text{Strike} \implies \text{NO}$ wins $\$1.00$).
* **Regime Logic**: In ranging or choppy regimes ($\text{Diff} \le +\$15.00$), the NO contract has structural positive statistical expectancy.
* **Trend Logic**: For strong upward trends ($\text{Diff} \ge +\$45.00$), trades YES trend continuation.

#### Playbook 3: Confirmed Moneyness Snub ($60\text{s} \le T < 240\text{s}$ / $1\text{m} - 4\text{m}$ Remaining)
* **Objective**: Lock in discount yield on confirmed in-the-money or out-of-the-money contracts late in the cycle.
* **Anti-Pin Requirement**: Strictly requires $|S_t - K| \ge \$35.00$. If inside $\pm \$35.00$, the trade is vetoed to avoid late-cycle coin flips.

---

## 3. Configuration Settings & Hyperparameters

| Parameter | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `max_entry_price` | `Decimal` | `Decimal("0.55")` | Hard entry price ceiling ($0.55) — prevents inverted risk-reward |
| `asymmetric_sweet_spot_max` | `Decimal` | `Decimal("0.45")` | Upper bound of asymmetric pricing sweet spot ($0.25–$0.45) |
| `min_edge_pct` | `float` | `0.04` (4.0%) | Minimum statistical edge required |
| `min_ev_dollars` | `Decimal` | `Decimal("0.02")` | Minimum net EV per contract after fees ($0.02) |
| `vpin_toxic_threshold` | `float` | `0.55` | Stricter VPIN toxicity ceiling for entry suppression |
| `vpin_safe_threshold` | `float` | `0.35` | Safe VPIN threshold |
| `default_btc_1m_volatility`| `float` | `14.0` | Expected 1-min BTC spot std dev ($14) |
| `take_profit_price_threshold`| `Decimal` | `Decimal("0.90")` | Profit harvest ceiling ($0.90) |
| `min_take_profit_roi` | `float` | `0.20` (+20%) | Minimum ROI target for profit harvest |
| `late_cycle_roi` | `float` | `0.15` (+15%) | Minimum ROI target in final 5 minutes |
| `fee_per_contract` | `Decimal` | `Decimal("0.01")` | Exchange taker fee per contract |
| `anti_pin_time_threshold_s`| `float` | `180.0` | Anti-pin window duration (3 minutes / 180 seconds) |
| `anti_pin_diff_threshold` | `float` | `25.0` | Anti-pin strike distance zone ($\pm \$25.00$) |

---

## 4. Buy / Sell Entry Conditions & Trigger Points

### Entry Trigger Criteria
A trade entry is triggered if **ALL** of the following conditions pass simultaneously:
1. **Hard Entry Ceiling**: Market Ask $\le \$0.55$ (guarantees risk $\le 55\phi$ to gain $\ge 45\phi$).
2. **Positive Net EV**: Net $\mathbb{E}[V] \ge +\$0.02$ per contract post-fee.
3. **Statistical Edge**: Statistical Edge $\alpha \ge 4.0\%$.
4. **Anti-Pin Zone Safety**: Outside the $\pm \$25.00$ pin zone if $T \le 180\text{s}$.
5. **VPIN Order Flow Safety**: VPIN Score $< 0.55$.
6. **ONNX Uncertainty Safety**: $P(\text{WAIT}) < 70\%$ when quotes are near 50¢.

### Guardrail Veto Matrix

| Veto Name | Trigger Condition | Action / Result |
| :--- | :--- | :--- |
| **Max Entry Price Veto** | Market Ask $> \$0.55$ | Hard veto on entries over 55¢ (prevents asymmetric drawdown). |
| **Anti-Pin Guard Veto** | $T \le 180\text{s}$ and $\|S_t - K\| \le \$25.00$ | Vetoes entries in final 3 minutes when spot is pinned near strike. |
| **VPIN Toxicity Veto** | $\text{VPIN} \ge 0.55$ | Vetoes entries during toxic order flow bursts. |
| **ONNX Uncertainty Veto**| $P(\text{WAIT}) \ge 0.70$ with Ask in $\$0.45–\$0.55$ | Vetoes entries during high-uncertainty chop. |
| **Late Cycle Pin Veto** | $T \le 240\text{s}$ and $\|S_t - K\| < \$35.00$ | Vetoes entries in Playbook 3 if spot distance is insufficient. |

---

## 5. Exit Conditions, Take-Profit & Stop-Loss / Salvage Triggers

```
  Position Entry ──► Monitor Best Bid ──┬── Bid >= $0.90 ──────────────────► [ TAKE PROFIT CEILING ]
                                       ├── ROI >= +20% (T <= 300s) ───────► [ TARGET ROI HARVEST ]
                                       ├── YES & Diff < -$15 & T <= 90s ──► [ ADVERSE LOSS SALVAGE ]
                                       └── Hold to Expiry ────────────────► [ AUTOMATED SETTLEMENT ]
```

### 1. Take-Profit Ceiling (`TAKE_PROFIT_CEILING`)
* **Trigger**: Best Bid $\ge \$0.90$.
* **Rationale**: Locks in profit at 90¢+, eliminating late binary flip risks.

### 2. Target ROI Harvest (`TAKE_PROFIT_ROI`)
* **Trigger**: Net ROI $\ge +20\%$ with Remaining Time $T \le 300\text{s}$ (5 minutes).
* **Rationale**: Secures banked returns as expiry approaches.

### 3. Adverse Loss Salvage (`ADVERSE_REVERSAL_SALVAGE`)
* **Trigger**: Position is YES, Spot is $>\$15.00$ OTM ($S_t - K < -\$15.00$), $T \le 90\text{s}$, and Best Bid $\ge \$0.10$.
* **Rationale**: Sells open position for 10¢–20¢ residual value instead of taking a $100\%$ total loss at $0\phi$ at settlement.

### 4. Automated Expiry Settlement
* **Trigger**: Contract expires ($T = 0$).
* **Payout**: $\$1.00$ per contract if $S_{\text{expiry}} > K$ (for YES) or $S_{\text{expiry}} \le K$ (for NO); otherwise $\$0.00$.

---

## 6. Capital Allocation & Risk Management

1. **Quarter-Kelly Sizing with Asymmetric Sweet-Spot Bonus**:
   $$\text{Base Size} = \text{Quarter-Kelly}(f^*)$$
   $$\text{Sweet-Spot Bonus}: \text{If Ask} \le \$0.45 \implies \text{Contracts} = \min(\text{MaxSize}, \text{Contracts} + 1)$$
2. **Micro-Capital Allocation**: Capped at **1–4 contracts** ($0.50 – $1.50 risk) for a $25–$50 micro bankroll.
3. **Loss Salvage Protocol**: Actively recovers capital on hopeless OTM positions in final 90 seconds.
