# 🤖 Bot 1: 3-Step Domination Bot (`ThreeStepDominationBot`)

> **Strategy ID**: `3_step_domination_bot`
> **Source File**: `src/kalshi_sim/ml/domination_bot.py`
> **Target Asset**: Kalshi 15-Minute Bitcoin Binary Prediction Contracts (`KXBTC15M`)

---

## 1. What It Is
The **3-Step Domination Bot** is an institutional cycle-aware quantitative trading engine designed specifically for the microstructure dynamics and time-decay properties of 15-minute binary options contracts on Kalshi.

Rather than relying on a single static model throughout the contract's life, the bot divides each 15-minute cycle into three distinct time windows (playbooks), applying tailored mathematical models and probability estimators suited for each phase of the expiration lifecycle.

---

## 2. How It Works

The engine runs a continuous execution loop evaluating live Level-2 Central Limit Order Book (CLOB) data, real-time Bitcoin spot index pricing, and order flow imbalance metrics.

```
  0m (Cycle Start)       5m (Mid-Cycle)        11m (Late-Cycle)      14m 15m (Expiry)
  │─────────────────────│─────────────────────│─────────────────────│───│
  ▲                     ▲                     ▲                     ▲
  │                     │                     │                     │
  [ PLAYBOOK 1 ]        [ PLAYBOOK 2 ]        [ PLAYBOOK 3 ]        [ SETTLEMENT ]
  Early Breakout        Mid Trend Drift       Late Gamma Snub       Automatic Payout
  Velocity (T > 600s)   & OFI Skew (T 240-600s)(T 45-240s)          ($1.00 or $0.00)
```

### The 3 Cycle Playbooks

#### Playbook 1: Early Momentum Breakout ($T > 600\text{s}$ / $10\text{m} - 15\text{m}$ Remaining)
* **Objective**: Capture early cycle directional surges away from the strike price.
* **Math Model**: Standard Normal Cumulative Distribution Function $\Phi(z)$ based on time-scaled volatility:
  $$\tau_{\text{mins}} = \frac{T}{60.0}, \quad \sigma_{\text{expected}} = \max(18.0, \sigma_{\text{default}} \cdot \sqrt{\tau_{\text{mins}}})$$
  $$z = \frac{S_t - K}{\sigma_{\text{expected}}}, \quad P(\text{YES}) = \Phi(z)$$
* **Trigger**: $|\text{Spot} - \text{Strike}| \ge \$35.00$ with statistical edge $\ge 6.0\%$.

#### Playbook 2: Mid-Cycle Trend Drift & OFI ($240\text{s} < T \le 600\text{s}$ / $4\text{m} - 10\text{m}$ Remaining)
* **Objective**: Combine spot moneyness with multi-level Order Flow Imbalance (OFI) and Level-3 order book volume skew.
* **Math Model**:
  $$\text{Book Skew} = \frac{\text{BidVol}_{L3} - \text{AskVol}_{L3}}{\max(1.0, \text{BidVol}_{L3} + \text{AskVol}_{L3})}$$
  $$z = \frac{(S_t - K) + (\text{Book Skew} \times 12.0)}{\sigma_{\text{expected}}}$$
  $$P(\text{YES}) = \Phi(z)$$

#### Playbook 3: Late-Cycle Gamma Snub ($45\text{s} \le T \le 240\text{s}$ / $0:45\text{s} - 4\text{m}$ Remaining)
* **Objective**: Harvest remaining yield on contracts deep in-the-money (ITM) or out-of-the-money (OTM) as binary delta/gamma rapidly collapse.
* **Math Model**: Dynamic volatility contracts sharply ($\sigma_{\text{expected}} = \max(4.0, \sigma_{\text{default}} \cdot \sqrt{\tau_{\text{mins}}})$), forcing $P(\text{YES})$ toward $1.00$ or $0.00$.

---

## 3. Configuration Settings & Hyperparameters

| Parameter | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `min_edge_pct` | `float` | `0.06` (6.0%) | Minimum statistical edge post-fee required to enter |
| `min_ev_dollars` | `Decimal` | `Decimal("0.02")` | Minimum net Expected Value ($0.02/contract) required |
| `vpin_toxic_threshold` | `float` | `0.60` | Maximum VPIN score allowed before entry veto |
| `vpin_safe_threshold` | `float` | `0.35` | Safe VPIN threshold for full Kelly sizing |
| `default_btc_1m_volatility`| `float` | `14.0` | Expected $1-minute BTC spot standard deviation ($14) |
| `take_profit_price_threshold`| `Decimal` | `Decimal("0.95")` | Profit harvest ceiling ($0.95) to eliminate late tail risk |
| `min_take_profit_roi` | `float` | `0.20` (+20%) | Minimum ROI target for mid-cycle exit |
| `late_cycle_roi` | `float` | `0.15` (+15%) | Minimum ROI target in final 120 seconds |
| `fee_per_contract` | `Decimal` | `Decimal("0.01")` | Exchange taker fee per contract |
| `min_spot_diff` | `float` | `35.0` | Minimum Spot-Strike distance ($35.00) to skip coin flips |
| `max_entry_price` | `float` | `0.62` | Standard maximum entry price cap (enforces $\ge 1.6:1$ R:R) |

---

## 4. Buy / Sell Entry Conditions & Trigger Points

### Entry Trigger Criteria
A trade entry is triggered if **ALL** of the following conditions pass simultaneously:
1. **Positive Net EV**: Net $\mathbb{E}[V] = P_{\text{win}} - \text{Ask} - \text{Fee} \ge +\$0.02$ per contract.
2. **Statistical Edge**: Edge $\alpha = P_{\text{win}} - \text{Ask} - \text{Fee} \ge 6.0\%$.
3. **Spot-Strike Distance**: $|S_t - K| \ge \$35.00$ (prevents entering dead-center coin flips).
4. **Price Corridor Gate**: Ask price is between $\$0.06$ and $\$0.62$ (or up to $\$0.72$ only if deep ITM $|S_t - K| \ge \$80.00$).
5. **Momentum Alignment**: Bet side MUST align with spot momentum direction unless edge $\ge 15.0\%$ (prevents counter-trend losses).

### Vetoes & Protection Filters

| Filter / Veto Name | Trigger Condition | Action / Result |
| :--- | :--- | :--- |
| **VPIN Toxicity Veto** | $\text{VPIN} > 0.60$ | Vetoes all new orders to prevent adverse selection by informed whales. |
| **Spot Proximity Veto** | $\|S_t - K\| < \$35.00$ | Vetoes trade entries when BTC is pinned near strike (50/50 coin-flip zone). |
| **Price Cap Hard Kill** | $\text{Ask} > \$0.72$ | Hard veto on any contract over 72¢ (prevents asymmetric risk of risking 72¢+ to win < 28¢). |
| **Price Cap Standard** | $\text{Ask} > \$0.62$ and $\|S_t - K\| < \$80.00$ | Vetoes entries over 62¢ unless deep spot separation is confirmed. |
| **Momentum Alignment Veto**| Bet NO when $S_t > K + \$35$ or bet YES when $S_t < K - \$35$ with Edge $< 15\%$ | Blocks contrarian trades against active market momentum. |
| **Overnight Cautious Mode** | Time between 1:00 AM – 6:00 AM ET | Requires higher edge ($\ge 12\%$) and wider separation ($\ge \$75$), caps size at 1 contract. |
| **Expiry Lock Window** | $T < 45\text{s}$ | Locks new entries in final 45 seconds prior to settlement. |

---

## 5. Exit Conditions, Take-Profit & Stop-Loss / Salvage Triggers

The bot continuously monitors open positions against live order book bids for early liquidation:

```
  Position Entry ──► Monitor Best Bid ──┬── Bid >= $0.95 ─────────► [ TAKE PROFIT CEILING ]
                                       ├── T <= 120s & Bid >= 0.85 ─► [ LATE CYCLE HARVEST ]
                                       ├── ROI >= +20% & Bid >= 0.80► [ TARGET ROI HARVEST ]
                                       └── Hold to Expiry ────────► [ AUTOMATED SETTLEMENT ]
```

### 1. Take-Profit Price Ceiling (`TAKE_PROFIT_CEILING`)
* **Trigger**: Best Bid $\ge \$0.95$ and Net PnL $> \$0.00$.
* **Rationale**: Captures 95%+ of maximum potential gain while eliminating asymmetric late-cycle reversal risk.

### 2. Late-Cycle Harvest (`LATE_CYCLE_HARVEST`)
* **Trigger**: Remaining Time $T \le 120\text{s}$, Best Bid $\ge \$0.85$, and Net ROI $\ge +15\%$.
* **Rationale**: Locks in profits before final binary settlement volatility.

### 3. Target ROI Harvest (`TAKE_PROFIT_ROI`)
* **Trigger**: Net ROI $\ge +20\%$ and Best Bid $\ge \$0.80$.
* **Rationale**: Secures banked returns when target gain threshold is achieved.

### 4. Automated Expiry Settlement
* **Trigger**: Contract expires ($T = 0$).
* **Payout**: $\$1.00$ per contract if $S_{\text{expiry}} > K$ (for YES) or $S_{\text{expiry}} \le K$ (for NO); otherwise $\$0.00$.

---

## 6. Capital Allocation & Risk Management

1. **Fractional Kelly Criterion ($0.15 \cdot f^*$)**:
   $$f^* = \frac{p \cdot b - (1 - p)}{b} = \frac{p - \text{Ask}_{\text{effective}}}{1 - \text{Ask}_{\text{effective}}}$$
   $$\text{Contract Size} = \min\left(\text{MaxSize}, \frac{\text{Equity} \times 0.05 \times (0.15 \cdot f^*)}{\text{Ask} + \text{Fee}}\right)$$
2. **Micro-Capital Sizing Cap**: In live trading ($30 bankroll), sizing is strictly capped at **1–2 contracts** ($0.50 – $1.50 per trade), preventing drawdown.
3. **Daily Circuit Breaker**: Auto-trips and halts trading if cumulative drawdown exceeds **15%**.
