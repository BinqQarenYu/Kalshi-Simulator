# Quantitative Strategy Bots & Algorithmic Engines

The simulator features four state-of-the-art quantitative trading bots running concurrently against live market feeds.

## 📚 Quantitative Strategy Documentation Index

Detailed specifications, mathematical models, configuration settings, buy/sell entry conditions, stop-loss/take-profit rules, and risk management parameters for each strategy bot:

- [🤖 Bot 1: 3-Step Domination Bot (`1.md` / `1_THREE_STEP_DOMINATION_BOT.md`)](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/1_THREE_STEP_DOMINATION_BOT.md)
- [🎯 Bot 2: Dominion 2 Bot (`2.md` / `2_DOMINION_2_BOT.md`)](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/2_DOMINION_2_BOT.md)
- [📈 Bot 3: Macro Trend Dominion Bot (`3.md` / `3_MACRO_TREND_DOMINION_BOT.md`)](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/3_MACRO_TREND_DOMINION_BOT.md)
- [🧠 Bot 4: ONNX Microstructure Neural Net Bot (`4.md` / `4_ONNX_MICROSTRUCTURE_BOT.md`)](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/4_ONNX_MICROSTRUCTURE_BOT.md)

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

For complete rules, parameters, and exit triggers, see [docs/1_THREE_STEP_DOMINATION_BOT.md](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/1_THREE_STEP_DOMINATION_BOT.md).

---

## 🎯 2. The Dominion 2 Bot (`Dominion2Bot`)

The **Dominion 2 Bot** (Anti-Pin Asymmetric Scalper Engine) targets high-payout discount contracts ($0.25 - $0.45) while actively shielding capital against late-cycle price pinning near the strike price.

For complete rules, parameters, anti-pin guardrails, and salvage triggers, see [docs/2_DOMINION_2_BOT.md](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/2_DOMINION_2_BOT.md).

---

## 📈 3. The Macro Trend Dominion Bot (`MacroTrendDominionBot`)

The **Macro Trend Dominion Bot** eliminates fighting active macro trends during Bitcoin bull/bear trend expansions by classifying 1-hour and 15-minute spot regimes and fusing Bayesian ONNX order flow predictions.

For complete rules, parameters, regime gates, and loss salvage rules, see [docs/3_MACRO_TREND_DOMINION_BOT.md](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/3_MACRO_TREND_DOMINION_BOT.md).

---

## 🧠 4. The ONNX Microstructure Neural Net Bot (`KalshiONNXEngine`)

The **ONNX Microstructure Bot** extracts a 28-dimensional feature tensor from the L2 CLOB on every orderbook update, runs deep learning inference via ONNX Runtime CPU, and calculates exact digital option Expected Value ($\mathbb{E}[V]$).

For complete rules, 28-D feature matrix, VPIN taper formula, and Kelly sizing, see [docs/4_ONNX_MICROSTRUCTURE_BOT.md](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/4_ONNX_MICROSTRUCTURE_BOT.md).

---

## 🛡️ Risk Management & Capital Allocation Summary

### 1. Fractional Kelly Criterion ($0.15 \cdot f^*$)
$$f^* = \frac{p \cdot b - (1 - p)}{b} = \frac{p - \text{Ask}}{1 - \text{Ask}}$$
$$\text{Micro-Allocation (Contracts)} = \min\left( Q_{\max}, \frac{\text{Equity} \times \text{MaxRiskPct} \times (0.15 \cdot f^*)}{\text{Ask} + \text{Fee}} \right)$$

For a realistic **$15.00 – $30.00 bankroll**, contract sizing is capped at **1–2 contracts** ($0.50 – $1.50 per trade), preventing catastrophic drawdowns.

### 2. VPIN Toxicity Veto & Continuous Taper
If VPIN exceeds the toxicity threshold ($\text{VPIN} > 0.60$), new order entries are automatically vetoed or continuously tapered.

### 3. Drawdown Circuit Breaker
If cumulative portfolio drawdown exceeds **$15\%$**, the circuit breaker trips, immediately halting all automated execution until manual review or reset.
