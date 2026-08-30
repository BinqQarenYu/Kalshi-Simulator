# Quantitative Strategy Bots & Algorithmic Engines

The simulator features two state-of-the-art quantitative trading bots running concurrently against live market feeds.

---

## 🤖 1. The 3-Step Domination Bot (`ThreeStepDominationBot`)

The **3-Step Domination Bot** is a cycle-aware algorithmic engine designed specifically for the microstructure dynamics of 15-minute binary contracts.

### 🎭 The 3 Cycle Playbooks

```
  0m (Start)            5m                    11m                   14m        15m (Expiry)
  │─────────────────────│─────────────────────│─────────────────────│──────────│
  ▲                     ▲                     ▲                     ▲
  │                     │                     │                     │
  [ PLAYBOOK 1 ]        [ PLAYBOOK 2 ]        [ PLAYBOOK 3 ]        [ SETTLEMENT ]
  Early Breakout        Mid Trend Drift       Late Gamma Snub       Automatic Payout
  Velocity (T=600-900s) & OFI Skew (T=240-600s) (T=45-240s)         ($1.00 or $0.00)
```

#### Playbook 1: Early Momentum Breakout ($T \in [600s, 900s]$)
* **Objective**: Exploit early cycle price dislocations when the underlying Bitcoin spot price surges away from the target strike.
* **Math Formulation**:
  $$\text{Diff} = S_t - K$$
  $$\text{Velocity} = \frac{\Delta S}{\Delta t}$$
  $$P(\text{YES}) = \Phi\left( \frac{S_t - K}{\sigma_{\text{early}} \sqrt{\tau}} \right)$$
* **Trigger**: If $|\text{Diff}| > \$15.00$ and market spread is narrow, enter with high conviction.

#### Playbook 2: Mid-Cycle Trend Drift & Order Flow Imbalance ($T \in [240s, 600s]$)
* **Objective**: Leverage Level-1 and Level-2 Order Flow Imbalance (OFI) to ride sustained spot drifts.
* **Math Formulation**:
  $$\text{OFI} = \frac{\text{BidQty} - \text{AskQty}}{\text{BidQty} + \text{AskQty}}$$
  $$P_{\text{drift}}(\text{YES}) = 0.50 + 0.35 \times \tanh\left(\frac{\text{Diff}}{25.0}\right) + 0.15 \times \text{OFI}$$

#### Playbook 3: Late Gamma Snub ($T \in [45s, 240s]$)
* **Objective**: Capture terminal time-decay yield on deep In-The-Money (ITM) or Out-Of-The-Money (OTM) contracts where probability rapidly compresses to $1.00$ or $0.00$.
* **Math Formulation**:
  $$P_{\text{gamma}} \ge 0.85 \implies \text{Buy YES at } \le \$0.80 \quad (\text{Edge} \ge 5\%)$$

---

## 🧠 2. The ONNX Microstructure Neural Net Bot (`KalshiONNXEngine`)

The **ONNX Microstructure Bot** extracts a 28-dimensional feature tensor from the L2 CLOB on every orderbook update and runs deep learning inference via ONNX Runtime CPU.

### 📐 The 28-Dimensional Microstructure Tensor

| Index | Feature Name | Description | Mathematical Expression |
| :---: | :--- | :--- | :--- |
| `0` | `spread_bps` | Inside Touch Bounded Spread | $\max(0.001, \min(0.25, \text{Ask} - \text{Bid}))$ |
| `1` | `microprice_skew` | Microprice Deviation from Mid | $\frac{\text{Bid} \cdot Q_{\text{ask}} + \text{Ask} \cdot Q_{\text{bid}}}{Q_{\text{bid}} + Q_{\text{ask}}} - \text{Mid}$ |
| `2` | `depth_imbalance_l1` | Level-1 Volume Imbalance | $\frac{Q_{\text{bid},1} - Q_{\text{ask},1}}{Q_{\text{bid},1} + Q_{\text{ask},1}}$ |
| `3` | `depth_decay_imbalance` | 15-Level Exponential Depth Imbalance | $\sum_{i=1}^{15} e^{-0.425(i-1)} (\Delta B_i - \Delta A_i)$ |
| `4` | `ofi_l1` | Inside-Touch Order Flow Imbalance | $\Delta B_1 \cdot \mathbb{I}_{\Delta P_B \ge 0} - \Delta A_1 \cdot \mathbb{I}_{\Delta P_A \le 0}$ |
| `5` | `cvd_tick_ratio` | Cumulative Volume Delta Momentum | $\frac{\text{BuyVolume} - \text{SellVolume}}{\text{TotalVolume}}$ |
| `6` | `vpin_metric` | Toxicity & Adverse Selection Metric | $\frac{\sum |V_{\tau}^B - V_{\tau}^S|}{V_{\text{bucket}}}$ |
| `7-27`| Multi-tier Depth & Flow | Deep multi-layer order book features | Normalized L2-L15 volume transitions |

### 📊 Stage 2: Mathematical Expected Value Engine (`StatisticalEVEngine`)

Binary digital contracts require digital option EV calculations rather than linear equity formulas:

$$\mathbb{E}[\text{YES}] = P_{\text{AI}}(\text{UP}) \cdot (1.00 - \text{Ask}_{\text{YES}}) - (1 - P_{\text{AI}}(\text{UP})) \cdot \text{Ask}_{\text{YES}} = P_{\text{AI}}(\text{UP}) - \text{Ask}_{\text{YES}}$$

$$\mathbb{E}[\text{NO}] = P_{\text{AI}}(\text{DOWN}) \cdot (1.00 - \text{Ask}_{\text{NO}}) - (1 - P_{\text{AI}}(\text{DOWN})) \cdot \text{Ask}_{\text{NO}} = P_{\text{AI}}(\text{DOWN}) - \text{Ask}_{\text{NO}}$$

$$\text{Statistical Edge } \alpha = P_{\text{AI}} - \text{Market Ask}$$

---

## 🛡️ Risk Management & Capital Allocation

### 1. Fractional Kelly Criterion ($0.25 \cdot f^*$)
$$f^* = \frac{p \cdot b - (1 - p)}{b} = \frac{p - \text{Ask}}{1 - \text{Ask}}$$
$$\text{Micro-Allocation (Contracts)} = \min\left( Q_{\max}, \frac{\text{Equity} \times \text{MaxRiskPct} \times (0.25 \cdot f^*)}{\text{Ask}} \right)$$

For a realistic **$15.00 bankroll**, contract sizing is capped at **1–4 contracts** ($0.50 – $1.50 per trade), preventing catastrophic drawdowns.

### 2. VPIN Toxicity Veto
If VPIN exceeds the toxicity threshold ($\text{VPIN} > 0.75$), order flow is deemed dominated by informed toxic flow, and all new trade entries are automatically vetoed.

### 3. Drawdown Circuit Breaker
If cumulative portfolio drawdown exceeds **$15\%$**, the circuit breaker trips, immediately halting all automated execution until manual review or reset.
