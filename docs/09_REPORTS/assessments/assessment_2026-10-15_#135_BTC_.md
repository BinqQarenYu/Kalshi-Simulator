# 6-Trade Evaluation Assessment Series: Batch #135 (BTC)

**Document ID:** `assessment_2026-10-15_#135_BTC_`  
**Series Classification:** Continuous 6-Trade Quantitative Audit & Forensic Ledger  
**Evaluation Date:** 2026-10-15 (00:51 UTC)  
**Target Asset:** Bitcoin Binary Options (`KXBTC15M` 15-Minute Expirations)  
**Execution Vessel:** `Bot 1 V4 (BTC Quolas Engine) / Dual Warrior Architecture`  
**Market Condition:** **🌊 CHOPPY** — Choppy (Range-Bound Compression & Mean-Reversion)  
**AI Macro Regime:** `STABLE_RANGE` | **Wave Region:** `CHOP`  
**Gate Evaluation Verdict:** **PASSED (Net Batch PnL $+0.76; Balance $25.00)**  

---

## 1. Executive Summary & Batch Scorecard

During this 6-trade evaluation cycle (Trades 1 through 6 of Batch #135), the algorithm recorded the following quantitative performance:

| Metric | Result | Target Benchmark | Status |
| :--- | :---: | :---: | :--- |
| **Market Condition** | **CHOPPY** | Choppy (Range-Bound Compression & Mean-Reversion) | 🌊 CHOPPY |
| **Batch Record** | **4 Wins – 2 Losses** | $\ge 4\text{W} - 2\text{L}$ | ✅ PASSED |
| **Win Rate** | **66.7%** | $\ge 60.0\%$ | ✅ PASS |
| **Net Batch PnL** | **$+0.76** | $>\$0.00$ | ✅ PROFITABLE |
| **Pre-Batch Balance** | **$24.24** | Micro-Bankroll | Baseline Equity |
| **Post-Batch Balance** | **$25.00** | Peak Preservation | ✅ CAPITAL GAIN |

**Quantitative Synthesis:** Batch #135 met all Quant Council performance gates with a 66.7% win rate (4W - 2L) and +$0.76 net PnL under Warrior 2 Chop Harvester rules.

---

## 2. Granular 6-Trade Ledger

Audited under Zero Float Financial Math (`decimal.Decimal`):

| # | Cycle Expiration Ticker | Side | Size | Entry Price | Settlement Price | Market Condition | Outcome | Net PnL | Post-Trade Balance |
| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **T1** | `KXBTC5M-26SEP071305-05` | **YES** | 1 | `$0.48` | `$1.00` | **CHOPPY** | **🟢 WIN** | **+0.52** | `$25.00` |
| **T2** | `KXBTC5M-26SEP071305-05` | **YES** | 1 | `$0.48` | `$1.00` | **CHOPPY** | **🟢 WIN** | **+0.52** | `$25.00` |
| **T3** | `KXBTC5M-26SEP071305-05` | **YES** | 1 | `$0.48` | `$1.00` | **CHOPPY** | **🟢 WIN** | **+0.52** | `$25.00` |
| **T4** | `KXBTC15M-T78650` | **NO** | 2 | `$0.35` | `$0.00` | **CHOPPY** | **🔴 LOSS** | **-0.74** | `$9999.26` |
| **T5** | `KXBTC15M-T78650` | **YES** | 1 | `$0.67` | `$1.00` | **CHOPPY** | **🟢 WIN** | **+0.31** | `$10000.31` |
| **T6** | `KXBTC15M-T78650` | **NO** | 1 | `$0.35` | `$0.00` | **CHOPPY** | **🔴 LOSS** | **-0.37** | `$9999.63` |

---

## 2.1. Empirical Loss & Failure Attribution Scorecard (Zero-AI Deterministic Autopsy)

| Trade ID | Outcome | Net PnL | Root Failure Code | Quant Attribution | Capital Salvageable |
| :---: | :---: | :---: | :--- | :--- | :---: |
| `WLR-261014043947-693` | **LOSS** | **-0.74** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |
| `WLR-261014043947-197` | **LOSS** | **-0.37** | `ERR_DISPERSION_EXCURSION` | Dispersion variance excursion | **$0.00** |

**Total Preventable Capital Leak in Sample:** **$0.00**

---

## 3. Macro Fleet Statistics (100-Trade Cumulative Sample)

To eliminate the statistical noise of small 6-trade batches, the macro performance is tracked continuously:
- **Total Settled Cycles:** 100 trades
- **Macro Record:** 55 Wins – 45 Losses
- **Macro Win Rate:** **55.0%**
- **Cumulative Net PnL:** **$+5.59**
- **Profit Factor:** 1.15
- **Capital Preservation Rate:** 100% (Zero liquidation events)

---

## 4. Parameter Evolution & Governance Verdict

- **Quant Council Verdict:** **APPROVED & MAINTAINED**
- **Active Preset:** `Council Baseline v3.2 (Dynamic Fading)`
- **Scale-Up Gate Status:** Stage 1 ($25 -> $40) **COMPLETED**. Stage 2 ($40 -> $50) **IN PROGRESS** (Current Balance: $25.00).
