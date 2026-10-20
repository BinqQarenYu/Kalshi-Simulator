# 6-Trade Evaluation Assessment Series: Batch #8 (ETH)

**Document ID:** `assessment_2026-10-19_#8_ETH_`  
**Series Classification:** Continuous 6-Trade Quantitative Audit & Forensic Ledger  
**Evaluation Date:** 2026-10-19 (16:45 UTC)  
**Target Asset:** Ethereum Binary Options (`KXETH15M` 15-Minute Expirations)  
**Execution Vessel:** `Bot 1 V4 (ETH Domination Engine) / Dual Warrior Architecture`  
**Market Condition:** **⚡ STORM EXPANSION** — Stormy (Directional Volatility & Volcano Expansion)  
**AI Macro Regime:** `STABLE_RANGE` | **Wave Region:** `CHOPPY`  
**Gate Evaluation Verdict:** **PASSED (Net Batch PnL $+2.13; Balance $26.34)**  

---

## 1. Executive Summary & Batch Scorecard

During this 6-trade evaluation cycle (Trades 1 through 6 of Batch #8), the algorithm recorded the following quantitative performance:

| Metric | Result | Target Benchmark | Status |
| :--- | :---: | :---: | :--- |
| **Market Condition** | **STORMY** | Stormy (Directional Volatility & Volcano Expansion) | ⚡ STORMY |
| **Batch Record** | **5 Wins – 1 Losses** | $\ge 4\text{W} - 2\text{L}$ | ✅ PASSED |
| **Win Rate** | **83.3%** | $\ge 60.0\%$ | ✅ PASS |
| **Net Batch PnL** | **$+2.13** | $>\$0.00$ | ✅ PROFITABLE |
| **Pre-Batch Balance** | **$24.21** | Micro-Bankroll | Baseline Equity |
| **Post-Batch Balance** | **$26.34** | Peak Preservation | ✅ CAPITAL GAIN |

**Gemini Synthesis:** Completed 6-trade evaluation batch under STORMY conditions with 5/6 wins (83.3% win rate). Rule-based deterministic fallbacks active.

---

## 2. Granular 6-Trade Ledger

Audited under Zero Float Financial Math (`decimal.Decimal`):

| # | Cycle Expiration Ticker | Side | Size | Entry Price | Settlement Price | Market Condition | Outcome | Net PnL | Post-Trade Balance |
| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **T1** | `KXETH15M-26OCT191215-15` | **YES** | 1 | `$0.53` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.47** | `$21.73` |
| **T2** | `KXETH15M-26OCT191215-15` | **NO** | 2 | `$0.32` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.66** | `$26.34` |
| **T3** | `KXETH15M-26OCT191230-30` | **YES** | 1 | `$0.38` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.62** | `$22.81` |
| **T4** | `KXETH15M-26OCT191230-30` | **YES** | 1 | `$0.36` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.62** | `$26.34` |
| **T5** | `KXETH15M-26OCT191245-45` | **YES** | 1 | `$0.45` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.55** | `$23.34` |
| **T6** | `KXETH15M-26OCT191245-45` | **YES** | 1 | `$0.45` | `$1.00` | **STORM** | **🟢 WIN** | **+0.53** | `$26.34` |

---

## 2.1. Empirical Loss & Failure Attribution Scorecard (Zero-AI Deterministic Autopsy)

| Trade ID | Outcome | Net PnL | Root Failure Code | Quant Attribution | Capital Salvageable |
| :---: | :---: | :---: | :--- | :--- | :---: |
| `WLR-ETH-261019161518-482` | **LOSS** | **-0.66** | `ERR_COUNTER_TREND` | Bet fought institutional 1H macro EMA slope (DEF-01) | **$0.00** |
| `WLR-ETH-261019141520-333` | **LOSS** | **-1.21** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019121534-589` | **LOSS** | **-0.68** | `ERR_COUNTER_TREND` | Bet fought institutional 1H macro EMA slope (DEF-01) | **$0.00** |
| `WLR-ETH-261019101528-689` | **LOSS** | **-0.01** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019100039-818` | **LOSS** | **-0.40** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019081511-460` | **LOSS** | **-0.40** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |

**Total Preventable Capital Leak in Sample:** **$0.00**


---

## 2.2. Empirical Sweetspot & Orderbook Corridor Profile

### Entry Price Corridors:
| Price Corridor | Wins | Losses | Win Rate | Net PnL | Sweetspot Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| DEEP_DISCOUNT ($0.38-$0.43) | 1 | 0 | 100.0% | $+0.62 | 🟢 SWEETSPOT |
| PRIME_SWEETSPOT ($0.44-$0.48) | 2 | 0 | 100.0% | $+1.08 | 🟢 SWEETSPOT |
| MOMENTUM_UPPER ($0.49-$0.52) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| HIGH_CEILING (>$0.52) | 1 | 0 | 100.0% | $+0.47 | 🟢 SWEETSPOT |
| OTM_TAIL (<$0.38) | 1 | 1 | 50.0% | $-0.04 | ⚪ NEUTRAL |

### Expiration Timing Windows (Tau $\tau$):
| Tau Window | Wins | Losses | Win Rate | Net PnL | Timing Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| EARLY_CYCLE (>600s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PRIME_MID_CYCLE (300s-600s) | 5 | 1 | 83.3% | $+2.13 | 🟢 SWEETSPOT |
| LATE_MID_CYCLE (180s-300s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PIN_ZONE (<180s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |

- **Optimal Entry Sweetspot:** `PRIME_SWEETSPOT ($0.44-$0.48)` (2W-0L, PnL: $+1.08)
- **Adverse Selection Hazard:** `OTM_TAIL (<$0.38)` (1W-1L, PnL: $-0.04)
- **Optimal Tau Timing Window:** `PRIME_MID_CYCLE (300s-600s)` (5W-1L, PnL: $+2.13)
- **Average Entry Price:** Wins: `$0.43` | Losses: `$0.32`
- **Side Distribution:** YES: `5W - 0L` | NO: `0W - 1L`


---

## 2.3. Unified One-Decision Qualification & Counterfactual Regret Audit

- **Skipped Candidate Tickets Audited:** 0
- **Gate Diagnostics:** All candidate gates verified without false-negative opportunity regret.


---


## 3. What Happened: Gemini Forensic Diagnostic & Root-Cause Autopsy

### Market Condition & Wave Dynamics Autopsy:
- **Active Market Condition:** **STORMY** (Stormy (Directional Volatility & Volcano Expansion))
- **Condition Dynamics:** High velocity wave expansion (Range: $81942.0, Avg VPIN: 0.22, Macro: STABLE_RANGE)
- **Batch Spot Range:** $81942.03 | **Avg Orderflow VPIN:** 0.217
- **Wave Regime Telemetry:** Baseline microstructural flow

### Winning Trades Autopsy:
Winning entries executed with favorable moneyness in STORMY market regime and positive expected value.

### Losing Trades Autopsy (Causal Taxonomy):
Drawdown cycles tagged under STORMY regime by ContinuousExperienceBuffer causal classifier.

### Probability Calibration & Platt Scaling:
Brier score at 0.3703; Platt Alpha at 0.65.

---

## 4. What Changes Triggered: Allowed Parameter Tweaks & Evolution

- **Allowed Tweaks Applied:** None
- **Tuning Rationale:** Maintained baseline parameters within council bounds for STORMY market conditions.

### Operational Guardrails Enforced:
1. **Zero Float Financial Math Law:** All balance increments, PnL calculations, and limit entries strictly processed in `decimal.Decimal`.
2. **1-Trade-Per-Cycle Invariant:** The bot maintained strict single-order occupancy, eliminating wash trading and self-competition.
3. **Continuous Experience Recalibration:** Online Platt Sigmoid Scaling dynamically recalibrated after every settled cycle.

---

## 5. Council Directives for Subsequent Batch

Grant auto-extension for Batch #9. Bot remains armed for live execution.
- **Cumulative Historical Trades:** 12
- **Cumulative Net PnL:** $0.9223
- **Macro Win Rate:** 66.7%
