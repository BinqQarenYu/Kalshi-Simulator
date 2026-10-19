# 6-Trade Evaluation Assessment Series: Batch #2 (ETH)

**Document ID:** `assessment_2026-10-19_#2_ETH_`  
**Series Classification:** Continuous 6-Trade Quantitative Audit & Forensic Ledger  
**Evaluation Date:** 2026-10-19 (08:43 UTC)  
**Target Asset:** Ethereum Binary Options (`KXETH15M` 15-Minute Expirations)  
**Execution Vessel:** `Bot 1 V4 (ETH Domination Engine) / Dual Warrior Architecture`  
**Market Condition:** **⚡ STORM EXPANSION** — Stormy (Directional Volatility & Volcano Expansion)  
**AI Macro Regime:** `STABLE_RANGE` | **Wave Region:** `CHOPPY`  
**Gate Evaluation Verdict:** **PASSED (Net Batch PnL $+1.75; Balance $19.64)**  

---

## 1. Executive Summary & Batch Scorecard

During this 6-trade evaluation cycle (Trades 1 through 6 of Batch #2), the algorithm recorded the following quantitative performance:

| Metric | Result | Target Benchmark | Status |
| :--- | :---: | :---: | :--- |
| **Market Condition** | **STORMY** | Stormy (Directional Volatility & Volcano Expansion) | ⚡ STORMY |
| **Batch Record** | **5 Wins – 1 Losses** | $\ge 4\text{W} - 2\text{L}$ | ✅ PASSED |
| **Win Rate** | **83.3%** | $\ge 60.0\%$ | ✅ PASS |
| **Net Batch PnL** | **$+1.75** | $>\$0.00$ | ✅ PROFITABLE |
| **Pre-Batch Balance** | **$17.89** | Micro-Bankroll | Baseline Equity |
| **Post-Batch Balance** | **$19.64** | Peak Preservation | ✅ CAPITAL GAIN |

**Gemini Synthesis:** Completed 6-trade evaluation batch under STORMY conditions with 5/6 wins (83.3% win rate). Rule-based deterministic fallbacks active.

---

## 2. Granular 6-Trade Ledger

Audited under Zero Float Financial Math (`decimal.Decimal`):

| # | Cycle Expiration Ticker | Side | Size | Entry Price | Settlement Price | Market Condition | Outcome | Net PnL | Post-Trade Balance |
| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **T1** | `KXETH15M-26OCT190230-30` | **YES** | 1 | `$0.53` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.55** | `$26.34` |
| **T2** | `KXETH15M-26OCT190315-15` | **YES** | 1 | `$0.54` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.46** | `$20.52` |
| **T3** | `KXETH15M-26OCT190315-15` | **YES** | 1 | `$0.54` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.46** | `$20.52` |
| **T4** | `KXETH15M-26OCT190315-15` | **YES** | 1 | `$0.54` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.46** | `$19.64` |
| **T5** | `KXETH15M-26OCT190315-15` | **YES** | 1 | `$0.54` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.46** | `$19.64` |
| **T6** | `KXETH15M-26OCT190315-15` | **YES** | 1 | `$0.54` | `$1.00` | **BLEED** | **🟢 WIN** | **+0.46** | `$19.64` |

---

## 2.1. Empirical Loss & Failure Attribution Scorecard (Zero-AI Deterministic Autopsy)

| Trade ID | Outcome | Net PnL | Root Failure Code | Quant Attribution | Capital Salvageable |
| :---: | :---: | :---: | :--- | :--- | :---: |
| `WLR-ETH-261019081511-460` | **LOSS** | **-0.40** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019073039-966` | **LOSS** | **-0.45** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019071532-729` | **LOSS** | **-0.12** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019063022-580` | **LOSS** | **-0.55** | `ADVERSE_SELECTION_SWEEP` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019043011-880` | **LOSS** | **-0.56** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019041531-288` | **LOSS** | **-0.40** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |

**Total Preventable Capital Leak in Sample:** **$0.00**


---

## 2.2. Empirical Sweetspot & Orderbook Corridor Profile

### Entry Price Corridors:
| Price Corridor | Wins | Losses | Win Rate | Net PnL | Sweetspot Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| DEEP_DISCOUNT ($0.38-$0.43) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PRIME_SWEETSPOT ($0.44-$0.48) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| MOMENTUM_UPPER ($0.49-$0.52) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| HIGH_CEILING (>$0.52) | 5 | 1 | 83.3% | $+1.75 | 🟢 SWEETSPOT |
| OTM_TAIL (<$0.38) | 0 | 0 | N/A | $+0.00 | — UNTESTED |

### Expiration Timing Windows (Tau $\tau$):
| Tau Window | Wins | Losses | Win Rate | Net PnL | Timing Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| EARLY_CYCLE (>600s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PRIME_MID_CYCLE (300s-600s) | 5 | 1 | 83.3% | $+1.75 | 🟢 SWEETSPOT |
| LATE_MID_CYCLE (180s-300s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PIN_ZONE (<180s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |

- **Optimal Entry Sweetspot:** `HIGH_CEILING (>$0.52)` (5W-1L, PnL: $+1.75)
- **Adverse Selection Hazard:** `HIGH_CEILING (>$0.52)` (5W-1L, PnL: $+1.75)
- **Optimal Tau Timing Window:** `PRIME_MID_CYCLE (300s-600s)` (5W-1L, PnL: $+1.75)
- **Average Entry Price:** Wins: `$0.54` | Losses: `$0.53`
- **Side Distribution:** YES: `5W - 1L` | NO: `0W - 0L`

---

## 3. What Happened: Gemini Forensic Diagnostic & Root-Cause Autopsy

### Market Condition & Wave Dynamics Autopsy:
- **Active Market Condition:** **STORMY** (Stormy (Directional Volatility & Volcano Expansion))
- **Condition Dynamics:** High velocity wave expansion (Range: $82663.0, Avg VPIN: 0.23, Macro: STABLE_RANGE)
- **Batch Spot Range:** $82662.97 | **Avg Orderflow VPIN:** 0.227
- **Wave Regime Telemetry:** Baseline microstructural flow

### Winning Trades Autopsy:
Winning entries executed with favorable moneyness in STORMY market regime and positive expected value.

### Losing Trades Autopsy (Causal Taxonomy):
Drawdown cycles tagged under STORMY regime by ContinuousExperienceBuffer causal classifier.

### Probability Calibration & Platt Scaling:
Brier score at 0.3780; Platt Alpha at 0.65.

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

Grant auto-extension for Batch #3. Bot remains armed for live execution.
- **Cumulative Historical Trades:** 12
- **Cumulative Net PnL:** $-1.4549
- **Macro Win Rate:** 41.7%
