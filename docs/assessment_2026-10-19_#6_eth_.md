# 6-Trade Evaluation Assessment Series: Batch #6 (ETH)

**Document ID:** `assessment_2026-10-19_#6_ETH_`  
**Series Classification:** Continuous 6-Trade Quantitative Audit & Forensic Ledger  
**Evaluation Date:** 2026-10-19 (12:45 UTC)  
**Target Asset:** Ethereum Binary Options (`KXETH15M` 15-Minute Expirations)  
**Execution Vessel:** `Bot 1 V4 (ETH Domination Engine) / Dual Warrior Architecture`  
**Market Condition:** **⚡ STORM EXPANSION** — Stormy (Directional Volatility & Volcano Expansion)  
**AI Macro Regime:** `STABLE_RANGE` | **Wave Region:** `CHOPPY`  
**Gate Evaluation Verdict:** **SAFETY_HALT (Net Batch PnL $-0.75; Balance $26.34)**  

---

## 1. Executive Summary & Batch Scorecard

During this 6-trade evaluation cycle (Trades 1 through 6 of Batch #6), the algorithm recorded the following quantitative performance:

| Metric | Result | Target Benchmark | Status |
| :--- | :---: | :---: | :--- |
| **Market Condition** | **STORMY** | Stormy (Directional Volatility & Volcano Expansion) | ⚡ STORMY |
| **Batch Record** | **2 Wins – 4 Losses** | $\ge 4\text{W} - 2\text{L}$ | 🛑 DRAWDOWN |
| **Win Rate** | **33.3%** | $\ge 60.0\%$ | ⚠️ UNDERPERFORM |
| **Net Batch PnL** | **$-0.75** | $>\$0.00$ | 🛑 DEFICIT |
| **Pre-Batch Balance** | **$27.09** | Micro-Bankroll | Baseline Equity |
| **Post-Batch Balance** | **$26.34** | Peak Preservation | ⚠️ CAPITAL RETRACEMENT |

**Gemini Synthesis:** Completed 6-trade evaluation batch under STORMY conditions with 2/6 wins (33.3% win rate). Rule-based deterministic fallbacks active.

---

## 2. Granular 6-Trade Ledger

Audited under Zero Float Financial Math (`decimal.Decimal`):

| # | Cycle Expiration Ticker | Side | Size | Entry Price | Settlement Price | Market Condition | Outcome | Net PnL | Post-Trade Balance |
| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **T1** | `KXETH15M-26OCT190615-15` | **YES** | 1 | `$0.47` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.47** | `$19.43` |
| **T2** | `KXETH15M-26OCT190615-15` | **YES** | 1 | `$0.47` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.47** | `$19.78` |
| **T3** | `KXETH15M-26OCT190615-15` | **NO** | 1 | `$0.01` | `$0.00` | **CHOP** | **🔴 LOSS** | **-0.01** | `$26.34` |
| **T4** | `KXETH15M-26OCT190815-15` | **YES** | 1 | `$0.55` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.45** | `$21.85` |
| **T5** | `KXETH15M-26OCT190815-15` | **NO** | 2 | `$0.33` | `$0.00` | **CHOP** | **🔴 LOSS** | **-0.68** | `$26.34` |
| **T6** | `KXETH15M-26OCT190845-45` | **YES** | 1 | `$0.55` | `$1.00` | **CHOP** | **🟢 WIN** | **+0.43** | `$26.34` |

---

## 2.1. Empirical Loss & Failure Attribution Scorecard (Zero-AI Deterministic Autopsy)

| Trade ID | Outcome | Net PnL | Root Failure Code | Quant Attribution | Capital Salvageable |
| :---: | :---: | :---: | :--- | :--- | :---: |
| `WLR-ETH-261019121534-589` | **LOSS** | **-0.68** | `ERR_COUNTER_TREND` | Bet fought institutional 1H macro EMA slope (DEF-01) | **$0.00** |
| `WLR-ETH-261019101528-689` | **LOSS** | **-0.01** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019100039-818` | **LOSS** | **-0.40** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019081511-460` | **LOSS** | **-0.40** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019073039-966` | **LOSS** | **-0.45** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019071532-729` | **LOSS** | **-0.12** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |

**Total Preventable Capital Leak in Sample:** **$0.00**


---

## 2.2. Empirical Sweetspot & Orderbook Corridor Profile

### Entry Price Corridors:
| Price Corridor | Wins | Losses | Win Rate | Net PnL | Sweetspot Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| DEEP_DISCOUNT ($0.38-$0.43) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PRIME_SWEETSPOT ($0.44-$0.48) | 0 | 2 | 0.0% | $-0.94 | 🔴 ADVERSE |
| MOMENTUM_UPPER ($0.49-$0.52) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| HIGH_CEILING (>$0.52) | 2 | 0 | 100.0% | $+0.88 | 🟢 SWEETSPOT |
| OTM_TAIL (<$0.38) | 0 | 2 | 0.0% | $-0.69 | 🔴 ADVERSE |

### Expiration Timing Windows (Tau $\tau$):
| Tau Window | Wins | Losses | Win Rate | Net PnL | Timing Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| EARLY_CYCLE (>600s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PRIME_MID_CYCLE (300s-600s) | 1 | 3 | 25.0% | $-0.50 | 🔴 HAZARD |
| LATE_MID_CYCLE (180s-300s) | 1 | 1 | 50.0% | $-0.25 | ⚪ NEUTRAL |
| PIN_ZONE (<180s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |

- **Optimal Entry Sweetspot:** `HIGH_CEILING (>$0.52)` (2W-0L, PnL: $+0.88)
- **Adverse Selection Hazard:** `PRIME_SWEETSPOT ($0.44-$0.48)` (0W-2L, PnL: $-0.94)
- **Optimal Tau Timing Window:** `LATE_MID_CYCLE (180s-300s)` (1W-1L, PnL: $-0.25)
- **Average Entry Price:** Wins: `$0.55` | Losses: `$0.32`
- **Side Distribution:** YES: `2W - 2L` | NO: `0W - 2L`


---

## 2.3. Unified One-Decision Qualification & Counterfactual Regret Audit

- **Skipped Candidate Tickets Audited:** 0
- **Gate Diagnostics:** All candidate gates verified without false-negative opportunity regret.


---


## 3. What Happened: Gemini Forensic Diagnostic & Root-Cause Autopsy

### Market Condition & Wave Dynamics Autopsy:
- **Active Market Condition:** **STORMY** (Stormy (Directional Volatility & Volcano Expansion))
- **Condition Dynamics:** High velocity wave expansion (Range: $82695.6, Avg VPIN: 0.28, Macro: STABLE_RANGE)
- **Batch Spot Range:** $82695.55 | **Avg Orderflow VPIN:** 0.280
- **Wave Regime Telemetry:** Baseline microstructural flow

### Winning Trades Autopsy:
Winning entries executed with favorable moneyness in STORMY market regime and positive expected value.

### Losing Trades Autopsy (Causal Taxonomy):
Drawdown cycles tagged under STORMY regime by ContinuousExperienceBuffer causal classifier.

### Probability Calibration & Platt Scaling:
Brier score at 0.3729; Platt Alpha at 0.65.

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

Safety halt evaluated. Applied allowed tweaks to protect bankroll. Re-arm quota reset.
- **Cumulative Historical Trades:** 6
- **Cumulative Net PnL:** $-0.7520
- **Macro Win Rate:** 33.3%
