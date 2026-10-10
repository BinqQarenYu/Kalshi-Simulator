# SCALEUP.md — Quant Council Directive on Dynamic Position Sizing & Capital Growth

**Date:** October 9, 2026  
**Status:** Council Sanctioned Architectural Directive  
**Target Strategy:** Bot 1 V4 (`bot1_v4_domination`)  
**Scope:** Breaking Free from Static 1-Contract Limits via Alpha & Bankroll Conviction Scaling  

---

## 1. Executive Summary: The 1-Contract Ceiling Dilemma

Static 1-contract sizing protects capital during incubation, but it imposes a severe mathematical ceiling:
1. **Linear vs. Exponential Growth:** At 1 contract, a 60% win rate yields linear, slow growth (~$0.25 net per cycle).
2. **Under-allocation of High Edge:** When an opportunity presents 85%+ win probability with a $50 moneyness moat, risking only 1 contract leaves massive mathematical expected value on the table.
3. **The User's Intuitive Proposal:** Leverage consecutive winning streaks (e.g. after 3 to 6 consecutive wins, scale to 2, 3, or 4 contracts).

The Quant Council investigated this proposal through an exhaustive forensic audit of the historical trade database.

---

## 2. Forensic Database Audit: The "Hot-Hand" Streak Trap

We analyzed all 100 historical trades in `data/win_loss_reports.json` to calculate the **Conditional Win Probability** following wins and losses:

```
Total Trades Audited: 100
Overall Baseline Win Rate: 56.0%

After 1 Win:            56 trades -> Next Win Rate: 48.2%  (-7.8% vs base)
After 2 Wins:           27 trades -> Next Win Rate: 44.4%  (-11.6% vs base!)
After 3 Wins:           12 trades -> Next Win Rate: 50.0%  (Coin flip)
After 1 Loss:           43 trades -> Next Win Rate: 67.4%  (+11.4% vs base)
After 2 Losses:         13 trades -> Next Win Rate: 76.9%  (+20.9% vs base)
```

### The Market Microstructure Truth:
- **Kalshi is NOT a trending casino game:** Each 15-minute cycle represents a bounded, fixed-time binary payoff.
- **Trend Exhaustion:** 3 consecutive wins means Bitcoin has moved in one direction for **45 continuous minutes**. In cryptocurrency order books, a 45-minute unidirectional run encounters institutional limit order walls, delta hedging by market makers, and profit-taking.
- **The Reverse Martingale Ruin Trap:**
  If the bot sizes up to 3 or 4 contracts after a 3-win streak:
  - Trade 1 (1 contract @ $0.40): WIN -> +$0.60
  - Trade 2 (1 contract @ $0.40): WIN -> +$0.60
  - Trade 3 (1 contract @ $0.40): WIN -> +$0.60
  - **Trade 4 (Sized UP to 4 contracts @ $0.48):** At a 44.4% win rate, a reversion loss strikes -> **-$1.92!**
  - **Net Account Result: -$0.12 (All 3 wins erased + net negative).**

**Law of the Council:** *Never size up based on backward-looking win streaks. Size up based on forward-looking mathematical edge and available equity.*

---

## 3. The Institutional Growth Architecture: "Alpha & Equity Conviction Sizing"

Instead of streak-chasing, elite quantitative funds scale size using two independent axes:
1. **Axis 1: Bankroll Equity Stepladder (Drawdown Defense)**
2. **Axis 2: Alpha Conviction (Forward Expected Value)**

```mermaid
flowchart TD
    A[Market Opportunity Detected] --> B{Bankroll Equity Milestone}
    
    B -->|Equity < $40| C[Tier 1: Strict 1 Contract Base]
    B -->|Equity $40 to $49.99| D{Warrior 2 Deep Discount Chop?}
    D -->|Yes: Price ≤ $0.42 & P ≥ 65%| E[🏹 Unlock 2 Contracts (Risk only $0.76 - $0.84)]
    D -->|No: Normal Storm| C
    
    B -->|Equity $50 to $74.99| F{Alpha Conviction Tier 2?}
    F -->|P ≥ 80% & Moat ≥ $30 & VPIN < 0.28| G[⚔️ Unlock 2 Contracts on Storm/Chop]
    F -->|Standard Edge| C
    
    B -->|Equity $75 to $99.99| H{Alpha Conviction Tier 3?}
    H -->|P ≥ 85% & Moat ≥ $45 & VPIN < 0.22| I[🔥 Unlock 3 Contracts]
    H -->|Standard Edge| G
    
    B -->|Equity ≥ $100.00| J{Seal of Star Player Active?}
    J -->|Yes & Conviction ≥ 88%| K[👑 Unlock 4 Contracts]
    J -->|Standard| I
```

---

## 4. The 4 Equity Growth Milestones

| Equity Tier | Bankroll Range | Max Size | Risk per Trade | Sizing Philosophy |
| :--- | :---: | :---: | :---: | :--- |
| **Tier 1 (Micro)** | **\$35.00 – \$39.99** | **1 Contract** | \$0.38 – \$0.55 (1.1% – 1.6%) | Capital preservation. 0% risk of streak blowup. |
| **Tier 1B (Chop Sniper)** | **\$40.00 – \$49.99** | **2 Contracts (Chop Only)** | \$0.76 – \$0.84 (1.5% – 1.7%) | Asymmetric risk/reward. Only at \$0.38–\$0.42 maker entries with 160% ROI. |
| **Tier 2 (Emerging)** | **\$50.00 – \$74.99** | **2 Contracts (All)** | \$0.76 – \$1.08 (1.5% – 2.1%) | Unlocks 2 contracts on both Storm and Chop when Conviction $\ge 80\%$. |
| **Tier 3 (Growth)** | **\$75.00 – \$99.99** | **3 Contracts** | \$1.14 – \$1.62 (1.5% – 2.1%) | Unlocks 3 contracts when Conviction $\ge 85\%$ and Moat $\ge \$45$. |
| **Tier 4 (Star Player)** | **\$100.00+** | **4 Contracts** | \$1.52 – \$2.16 (1.5% – 2.1%) | Full `Seal of Star Player` authorization on elite conviction setups ($\ge 88\%$). |

---

## 5. Regime-Specific Sizing Economics

### Warrior 2: Chop Harvester Sizing Advantage
In Chop, our maker entry limit is clamped between **\$0.38 and \$0.42**:
- Cost of 2 contracts @ \$0.38 = **\$0.76 total risk**.
- Payout on win = **+\$1.24 profit (+163% ROI)**.
- Break-even win rate is only **38.0%**.
- Sizing to 2 contracts in Chop is **safer in dollar risk** than trading 1 contract at \$0.55 in a wild storm!

### Warrior 1: Storm Hunter Sizing Discipline
In Storm, entry prices reach **\$0.52 – \$0.55**:
- 2 contracts cost \$1.04 – \$1.10.
- Payout on win = +\$0.90 to +\$0.96.
- To trade 2 contracts in Storm, the engine demands:
  1. $P_{\text{win}} \ge 80\%$
  2. Spatial Moneyness Moat $|S_t - K| \ge \$30.00$
  3. $\text{VPIN} < 0.28$ (clean order flow, no toxic dumps).

---

## 6. Granularized Implementation Plan (For Codeflow)

### Task 1: Refactor `StatisticalEVEngine.compute_conviction_tier`
- **File:** `src/kalshi_sim/ml/statistical_ev_engine.py`
- **Changes:**
  - Accept `total_equity: Decimal`, `regime: str = "STORM"`, and `has_star_player_seal: bool = False`.
  - Implement Tier 1B Chop Discount boost: Allow 2 contracts if `regime == "CHOP"`, `price <= Decimal("0.42")`, `ai_prob >= 0.65`, and `total_equity >= Decimal("40.00")`.
  - Implement Tier 2 ($50), Tier 3 ($75), and Tier 4 ($100 with Star Player).

### Task 2: Wire Dynamic Sizing into `Bot1V4DominationEngine`
- **File:** `src/kalshi_sim/ml/bot1_v4_engine.py`
- **Changes:**
  - Pass `total_equity` and `regime` into `compute_conviction_tier` for both Warrior 1 (`regime="STORM"`) and Warrior 2 (`regime="CHOP"`).
  - Add `total_equity` parameter to `evaluate_market_opportunity` and update default from live bankroll synchronizer.
  - Check for `Seal of Star Player` from `data/seal_of_excellence.json`.

### Task 3: ASVL Unit Test Suite
- **File:** `tests/test_conviction_scaling.py`
- **Test Scenarios:**
  1. Equity < \$40: strictly 1 contract.
  2. Equity \$42 in Chop @ \$0.38 ($P \ge 65\%$): scales to 2 contracts.
  3. Equity \$42 in Storm @ \$0.50: stays at 1 contract (defense intact).
  4. Equity \$52 in Storm with $P \ge 82\%$, Moat $\ge \$30$: scales to 2 contracts.
  5. Equity \$105 with `Seal of Star Player` and $P \ge 88\%$: scales to 4 contracts.

### Task 4: Code Parity & Deployment Verification
- Synchronize across `zero_hallucination_mode` and `run_live_real_money`.
- Execute full test suite `pytest tests/` under ASVL.
- Verify live state on port 8000 via `/api/state`.
