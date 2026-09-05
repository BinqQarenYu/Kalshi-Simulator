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
 │  • Confidence thresholding (>= 70% directional confidence)  │
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
 │  • Requires Min Edge >= 3.0% and Net EV >= $0.02/ct          │
 │  • VPIN Taper: Scales size 1.0 -> 0.0 in warning band        │
 │  • Fractional Kelly Sizing: f* = (P*b - (1-P))/b (15% Kelly)│
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
                 [ Virtual Order Execution ]
```

---

## 3. Configuration Settings & Hyperparameters

### Stage 1: ONNX Inference Engine (`KalshiONNXEngine`)

| Parameter | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `CONFIDENCE_THRESHOLD` | `float` | `0.70` (70%) | AI must be 70%+ confident to fire directional signal |
| `VPIN_OVERRIDE_THRESHOLD`| `float` | `0.75` | Hard VPIN risk cutoff override |
| `model_path` | `Path` | `"models/nano_microscope_overhauled.onnx"` | Trained ONNX neural network path |
| `stats_path` | `Path` | `"models/feature_stats.json"` | Z-Score mean and standard deviation normalization parameters |

### Stage 2: Mathematical EV & Kelly Engine (`StatisticalEVEngine`)

| Parameter | Type | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `min_ev_threshold` | `Decimal` | `Decimal("0.02")` | Minimum net Expected Value ($0.02/contract) required |
| `min_edge_pct` | `float` | `0.03` (3.0%) | Minimum statistical edge required post-fee |
| `fee_per_contract` | `Decimal` | `Decimal("0.01")` | Exchange taker fee per contract ($0.01) |
| `fractional_kelly` | `float` | `0.15` (15%) | Fractional Kelly multiplier for capital preservation |
| `max_portfolio_risk_pct`| `Decimal` | `Decimal("0.05")` | Maximum percentage of portfolio equity at risk per trade (5%) |
| `vpin_safe_threshold` | `float` | `0.35` | Safe VPIN threshold for full Kelly sizing |
| `vpin_warn_threshold` | `float` | `0.50` | VPIN warning threshold initiating sizing taper |
| `vpin_toxic_threshold` | `float` | `0.60` | Maximum VPIN threshold triggering complete trade suppression |

---

## 4. 28-Dimensional Microstructure Feature Vector

| Index | Feature Symbol | Description | Formula / Normalization |
| :---: | :--- | :--- | :--- |
| `0` | `spread_bps` | Inside Touch Bounded Spread | $\max(0.001, \min(0.25, \text{Ask} - \text{Bid}))$ |
| `1` | `ofi_l1` | Top-of-Book Order Flow Imbalance | $\frac{B_1 - A_1}{B_1 + A_1 + \epsilon}$ |
| `2` | `ofi_l5` | Level 1-5 Order Flow Imbalance | $\frac{\sum_{i=1}^5 B_i - \sum_{i=1}^5 A_i}{\sum_{i=1}^5 B_i + \sum_{i=1}^5 A_i + \epsilon}$ |
| `3` | `ofi_l15` | Full Depth Order Flow Imbalance | $\frac{\sum B_i - \sum A_i}{\sum B_i + \sum A_i + \epsilon}$ |
| `4` | `cvd_norm` | Cumulative Volume Delta (Normalized) | $\frac{\sum (\text{Signed Trade Qty})}{\text{Baseline Volume}}$ |
| `5` | `entropy` | Trade Size Shannon Entropy | $-\sum p_i \log_2(p_i)$ over rolling trade window |
| `6` | `vpin_score` | Volume-Synchronized Probability of Toxicity | PBC algorithm over volume buckets |
| `7` | `spoof_mag_bid` | Bid Depth Spoofing / Pulling Metric | Weighted outer-layer queue cancellations |
| `8` | `spoof_mag_ask` | Ask Depth Spoofing / Pulling Metric | Weighted outer-layer queue cancellations |
| `9` | `bid_absorption`| Touch Absorption Volume (Bid) | Passive liquidity consumed without price change |
| `10`| `ask_absorption`| Touch Absorption Volume (Ask) | Passive liquidity consumed without price change |
| `11`| `whale_tx` | Institutional Block Trade Counter | Trades exceeding dynamic volume threshold |
| `12`| `layering_index`| Outer vs. Inner Book Density Ratio | $\frac{\text{Volume}(L_6 \dots L_{15})}{\text{Volume}(L_1 \dots L_5) + \epsilon}$ |
| `13–27`| `spatial_0..14`| Exponential Decay Depth Imbalance | $e^{-\alpha i} \cdot \left( \frac{B_i - A_i}{\text{Baseline Volume}} \right)$ for $i=0 \dots 14$ |

---

## 5. Buy / Sell Entry Conditions & Trigger Points

### Entry Trigger Criteria
A trade entry is triggered if **ALL** of the following conditions pass simultaneously:
1. **AI Confidence Gate**: ONNX Stage 1 model predicts directional signal with confidence $\ge 70.0\%$.
2. **Positive Net EV**: Net $\mathbb{E}[V] \ge +\$0.02$ per contract post-fee ($0.01/ct).
3. **Statistical Edge**: Statistical edge $\alpha \ge 3.0\%$ post-fee.
4. **VPIN Safety Gate**: Order flow toxicity VPIN score $< 0.60$.

---

## 6. Capital Allocation & Risk Management

1. **Fractional Kelly Criterion ($0.15 \cdot f^*$)**:
   $$b = \frac{1.00 - \text{Ask}_{\text{effective}}}{\text{Ask}_{\text{effective}}}, \quad f^* = \frac{p \cdot b - (1 - p)}{b}$$
   $$\text{Contract Size} = \min\left(Q_{\max}, \frac{\text{Equity} \times 0.05 \times (0.15 \cdot f^*)}{\text{Ask} + \text{Fee}}\right)$$
2. **VPIN Sizing Taper**:
   - If $\text{VPIN} \le 0.35$: Full Kelly sizing multiplier ($1.0$).
   - If $0.35 < \text{VPIN} \le 0.60$: Continuous linear size taper $1.0 \to 0.0$.
   - If $\text{VPIN} > 0.60$: Complete trade suppression ($0$ contracts).
3. **Daily Circuit Breaker**: Auto-trips and halts trading if cumulative drawdown exceeds **15%**.
