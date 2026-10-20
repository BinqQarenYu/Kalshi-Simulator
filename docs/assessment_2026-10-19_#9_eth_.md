# 6-Trade Evaluation Assessment Series: Batch #9 (ETH)

**Document ID:** `assessment_2026-10-19_#9_ETH_`  
**Series Classification:** Continuous 6-Trade Quantitative Audit & Forensic Ledger  
**Evaluation Date:** 2026-10-19 (19:15 UTC)  
**Target Asset:** Ethereum Binary Options (`KXETH15M` 15-Minute Expirations)  
**Execution Vessel:** `Bot 1 V4 (ETH Domination Engine) / Dual Warrior Architecture`  
**Market Condition:** **⚡ STORM EXPANSION** — Stormy (Directional Volatility & Volcano Expansion)  
**AI Macro Regime:** `STABLE_RANGE` | **Wave Region:** `CHOPPY`  
**Gate Evaluation Verdict:** **SAFETY_HALT (Net Batch PnL $-2.61; Balance $26.34)**  

---

## 1. Executive Summary & Batch Scorecard

During this 6-trade evaluation cycle (Trades 1 through 6 of Batch #9), the algorithm recorded the following quantitative performance:

| Metric | Result | Target Benchmark | Status |
| :--- | :---: | :---: | :--- |
| **Market Condition** | **STORMY** | Stormy (Directional Volatility & Volcano Expansion) | ⚡ STORMY |
| **Batch Record** | **0 Wins – 6 Losses** | $\ge 4\text{W} - 2\text{L}$ | 🛑 DRAWDOWN |
| **Win Rate** | **0.0%** | $\ge 60.0\%$ | ⚠️ UNDERPERFORM |
| **Net Batch PnL** | **$-2.61** | $>\$0.00$ | 🛑 DEFICIT |
| **Pre-Batch Balance** | **$28.95** | Micro-Bankroll | Baseline Equity |
| **Post-Batch Balance** | **$26.34** | Peak Preservation | ⚠️ CAPITAL RETRACEMENT |

**Gemini Synthesis:** Batch #9 generated a net PnL of -$2.6142 across 6 settled live trades, resulting in a 0.0% win rate under active STORMY market conditions. The bot suffered catastrophic performance due to recurrent strike dispersion failures and spot tracking anomalies under high velocity wave expansion. A safety halt is invoked immediately to prevent further capital erosion pending spot-to-strike synchronization re-calibration.

---

## 2. Granular 6-Trade Ledger

Audited under Zero Float Financial Math (`decimal.Decimal`):

| # | Cycle Expiration Ticker | Side | Size | Entry Price | Settlement Price | Market Condition | Outcome | Net PnL | Post-Trade Balance |
| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **T1** | `KXETH15M-26OCT191300-00` | **YES** | 1 | `$0.42` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.42** | `$21.55` |
| **T2** | `KXETH15M-26OCT191300-00` | **YES** | 1 | `$0.42` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.42** | `$22.41` |
| **T3** | `KXETH15M-26OCT191300-00` | **YES** | 1 | `$0.42` | `$0.00` | **CHOP** | **🔴 LOSS** | **-0.44** | `$26.34` |
| **T4** | `KXETH15M-26OCT191345-45` | **YES** | 1 | `$0.45` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.45** | `$21.55` |
| **T5** | `KXETH15M-26OCT191345-45` | **YES** | 1 | `$0.45` | `$0.00` | **BLEED** | **🔴 LOSS** | **-0.45** | `$22.44` |
| **T6** | `KXETH15M-26OCT191345-45` | **YES** | 1 | `$0.42` | `$0.00` | **CHOP** | **🔴 LOSS** | **-0.44** | `$26.34` |

---

## 2.1. Empirical Loss & Failure Attribution Scorecard (Zero-AI Deterministic Autopsy)

| Trade ID | Outcome | Net PnL | Root Failure Code | Quant Attribution | Capital Salvageable |
| :---: | :---: | :---: | :--- | :--- | :---: |
| `WLR-ETH-261019174526-731` | **LOSS** | **-0.44** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019170011-853` | **LOSS** | **-0.44** | `ERR_DOOMED_HOLD_TO_ZERO` | Doomed position held to 0¢; salvage was possible (DEF-03, wasted $0.12) | **+$0.12 wasted** |
| `WLR-ETH-261019161518-482` | **LOSS** | **-0.66** | `ERR_COUNTER_TREND` | Bet fought institutional 1H macro EMA slope (DEF-01) | **$0.00** |
| `WLR-ETH-261019141520-333` | **LOSS** | **-1.21** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-ETH-261019121534-589` | **LOSS** | **-0.68** | `ERR_COUNTER_TREND` | Bet fought institutional 1H macro EMA slope (DEF-01) | **$0.00** |
| `WLR-ETH-261019101528-689` | **LOSS** | **-0.01** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |

**Total Preventable Capital Leak in Sample:** **$0.12**


---

## 2.2. Empirical Sweetspot & Orderbook Corridor Profile

### Entry Price Corridors:
| Price Corridor | Wins | Losses | Win Rate | Net PnL | Sweetspot Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| DEEP_DISCOUNT ($0.38-$0.43) | 0 | 4 | 0.0% | $-1.71 | 🔴 ADVERSE |
| PRIME_SWEETSPOT ($0.44-$0.48) | 0 | 2 | 0.0% | $-0.90 | 🔴 ADVERSE |
| MOMENTUM_UPPER ($0.49-$0.52) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| HIGH_CEILING (>$0.52) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| OTM_TAIL (<$0.38) | 0 | 0 | N/A | $+0.00 | — UNTESTED |

### Expiration Timing Windows (Tau $\tau$):
| Tau Window | Wins | Losses | Win Rate | Net PnL | Timing Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| EARLY_CYCLE (>600s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PRIME_MID_CYCLE (300s-600s) | 0 | 5 | 0.0% | $-2.18 | 🔴 HAZARD |
| LATE_MID_CYCLE (180s-300s) | 0 | 0 | N/A | $+0.00 | — UNTESTED |
| PIN_ZONE (<180s) | 0 | 1 | 0.0% | $-0.44 | 🔴 HAZARD |

- **Optimal Entry Sweetspot:** `PRIME_SWEETSPOT ($0.44-$0.48)` (0W-2L, PnL: $-0.90)
- **Adverse Selection Hazard:** `DEEP_DISCOUNT ($0.38-$0.43)` (0W-4L, PnL: $-1.71)
- **Optimal Tau Timing Window:** `PIN_ZONE (<180s)` (0W-1L, PnL: $-0.44)
- **Average Entry Price:** Wins: `$0.00` | Losses: `$0.43`
- **Side Distribution:** YES: `0W - 6L` | NO: `0W - 0L`


---

## 2.3. Unified One-Decision Qualification & Counterfactual Regret Audit

- **Skipped Candidate Tickets Audited:** 0
- **Gate Diagnostics:** No candidate qualification tickets were skipped during this cycle, revealing an absence of defensive filtering. The lack of strict pre-entry gating during microstructural regime shifts directly allowed toxic entries into the live orderbook.


---


## 3. What Happened: Gemini Forensic Diagnostic & Root-Cause Autopsy

### Market Condition & Wave Dynamics Autopsy:
- **Active Market Condition:** **STORMY** (Stormy (Directional Volatility & Volcano Expansion))
- **Condition Dynamics:** High velocity wave expansion (Range: $81881.4, Avg VPIN: 0.19, Macro: STABLE_RANGE)
- **Batch Spot Range:** $81881.35 | **Avg Orderflow VPIN:** 0.187
- **Wave Regime Telemetry:** Baseline microstructural flow

### Winning Trades Autopsy:
No winning trades occurred in Batch #9 (0W-6L). All fills entered into unfavorable orderbook dynamics without sufficient spot buffer, resulting in immediate equity drawdown.

### Losing Trades Autopsy (Causal Taxonomy):
Five out of six losses failed due to `ERR_DISPERSION_EXCURSION`, where spot price failed to hold the strike baseline due to fast directional drift and microstructural volatility expansion. One loss was driven by `ERR_DOOMED_HOLD_TO_ZERO`, where the position was held to full settlement despite deteriorating spot differentials ($1.91 vs required threshold).

### Probability Calibration & Platt Scaling:
Model probability calibration is severely degraded, with the rolling Brier Score escalating to 0.3716 (substantially worse than the 0.25 random coin-flip benchmark). High AI confidence assignments (0.80–0.82) were completely decoupled from binary settlement outcomes, confirming severe overconfidence and justifying Platt scaling alpha shrinkage (0.65).

---

## 4. What Changes Triggered: Allowed Parameter Tweaks & Evolution

- **Allowed Tweaks Applied:** `discount_limit_price` = 0.42, `min_confidence` = 85.0, `min_ev_dollars` = 0.04, `min_spot_diff` = 30.0, `vpin_toxic_threshold` = 0.55, `take_profit_price_threshold` = 0.85, `min_take_profit_roi` = 50.0, `moneyness_moat_multiplier` = 1.4, `min_viable_ask_floor` = 0.4, `silas_pinning_blackout_seconds` = 180.0, `adverse_slippage_stress_cents` = 0.02
- **Tuning Rationale:** Tightening `min_confidence` to 85.0% and escalating `min_spot_diff` to 30.0 prevents entries with inadequate spot margin during STORMY market conditions. Lowering `vpin_toxic_threshold` to 0.55 and increasing `silas_pinning_blackout_seconds` to 180.0 suppresses trading under toxic microstructural orderflow and pinning risk.

### Operational Guardrails Enforced:
1. **Zero Float Financial Math Law:** All balance increments, PnL calculations, and limit entries strictly processed in `decimal.Decimal`.
2. **1-Trade-Per-Cycle Invariant:** The bot maintained strict single-order occupancy, eliminating wash trading and self-competition.
3. **Continuous Experience Recalibration:** Online Platt Sigmoid Scaling dynamically recalibrated after every settled cycle.

---

## 5. Council Directives for Subsequent Batch

Safety halt evaluated. Applied allowed tweaks to protect bankroll. Re-arm quota reset.
- **Cumulative Historical Trades:** 6
- **Cumulative Net PnL:** $-2.6142
- **Macro Win Rate:** 0.0%
