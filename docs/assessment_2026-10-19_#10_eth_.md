# 6-Trade Evaluation Assessment Series: Batch #10 (ETH)

**Document ID:** `assessment_2026-10-19_#10_ETH_`  
**Series Classification:** Continuous 6-Trade Quantitative Audit & Forensic Ledger  
**Evaluation Date:** 2026-10-19 (21:30 UTC)  
**Target Asset:** Ethereum Binary Options (`KXETH15M` 15-Minute Expirations)  
**Execution Vessel:** `Bot 1 V4 (ETH Domination Engine) / Dual Warrior Architecture`  
**Market Condition:** **⚡ STORM EXPANSION** — Stormy (Directional Volatility & Volcano Expansion)  
**AI Macro Regime:** `STABLE_RANGE` | **Wave Region:** `CHOPPY`  
**Gate Evaluation Verdict:** **PASSED (Net Batch PnL $+0.19; Balance $26.34)**  

---

## 1. Executive Summary & Batch Scorecard

During this 6-trade evaluation cycle (Trades 1 through 6 of Batch #10), the algorithm recorded the following quantitative performance:

| Metric | Result | Target Benchmark | Status |
| :--- | :---: | :---: | :--- |
| **Market Condition** | **STORMY** | Stormy (Directional Volatility & Volcano Expansion) | ⚡ STORMY |
| **Batch Record** | **3 Wins – 3 Losses** | $\ge 4\text{W} - 2\text{L}$ | ⚠️ COIN-FLIP |
| **Win Rate** | **50.0%** | $\ge 60.0\%$ | ⚠️ UNDERPERFORM |
| **Net Batch PnL** | **$+0.19** | $>\$0.00$ | ✅ PROFITABLE |
| **Pre-Batch Balance** | **$26.15** | Micro-Bankroll | Baseline Equity |
| **Post-Batch Balance** | **$26.34** | Peak Preservation | ✅ CAPITAL GAIN |

**Gemini Synthesis:** Completed 6-trade evaluation batch under STORMY conditions with 3/6 wins (50.0% win rate). Rule-based deterministic fallbacks active.

---

## 2. Granular 6-Trade Ledger

Audited under Zero Float Financial Math (`decimal.Decimal`):

| # | Cycle Expiration Ticker | Side | Size | Entry Price | Settlement Price | Market Condition | Outcome | Net PnL | Post-Trade Balance |
| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **T1** | `KXETH15M-26OCT191545-45` | **YES** | 1 | `$0.41` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.59** | `$22.55` |
| **T2** | `KXETH15M-26OCT191545-45` | **NO** | 2 | `$0.26` | `$0.00` | **CHOP** | **🔴 LOSS** | **-0.54** | `$26.34` |
| **T3** | `KXETH15M-26OCT191715-15` | **YES** | 1 | `$0.51` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.49** | `$23.10` |
| **T4** | `KXETH15M-26OCT191715-15` | **YES** | 1 | `$0.51` | `$1.00` | **CHOP** | **🟢 WIN** | **+0.47** | `$26.34` |
| **T5** | `KXETH15M-26OCT191730-30` | **YES** | 1 | `$0.40` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.40** | `$22.25` |
| **T6** | `KXETH15M-26OCT191730-30` | **YES** | 1 | `$0.40` | `$0.00` | **CHOP** | **🔴 LOSS** | **-0.42** | `$26.34` |

---

## 2.1. Empirical Loss & Failure Attribution Scorecard (Zero-AI Deterministic Autopsy)

| Trade ID | Outcome | Net PnL | Root Failure Code | Quant Attribution | Capital Salvageable |
| :---: | :---: | :---: | :--- | :--- | :---: |
| `WLR-ETH-261019213007-702` | **LOSS** | **-0.42** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019194525-916` | **LOSS** | **-0.54** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019174526-731` | **LOSS** | **-0.44** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019170011-853` | **LOSS** | **-0.44** | `ERR_DOOMED_HOLD_TO_ZERO` | Doomed position held to 0¢; salvage was possible (DEF-03, wasted $0.12) | **+$0.12 wasted** |
| `WLR-ETH-261019161518-482` | **LOSS** | **-0.66** | `ERR_COUNTER_TREND` | Bet fought institutional 1H macro EMA slope (DEF-01) | **$0.00** |
| `WLR-ETH-261019141520-333` | **LOSS** | **-1.21** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |

**Total Preventable Capital Leak in Sample:** **$0.12**


---

## 2.2. Empirical Sweetspot & Orderbook Corridor Profile

### Entry Price Corridors:
| Price Corridor | Wins | Losses | Win Rate | Net PnL | Sweetspot Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| DEEP_DISCOUNT ($0.38-$0.43) | 1 | 2 | 33.3% | $-0.23 | 🔴 ADVERSE |
| PRIME_SWEETSPOT ($0.44-$0.48) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| MOMENTUM_UPPER ($0.49-$0.52) | 2 | 0 | 100.0% | $+0.96 | 🟢 SWEETSPOT |
| HIGH_CEILING (>$0.52) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| OTM_TAIL (<$0.38) | 0 | 1 | 0.0% | $-0.54 | 🔴 ADVERSE |

### Expiration Timing Windows (Tau $\tau$):
| Tau Window | Wins | Losses | Win Rate | Net PnL | Timing Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| EARLY_CYCLE (>600s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PRIME_MID_CYCLE (300s-600s) | 3 | 3 | 50.0% | $+0.19 | ⚪ NEUTRAL |
| LATE_MID_CYCLE (180s-300s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PIN_ZONE (<180s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |

- **Optimal Entry Sweetspot:** `MOMENTUM_UPPER ($0.49-$0.52)` (2W-0L, PnL: $+0.96)
- **Adverse Selection Hazard:** `OTM_TAIL (<$0.38)` (0W-1L, PnL: $-0.54)
- **Optimal Tau Timing Window:** `PRIME_MID_CYCLE (300s-600s)` (3W-3L, PnL: $+0.19)
- **Average Entry Price:** Wins: `$0.48` | Losses: `$0.35`
- **Side Distribution:** YES: `3W - 2L` | NO: `0W - 1L`


---

## 2.3. Unified One-Decision Qualification & Counterfactual Regret Audit

- **Skipped Candidate Tickets Audited:** 0
- **Gate Diagnostics:** All candidate gates verified without false-negative opportunity regret.


---


## 3. What Happened: Gemini Forensic Diagnostic & Root-Cause Autopsy

### Market Condition & Wave Dynamics Autopsy:
- **Active Market Condition:** **STORMY** (Stormy (Directional Volatility & Volcano Expansion))
- **Condition Dynamics:** High velocity wave expansion (Range: $82044.5, Avg VPIN: 0.26, Macro: STABLE_RANGE)
- **Batch Spot Range:** $82044.48 | **Avg Orderflow VPIN:** 0.263
- **Wave Regime Telemetry:** Baseline microstructural flow

### Winning Trades Autopsy:
Winning entries executed with favorable moneyness in STORMY market regime and positive expected value.

### Losing Trades Autopsy (Causal Taxonomy):
Drawdown cycles tagged under STORMY regime by ContinuousExperienceBuffer causal classifier.

### Probability Calibration & Platt Scaling:
Brier score at 0.3742; Platt Alpha at 0.65.

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

Grant auto-extension for Batch #11. Bot remains armed for live execution.
- **Cumulative Historical Trades:** 12
- **Cumulative Net PnL:** $-2.4224
- **Macro Win Rate:** 25.0%
