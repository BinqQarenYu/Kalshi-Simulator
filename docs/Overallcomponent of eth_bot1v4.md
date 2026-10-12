# Institutional System Architecture: ETH Bot 1 V4 (QuoLas) Complete Decision & Component Breakdown

**Document Name:** `Overallcomponent of eth_bot1v4.md`
**Classification:** Quantitative Trading Infrastructure & Signal Processing Hierarchy
**Asset Target:** Kalshi Ethereum Binary Options (`KXETH15M` 15‑Minute Expirations)
**Execution Vessel:** `ETH Bot 1 V4 (Domination Engine) / Dual Warrior Architecture`
**Environment:** Local PC Live Daemon (`kalshi-eth-quolas.service` – runs on user workstation, not AWS)
**Mathematical Standard:** Strict Zero Float Financial Math (`decimal.Decimal`)

---

## Executive Summary

ETH Bot 1 V4 ("QuoLas") mirrors the Bitcoin‑centric Bot 1 V4 architecture but operates on the Ethereum binary‑options market. All decision pipelines – machine‑learning models, micro‑structure filters, real‑time regime classifiers, cycle‑timing gates, and strictly bounded Expected‑Value (EV) math – are retained. The only differences are asset‑specific configuration values (volatility, spot‑diff thresholds) and model files tuned for ETH.

If **any single component** in the pipeline flags an anomaly, toxicity, frozen liquidity, or negative expected value, the decision instantly resolves to `WAIT` (`recommended_contracts = 0`).

```mermaid
flowchart TD
    MarketData["Binance ETH Spot + Kalshi L2 CLOB Feeds"] --> Tier1_3
    subgraph Tier1_3 ["Tier 1 & Tier 3: Microstructure & Liquidity Shields"]
        M1["Max Turnover Cap (1 Trade/Cycle)"]
        M2["Frozen Sensor / Dead Book Veto"]
        M3["VPIN Toxicity Veto (VPIN < 0.65)"]
        M4["CLOB Spread Corridor Cap (< $0.05)"]
    end
    Tier1_3 --> Intelligence
    subgraph Intelligence ["Tier 1: Machine Learning & Intelligence Models"]
        ONNX["eth_quolas.onnx (Microstructural Neural Softmax)"]
        HMM["ETH HMMBrain (5m Gaussian Markov Macro Regime)"]
        EXP["ContinuousExperienceBuffer (Quadrant Mistake Pruning)"]
        Bayes["Bayesian Fusion Core (P_win Posterior)"]
    end
    Intelligence --> Selector
    subgraph Selector ["Tier 2: Real‑Time Regime Routing (One Boat, Two Warriors)"]
        RegimeDetect{"detect_market_regime"}
        W1["Warrior 1: Storm Hunter (Breakout / Kelly Limit $0.48-$0.55)"]
        W2["Warrior 2: Chop Harvester ($0.38-$0.42 Maker / 150s-450s)"]
    end
    RegimeDetect --|STORM| W1
    RegimeDetect --|CHOP| W2
    W1 --> ExecutionGates
    W2 --> ExecutionGates
    subgraph ExecutionGates ["Tier 4 & Tier 5: Execution Gates & EV Sizing"]
        G1["Opening Quarantine (T ≤ 780s) & Late Pin Freeze"]
        G2["Dynamic Proximity Moat (|Spot - Strike| ≥ Moat)"]
        G3["ONNX Consensus Veto (WAIT ≥ 70% Guard)"]
        G4["Statistical EV Hurdle (Net EV ≥ +$0.02)"]
        G5["Micro‑Bankroll Sizing (Max 1 Contract)"]
    end
    ExecutionGates --> Order["Kalshi Live REST Orderbook Dispatch"]
```

---

## Detailed Component Catalog

### 1. Tier 1: Machine Learning & Probabilistic Intelligence Models

1. **`ContinuousExperienceBuffer` (Empirical Online Learning Engine)**
   * **Location:** [`src/kalshi_sim/ml/continuous_experience.py`](file:///F:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/continuous_experience.py)
   * **Role:** Dynamic online self‑sharpening buffer updated in RAM and persisted to disk after every settled trade.
   * **Decision Responsibilities:**
     * Mistake Quadrant Pruner – vetoes entries when time‑to‑expiry ($T$) and strike separation ($\Delta P$) fall into an empirically unprofitable quadrant.
     * Online Platt Sigmoid Recalibration – updates calibration scalars ($A, B$) using walk‑forward settlement outcomes.

2. **`eth_quolas.onnx` (Low‑Latency Deep Microstructure Model for ETH)**
   * **Location:** [`models/eth_quolas.onnx`](file:///F:/012D_TRADE/Kalshi%20Simulator/models/eth_quolas.onnx) *(placeholder – replace with trained ETH model)*
   * **Role:** High‑frequency neural network evaluated via ONNX Runtime on L2 order‑book delta, micro‑price velocity, and trade imbalance for ETH.
   * **Decision Responsibilities:**
     * Outputs 3‑class softmax vector: `[P(UP), P(DOWN), P(WAIT)]`.
     * Provides micro‑structural confidence and flags informed toxic order flow.

3. **`ETH HMMBrain` (Gaussian Hidden Markov Model / 5m Macro Regime for ETH)**
   * **Location:** [`src/kalshi_sim/ml/eth_bot1v4/hmm_brain.py`](file:///F:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/eth_bot1v4/hmm_brain.py)
   * **Role:** Continuous 30‑second background Markov chain analyzing Binance 5‑minute OHLCV candles for ETH.
   * **Decision Responsibilities:**
     * Classifies macro state into `BULL_MOMENTUM`, `BEAR_MOMENTUM`, or `STABLE_RANGE`.
     * Enforces **HMM RISK_OFF Veto** – suppresses directional trading if macro transition volatility spikes.

4. **`Bayesian Fusion Core` (Macro Normal Erf × Micro ONNX)**
   * **Location:** [`src/kalshi_sim/ml/eth_bot1v4/eth_bot1_v4_engine.py`](file:///F:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/eth_bot1v4/eth_bot1_v4_engine.py#L420-L460)
   * **Role:** Blends macro physical probability (Gaussian CDF / error function `math.erf`) with micro‑structural ONNX predictions.
   * **Decision Responsibilities:**
     * Computes calibrated posterior win probabilities: $P_{\text{win}}(\text{YES})$ and $P_{\text{win}}(\text{NO})$.

---

### 2. Tier 2: Real‑Time Market Regime Classifier (One Boat, Two Warriors)

5. **`detect_market_regime` (Warrior Selector)**
   * **Role:** Evaluates live 15‑minute cycle range ($\Delta P_{\text{cycle}}$), 1s/3s spot velocity, and order‑book VPIN.
   * **Decision Responsibilities:** Dynamically switches the engine mode between **Warrior 1 (Storm Hunter)** and **Warrior 2 (Chop Harvester)**.

6. **`Warrior 1: Storm Hunter` (Momentum & Breakout Specialist)**
   * **Active Regime:** `STORM` – volatile, directional trending market.
   * **Decision Responsibilities:**
     * Captures momentum, breakout surges, and trend continuation.
     * Operates dynamic limit pricing up to $\$0.48 - \$0.55$ when edge is confirmed.

7. **`Warrior 2: Chop Harvester` (Deep‑Discount Mean‑Reversion Specialist)**
   * **Active Regime:** `CHOP` – ranging, oscillating compression market.
   * **Decision Responsibilities:**
     * Restricts execution to the **$150\text{s} \le T \le 450\text{s}$** window (waits for boundaries to establish, freezes before late‑cycle pin risk).
     * Enforces asymmetric deep‑discount maker entries: **$\$0.38 - \$0.42$** (delivering an asymmetric $1\!:\!1.8+$ risk‑to‑reward payoff).

---

### 3. Tier 3: Microstructure & Liquidity Safety Vetoes

8. **`Frozen Sensor / Dead Book Veto`** – blocks trading when order‑book variance collapses or ONNX predicts `WAIT` ≥ 0.99.

9. **`VPIN Toxicity Veto`** – blocks trading when $\text{VPIN} \ge 0.65$ or the ONNX model signals high toxicity.

10. **`CLOB Spread Corridor Cap`** – rejects orders when spread $> \$0.05$.

11. **`ONNX Consensus Team Gate`** – requires ONNX `WAIT` confidence < 70 % to allow directional trades.

---

### 4. Tier 4: Cycle Timing & Spatial Geometry Gates

12. **`Opening Cycle Noise Quarantine Gate`** – silences trading for the first 120 s ($T > 780\text{s}$).

13. **`Late‑Cycle Pin Freeze Gate`** – blocks entries close to settlement (\$T < 150\text{s}$ in Chop regime).

14. **`Dynamic Proximity Moat Filter`** – calculates a volatility‑scaled minimum distance; vetoes orders that are too close to the strike, using ETH‑specific `min_spot_diff` derived from live volatility and the ETH asset config.

15. **`Max Turnover Cap`** – enforces the 1‑Trade‑Per‑Cycle invariant.

---

### 5. Tier 5: Quantitative EV & Position Sizing Engine

16. **`StatisticalEVEngine` & Minimum EV Hurdle Gate**
    * **Formula:** $\text{EV} = P_{\text{win}} \times \$1.00 - \text{LimitPrice} - \text{ExchangeFeeBuffer}$
    * **Gate:** Blocks entry unless $\text{EV} \ge +\$0.02$ to $+\$0.04$.

17. **`Kelly Sizing & Conviction Tier Engine`**
    * **Formula:** Fractional Kelly ($\frac{1}{4}$ Kelly) × Conviction Score × Star Player Seal.
    * **Gate:** Allocates position sizing – strictly **1 contract max** under the micro‑bankroll capital‑preservation law.

---

## Asset‑Specific Configuration (ETH)

| Parameter | BTC Default | ETH Adaptation |
|-----------|--------------|----------------|
| `typical_1m_volatility` | 14.0 | **≈ 8.5** (derived from recent ETH 1‑minute vol) |
| `min_spot_diff` | 25.0 | **≈ 12.0**, dynamically scaled by live ETH volatility (see `lead_deer_quant_brain` scaling logic) |
| Model files | `models/quolas.onnx`, `models/hmm_latest.pkl` | `models/eth_quolas.onnx`, `models/eth_hmm_latest.pkl` |

All ETH‑specific numeric constants are stored in `src/kalshi_sim/ml/quolas_core/config.py` under `CryptoAsset.ETH` and are applied at runtime via `get_asset_config`.

---

## Component Matrix Reference Table (ETH)

| # | Component Name | Module File | Decision Power | Type |
|---|----------------|-------------|----------------|------|
| **1** | `ContinuousExperienceBuffer` | `ml/continuous_experience.py` | Quadrant Pruning & Platt Calibration | ML / Adaptive Memory |
| **2** | `eth_quolas.onnx` | `models/eth_quolas.onnx` | L2 Imbalance Softmax & Confidence | ML / Deep Neural Net |
| **3** | `ETH HMMBrain` | `ml/eth_bot1v4/hmm_brain.py` | 5m Macro Regime & RISK_OFF Veto | ML / Markov Model |
| **4** | `Bayesian Fusion Core` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Blended $P_{\text{win}}$ Posterior | Probabilistic Engine |
| **5** | `detect_market_regime` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | STORM vs. CHOP Routing | Dynamic Classifier |
| **6** | `Warrior 1: Storm Hunter` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Momentum & Breakout Execution | Execution Module |
| **7** | `Warrior 2: Chop Harvester` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Deep‑Discount Maker ($0.38 - $0.42) | Execution Module |
| **8** | `Frozen Sensor Veto` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Zero‑Variance Orderbook Shield | Safety Veto |
| **9** | `VPIN Toxicity Veto` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Toxic Order Flow Shield ($\ge 0.65$) | Safety Veto |
| **10** | `CLOB Spread Corridor Cap` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Spread Width Gate ($>\$0.05$) | Liquidity Gate |
| **11** | `ONNX Consensus Team Gate` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Neural Net Veto Override ($\ge 70\%$) | Consensus Gate |
| **12** | `Opening Noise Quarantine` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | First 120s Cycle Shield ($T > 780\text{s}$) | Timing Gate |
| **13** | `Late Pin Freeze Gate` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Near‑Settlement Protection ($T < 150\text{s}$) | Timing Gate |
| **14** | `Dynamic Proximity Moat` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | Minimum Volatility Distance | Spatial Filter |
| **15** | `Max Turnover Cap` | `ml/eth_bot1v4/eth_bot1_v4_engine.py` | 1‑Trade‑Per‑Cycle Lock | Risk Limit |
| **16** | `StatisticalEVEngine` | `ml/statistical_ev.py` | Net Expected Value Hurdle ($>+\$0.02$) | Quantitative Gate |
| **17** | `Kelly Sizing Engine` | `ml/statistical_ev.py` | Micro‑Bankroll Sizing (1 Contract Max) | Capital Preservation |

---

*Generated autonomously and archived under the Kalshi Simulator Quantitative Documentation Series (ETH variant).*
