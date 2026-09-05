# 🧠 Bot 4: ONNX Microstructure Neural Net Bot (`KalshiONNXEngine` & `StatisticalEVEngine`)

> **Strategy ID**: `onnx_microstructure_bot`
> **Source Files**: `src/kalshi_sim/ml/onnx_engine.py`, `src/kalshi_sim/ml/feature_extractor.py`, `src/kalshi_sim/ml/statistical_ev_engine.py`
> **Target Asset**: Kalshi 15-Minute Bitcoin Binary Prediction Contracts (`KXBTC15M`)

---

## 1. What It Is
The **ONNX Microstructure Neural Net Bot** is a high-frequency, sub-millisecond quantitative trading system that extracts a 28-dimensional feature vector from the Level-2 CLOB and public trade stream on every tick, passes it to a deep neural graph via ONNX Runtime CPU, and evaluates exact Expected Value ($\mathbb{E}[V]$) against live bid/ask spreads.

It solves the binary odds-inversion flaw by decoupling directional probability prediction (Stage 1 AI) from execution and capital sizing (Stage 2 Mathematical EV & Kelly Engine).

---

## 2. How It Works

The bot operates a two-stage decision pipeline:

```
  [ Level-2 CLOB Book & Public Trade Tape ]
                      │
                      ▼
 ┌─────────────────────────────────────────────────────────────┐
 │       STAGE 1: 28-D FEATURE EXTRACTION & ONNX INFERENCE     │
 │                                                             │
 │  • Extract 28-D vector (OFI, CVD, VPIN, Decay Depth, Spoof) │
 │  • Apply Z-Score normalization (feature_stats.json)        │
 │  • Execute ONNX Model (nano_microscope_overhauled.onnx)     │
 │  • Apply Temperature Softmax Scaling (T = 0.65)             │
 │  • Outputs: P(LONG), P(SHORT), P(WAIT), VPIN Score          │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │       STAGE 2: MATHEMATICAL EV & KELLY SIZING ENGINE        │
 │                                                             │
 │  • Calculate Net EV post-fee ($0.01/ct):                    │
 │    Net E[YES] = P(LONG) - Ask_YES - Fee                     │
 │    Net E[NO]  = P(SHORT) - Ask_NO - Fee                     │
 │  • Price Corridor Check: $0.06 <= Ask <= $0.90              │
 │  • VPIN Taper: Scales size 1.0 -> 0.0 in warning band        │
 │  • Fractional Kelly Sizing: f* = (P*b - (1-P))/b           │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
                 [ Virtual Order Execution ]
```

---

## 3. The 28-Dimensional Microstructure Feature Tensor

| Index | Feature Symbol | Category | Description | Formula / Expression |
| :---: | :--- | :--- | :--- | :--- |
| `0` | `spread_bps` | Market Quality | Bounded Inside Touch Spread | $\max(0.001, \min(0.25, \text{Ask} - \text{Bid}))$ |
| `1` | `ofi_l1` | Order Flow | Top-of-Book Order Flow Imbalance | $\frac{B_1 - A_1}{B_1 + A_1 + \epsilon}$ |
| `2` | `ofi_l5` | Order Flow | Level 1-5 Cumulative Imbalance | $\frac{\sum_{i=1}^5 B_i - \sum_{i=1}^5 A_i}{\sum_{i=1}^5 B_i + \sum_{i=1}^5 A_i + \epsilon}$ |
| `3` | `ofi_l15` | Order Flow | Full 15-Level Book Imbalance | $\frac{\sum B_i - \sum A_i}{\sum B_i + \sum A_i + \epsilon}$ |
| `4` | `cvd_norm` | Momentum | Cumulative Volume Delta (Normalized) | $\frac{\sum (\text{Signed Trade Qty})}{\text{Baseline Volume}}$ |
| `5` | `entropy` | Market Dynamics | Trade Size Shannon Entropy | $-\sum p_i \log_2(p_i)$ over rolling trades |
| `6` | `vpin_score` | Toxicity | Volume-Synchronized Probability of Toxicity | PBC algorithm over volume buckets |
| `7` | `spoof_mag_bid` | Microstructure | Bid Layer Queue Cancellation Ratio | Weighted outer-layer bid cancellations |
| `8` | `spoof_mag_ask` | Microstructure | Ask Layer Queue Cancellation Ratio | Weighted outer-layer ask cancellations |
| `9` | `bid_absorption`| Microstructure | Touch Bid Liquidity Absorption | Passive bid liquidity consumed without price move |
| `10`| `ask_absorption`| Microstructure | Touch Ask Liquidity Absorption | Passive ask liquidity consumed without price move |
| `11`| `whale_tx` | Order Flow | Institutional Block Trade Counter | Count of trades exceeding dynamic threshold |
| `12`| `layering_index`| Depth Geometry | Outer vs. Inner Book Density Ratio | $\frac{\text{Volume}(L_6 \dots L_{15})}{\text{Volume}(L_1 \dots L_5) + \epsilon}$ |
| `13-27`| `spatial_0..14`| Exponential Depth | 15-Level Exponential Decay Imbalance | $e^{-\alpha i} \cdot \left(\frac{B_i - A_i}{\text{Baseline}}\right)$ for $i=0 \dots 14$ |

---

## 4. Configuration Settings & Hyperparameters

| Parameter | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `confidence_threshold` | `float` | `0.70` (70%) | Directional dominance threshold required to generate signal |
| `temperature` | `float` | `0.65` | Temperature parameter for softmax logit calibration |
| `min_ev_threshold` | `Decimal` | `Decimal("0.02")` | Minimum net EV per contract after fees ($0.02) |
| `min_edge_pct` | `float` | `0.03` (3.0%) | Minimum net statistical edge post-fee |
| `fee_per_contract` | `Decimal` | `Decimal("0.01")` | Exchange taker fee per contract ($0.01) |
| `fractional_kelly` | `float` | `0.15` (15%) | Fractional Kelly multiplier for capital allocation |
| `max_portfolio_risk_pct` | `Decimal` | `Decimal("0.05")` | Maximum portfolio risk per trade (5%) |
| `vpin_safe_threshold` | `float` | `0.35` | VPIN score $\le 0.35$ gets 100% full Kelly sizing |
| `vpin_warn_threshold` | `float` | `0.50` | VPIN warning threshold |
| `vpin_toxic_threshold` | `float` | `0.60` / `0.75` | VPIN score $\ge 0.60$ tapers size to 0; $> 0.75$ triggers hard veto |
| `price_corridor_min` | `Decimal` | `Decimal("0.06")` | Price corridor floor ($0.06) — prevents fee drag |
| `price_corridor_max` | `Decimal` | `Decimal("0.90")` | Price corridor ceiling ($0.90) — prevents tail risk blowups |

---

## 5. Buy / Sell Entry Conditions & Trigger Points

### Entry Trigger Criteria
A trade entry is triggered if **ALL** of the following conditions pass simultaneously:
1. **Stage 1 Signal**: ONNX model outputs `LONG` or `SHORT` with relative dominance $\ge 55\%$ and $P(\text{LONG/SHORT}) \ge 10\%$.
2. **Positive Net EV**: Net $\mathbb{E}[V] = P_{\text{AI}} - \text{Ask} - \text{Fee} \ge +\$0.02$ per contract.
3. **Net Statistical Edge**: Edge $\alpha = P_{\text{AI}} - \text{Ask} - \text{Fee} \ge 3.0\%$.
4. **Price Corridor Gate**: Contract Ask price is inside $\$0.06 \le \text{Ask} \le \$0.90$.
5. **VPIN Safety & Taper**: VPIN Score $< 0.60$ (or tapered if between $0.35$ and $0.60$).
6. **Regime Gate**: $P(\text{WAIT})$ does NOT dominate directional probabilities.

### VPIN Continuous Toxicity Taper Formula
Position sizing is scaled continuously based on measured market toxicity:

$$\text{VPIN Multiplier} = \begin{cases}
1.0 & \text{if } \text{VPIN} \le 0.35 \quad \text{(Full Kelly Sizing)} \\
1.0 - \frac{\text{VPIN} - 0.35}{0.60 - 0.35} & \text{if } 0.35 < \text{VPIN} < 0.60 \quad \text{(Linear Decay)} \\
0.0 & \text{if } \text{VPIN} \ge 0.60 \quad \text{(Sizing Frozen)}
\end{cases}$$

---

## 6. Exit Conditions, Take-Profit & Expiry Settlement

### 1. Stage 2 Model Inversion Exit
* **Trigger**: Stage 1 AI signal flips direction (e.g., from `LONG` to `SHORT`) or $P(\text{WAIT}) \ge 70\%$ while holding position.

### 2. Automated Expiry Settlement
* **Trigger**: Contract reaches 15-minute expiration ($T = 0$).
* **Payout**: $\$1.00$ per contract if contract settles in-the-money; $\$0.00$ if out-of-the-money.

---

## 7. Capital Allocation & Risk Management

1. **Fractional Kelly Criterion ($0.15 \cdot f^*$)**:
   $$b = \frac{1.00 - (\text{Ask} + \text{Fee})}{\text{Ask} + \text{Fee}}$$
   $$f^* = \frac{P_{\text{AI}} \cdot b - (1 - P_{\text{AI}})}{b}$$
   $$\text{Tapered Kelly Fraction} = (0.15 \cdot f^*) \times \text{VPIN Multiplier}$$
2. **Contract Sizing Formula**:
   $$\text{Allocated Capital} = \min\left(\text{Equity} \times 0.05, \, \text{Equity} \times \text{Tapered Kelly Fraction}\right)$$
   $$\text{Contracts} = \max\left(1, \, \min\left(\text{MaxSize}, \, \left\lfloor \frac{\text{Allocated Capital}}{\text{Ask} + \text{Fee}} \right\rfloor \right)\right)$$
3. **Sub-Millisecond Execution**: Single-threaded ONNX session execution guarantees average inference latency of **$0.38\text{ms}$** (sub-millisecond), eliminating execution lag.
