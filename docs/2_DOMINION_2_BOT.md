# 🎯 Bot 2: Dominion 2 Bot (`Dominion2Bot`)

> **Strategy ID**: `dominion_2_bot`
> **Source File**: `src/kalshi_sim/ml/dominion_2_bot.py`
> **Target Asset**: Kalshi 15-Minute Bitcoin Binary Prediction Contracts (`KXBTC15M`)

---

## 1. What It Is
The **Dominion 2 Bot** (Anti-Pin Asymmetric Scalper Engine) is an institutional quantitative strategy designed specifically to exploit asymmetric pricing sweet spots and Kalshi's unique settlement rules while actively shielding capital against late-cycle price pinning.

It incorporates the empirical winning pillars identified during live exchange execution audits:
1. Hard Entry Price Ceiling ($\le \$0.55$) to guarantee favorable risk-reward ratios ($\ge 1.22:1$).
2. Asymmetric Pricing Sweet Spot ($\$0.25 - \$0.45$) targeting high-payout discount contracts with contract size bonuses.
3. Exploitation of Kalshi's Tie Settlement Invariant ($\text{Spot} \le \text{Strike} \implies \text{NO}$ wins $\$1.00$).
4. Anti-Pin / Anti-Tie Defense to veto coin-flip trades near the strike price ($\le 180\text{s}$ left and $|\text{Diff}| \le \$25$).
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
* **Regime Logic**: In ranging or choppy regimes ($-15.00 \le \text{Diff} \le +15.00$), the NO contract has structural positive statistical expectancy.
* **Trend Logic**: For strong upward trends ($\text{Diff} \ge +\$45.00$), trades YES trend continuation.

#### Playbook 3: Confirmed Moneyness Snub ($60\text{s} \le T < 240\text{s}$ / $1\text{m} - 4\text{m}$ Remaining)
* **Objective**: Lock in discount yield on confirmed in-the-money or out-of-the-money contracts late in the cycle.
* **Anti-Pin Requirement**: Strictly requires $|S_t - K| \ge \$35.00$. If inside $\pm \$35.00$, the trade is vetoed to avoid late-cycle coin flips.

---

## 3. Configuration Settings & Hyperparameters

| Parameter | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `max_entry_price` | `Decimal` | `Decimal("0.55")` | Hard entry price ceiling ($0.55) to enforce $\ge 1.22:1$ R:R |
| `min_edge_pct` | `float` | `0.04` (4.0%) | Minimum statistical edge required post-fee |
| `min_ev_dollars` | `Decimal` | `Decimal("0.02")` | Minimum net Expected Value ($0.02/contract) required |
| `vpin_toxic_threshold` | `float` | `0.55` | Stricter VPIN score threshold for order flow toxicity veto |
| `vpin_safe_threshold` | `float` | `0.35` | Safe VPIN threshold for full Kelly sizing |
| `default_btc_1m_volatility`| `float` | `14.0` | Expected $1-minute BTC spot standard deviation ($14) |
| `take_profit_price_threshold`| `Decimal` | `Decimal("0.90")` | Profit harvest ceiling ($0.90) |
| `min_take_profit_roi` | `float` | `0.20` (+20%) | Minimum ROI target for mid-cycle exit |
| `late_cycle_roi` | `float` | `0.15` (+15%) | Minimum ROI target in late cycle |
| `fee_per_contract` | `Decimal` | `Decimal("0.01")` | Exchange taker fee per contract |
| `anti_pin_time_threshold_s`| `float` | `180.0` (3m) | Expiration window where anti-pin defense is active |
| `anti_pin_diff_threshold` | `float` | `25.0` ($25) | Spot distance threshold for anti-pin tie zone veto |
| `asymmetric_sweet_spot_max`| `Decimal` | `Decimal("0.45")` | Upper bound for asymmetric discount sweet spot ($0.25 - $0.45) |

---

## 4. Buy / Sell Entry Conditions & Trigger Points

### Entry Trigger Criteria
A trade entry is triggered if **ALL** of the following conditions pass simultaneously:
1. **Positive Net EV**: Net $\mathbb{E}[V] \ge +\$0.02$ per contract.
2. **Statistical Edge**: Edge $\alpha \ge 4.0\%$ post-fee.
3. **Price Ceiling**: Ask price MUST be $\le \$0.55$.
4. **Anti-Pin / Anti-Tie Pass**: Not inside $T \le 180\text{s}$ with $|\text{Diff}| \le \$25.00$.
5. **ONNX Uncertainty Pass**: $P(\text{WAIT}) < 0.70$ when ask is in $0.45 - 0.55$ range.

### Vetoes & Protection Filters

| Filter / Veto Name | Trigger Condition | Action / Result |
| :--- | :--- | :--- |
| **VPIN Toxicity Veto** | $\text{VPIN} \ge 0.55$ | Vetoes all new orders to prevent adverse selection by informed whales. |
| **Anti-Pin / Anti-Tie Defense** | $T \le 180\text{s}$ and $|S_t - K| \le \$25.00$ | Vetoes entries in the final 3 minutes when pinned near strike. |
| **ONNX Uncertainty Veto** | $P(\text{WAIT}) \ge 0.70$ in $0.45 - 0.55$ ask band | Suppresses entries during AI high-uncertainty regimes. |
| **Price Cap Hard Ceiling** | $\text{Ask} > \$0.55$ | Hard veto on any contract over 55¢ (guarantees $\ge 1.22:1$ R:R). |
| **Playbook 3 Late Pin Veto** | $T < 240\text{s}$ and $|S_t - K| < \$35.00$ | Vetoes entries in Playbook 3 if spot separation $< \$35.00$. |

---

## 5. Exit Conditions, Take-Profit & Stop-Loss / Salvage Triggers

The bot continuously monitors open positions against live order book bids for early liquidation or loss salvage:

### 1. Take-Profit Price Ceiling (`TAKE_PROFIT_CEILING`)
* **Trigger**: Best Bid $\ge \$0.90$.
* **Rationale**: Locks gains at 90¢ to eliminate late-cycle reversal risk.

### 2. Target ROI Harvest (`TAKE_PROFIT_ROI`)
* **Trigger**: Net ROI $\ge +20\%$ with $T \le 300\text{s}$ (final 5 minutes).
* **Rationale**: Secures banked returns before expiration volatility.

### 3. Adverse Reversal Salvage (`ADVERSE_REVERSAL_SALVAGE`)
* **Trigger**: YES position held, Spot Diff $< -\$15.00$ OTM, $T \le 90\text{s}$ left, and Best Bid $\ge \$0.10$.
* **Rationale**: Salvages residual capital ($0.10+$) on hopeless out-of-the-money positions instead of taking a $100\%$ total loss at settlement.

### 4. Automated Expiry Settlement
* **Trigger**: Contract expires ($T = 0$).
* **Payout**: $\$1.00$ per contract if $S_{\text{expiry}} > K$ (for YES) or $S_{\text{expiry}} \le K$ (for NO); otherwise $\$0.00$.

---

## 6. Capital Allocation & Risk Management

1. **Quarter-Kelly Sizing**:
   $$f^* = \frac{p \cdot b - (1 - p)}{b}$$
   $$\text{Base Size} = \text{Quarter-Kelly Sizing}$$
2. **Asymmetric Sweet-Spot Bonus**: If ask price $\le \$0.45$, contract size is boosted by **+1 contract** up to `max_position_size`.
3. **Daily Circuit Breaker**: Auto-trips and halts trading if cumulative drawdown exceeds **15%**.
