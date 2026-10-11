# DOF_Counterfactual_Shadow_Ledger.md — Degrees of Freedom, Unfilled Bets & Hidden Variables Architecture

**Document ID:** `DOF_Counterfactual_Shadow_Ledger.md`  
**Classification:** Quant Council Microstructure Theory & Counterfactual Learning Specification  
**Status:** Approved for Future Direction & Roadmap (Protected under Rule 9 — Brain Code Untouched)  
**Execution Directives:** 
1. **DO NOT USE FOR LIVE UPGRADE YET**: All variables and forensic modules remain candidate choices in reserve.
2. **SELECTION ARBITRATION**: The **6-Trade Evaluation Cycle** and **Total Assessment** will empirically choose and promote these DOFs based on ground-truth batch results.
3. **TASK TICKING RULE**: All granular codification tasks remain unticked (`[ ]`). Each task is strictly ticked (`[x]`) only after the code has been authored, deployed, and verified under ASVL.
**Core Thesis:** *Unfilled orders and guardrail vetoes are zero-capital synthetic training samples that expose hidden microstructure variables (Degrees of Freedom) and eliminate survivorship bias.*

---

## 1. Executive Summary & Problem Formulation

In conventional quantitative execution, trading engines only store, review, and train on **filled trades**. This creates a catastrophic statistical blind spot known as **Survivorship Bias in Execution**:

```
                       ┌─────────────────────────────────────────┐
                       │          TOTAL AI TRADE INTENTS         │
                       └────────────────────┬────────────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
        ┌─────────────────────────┐                   ┌─────────────────────────┐
        │      FILLED TRADES      │                   │     UNFILLED INTENTS    │
        │      (Seen World)       │                   │     (Unseen World)      │
        │ • Recorded in DB        │                   │ • Discarded / Forgotten │
        │ • Used for PnL / WinRate│                   │ • Contains Hidden DOFs  │
        │ • Suffer from Adverse   │                   │ • ZERO Risk Observed    │
        │   Selection             │                   │   Counterfactuals       │
        └─────────────────────────┘                   └─────────────────────────┘
```

When a trading engine only trains on its fills, it frequently trains on **adverse selection** (i.e., toxic flow that aggressively crossed the spread to hit our resting order because smart money knew the price was about to collapse).

Conversely, **unfilled bets and vetoed intents** represent decisions that the model *wanted* to make, but did not proceed due to internal risk locks or market queue dynamics. Because every Kalshi binary option deterministically settles at $\$1.00$ or $\$0.00$ at the end of its 15-minute window, we can observe the true outcome of every missed bet **with zero capital at risk**.

By recording these unexecuted intents along with their microstructural environment, we capture new **Degrees of Freedom (DOF)**—the hidden variables that govern fill probability, regime adaptation, and execution quality.

---

## 2. Taxonomy of the Unfilled State (The 4 Failure Modes)

To learn from unexecuted bets, we must categorize precisely *why* an intent did not proceed. Every non-executed signal belongs to one of four discrete failure modes:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              THE 4 FAILURE MODES                                       │
├───────────────┬──────────────────────────┬─────────────────────────────────────────────┤
│ Mode Code     │ Failure Description      │ Primary Microstructure Driver               │
├───────────────┼──────────────────────────┼─────────────────────────────────────────────┤
│ **Mode G**    │ **Guardrail Veto**       │ Pre-flight risk intercept (1-Trade Lock,     │
│ (Guardian)    │ (Internal)               │ 45s cooldown, bankroll limit, streak cap).  │
├───────────────┼──────────────────────────┼─────────────────────────────────────────────┤
│ **Mode Q**    │ **CLOB Queue Non-Fill**  │ Maker limit order posted on Kalshi book,    │
│ (Queue)       │ (External Exchange)      │ but price walked away or cycle expired.     │
├───────────────┼──────────────────────────┼─────────────────────────────────────────────┤
│ **Mode E**    │ **Expectancy Hurdle**    │ Model $P_{\text{win}} > 50\%$, but forward  │
│ (Expectancy)  │ (Mathematical Gate)      │ EV failed Kelly hurdle or minimum discount. │
├───────────────┼──────────────────────────┼─────────────────────────────────────────────┤
│ **Mode M**    │ **Microstructure Veto**  │ Adverse flow detected: VPIN $> 0.35$, OFI   │
│ (Micro)       │ (Order Flow Safety)      │ inverted, or bid-ask spread widened $> 8¢$. │
└───────────────┴──────────────────────────┴─────────────────────────────────────────────┘
```

---

## 3. The Unified Degrees of Freedom (DOF) Master Portfolio

By synthesizing the **Regime & Strategy DOFs created yesterday** ([`docs/GeneralAssesment 001.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/GeneralAssesment%20001.md)) with the **Microstructure & Counterfactual DOFs created today**, we establish the complete candidate parameter space for future iterations:

### Class I: Macro & Regime Degrees of Freedom (Created Yesterday in General Assessment 001)
These macro DOFs govern *which warrior holds the helm* and the macroeconomic state of the market:

| ID | Degree of Freedom (DOF) | Target / Dynamic Range | Operational Function in Regime Engine |
| :--- | :--- | :--- | :--- |
| **`DOF-01`** | **Kinetic Volatility Boundary ($\sigma_{1\text{m}}$)** | $\$12.00$ (Chop) vs $\$16.00$ (Trend) | Delineates compressed mean-reversion from explosive directional momentum. |
| **`DOF-02`** | **Geometric Range Box ($S_{\max} - S_{\min}$)** | $\le \$28.00$ (Chop Cage) vs $> \$50.00$ | Restricts Warrior 2 inside tight consolidation channels. |
| **`DOF-03`** | **Circadian Volume Window** | `13:00–22:00 UTC` vs `23:00–08:00 UTC` | Adjusts baseline aggression between US/London liquid hours and Asian overnight calm. |
| **`DOF-04`** | **Chop Discount Entry Limit ($P_{\text{limit}}$)** | $\$0.38 - \$0.42$ | Asymmetric pricing sweet spot providing $1 : 1.63$ risk-to-reward ratio. |
| **`DOF-05`** | **Dynamic Scalp Exit Hurdle ($\text{ROI}_{\text{exit}}$)**| $+35\% - +50\%$ cash gain | Fires early take-profit exit in chop without waiting for expiration gamma risk. |
| **`DOF-06`** | **Volcano Breakout Trigger** | $|\Delta \text{OFI}| > 0.45$, $|v_{3\text{s}}| > \$15/\text{s}$ | Fast-path order cancellation and regime shift to Warrior 1 upon trend eruption. |
| **`DOF-07`** | **Cooldown Hysteresis Duration** | $45$ continuous seconds calm | Anti-whipsaw filter preventing false reversion back into chop during volatility pauses. |

### Class II: Microstructure & Counterfactual Degrees of Freedom (Created Today in Shadow Ledger)
These micro DOFs govern *why an order fails to proceed or fill* in the orderbook queue:

| ID | Degree of Freedom (DOF) | Target / Type | Operational Function in Execution Engine |
| :--- | :--- | :--- | :--- |
| **`DOF-08`** | **Queue Distance from Touch ($\Delta_{\text{touch}}$)**| $0¢, 1¢, 2¢$ (Integer) | Measures queue passivity. Distance of our bid below best prevailing bid. |
| **`DOF-09`** | **Queue Depth Ahead ($Q_{\text{ahead}}$)** | Contracts (Integer) | Total resting contracts with time-priority ahead of our order at the price level. |
| **`DOF-10`** | **Level-2 Bid-Ask Spread ($S_{\text{CLOB}}$)** | $\$0.02 - \$0.08$ (Decimal) | Spread width at intent. Wide spreads demand maker resting; tight spreads allow snipes. |
| **`DOF-11`** | **Expiration Horizon Countdown ($\tau$)** | $0 - 900$ Seconds | Time remaining until settlement. Governs theta decay and TWAP gamma pinning. |
| **`DOF-12`** | **Volume Flow Toxicity ($v_{\text{VPIN}}$)** | $0.00 - 1.00$ (Float) | Microstructure hazard rate. Distinguishes retail flow from toxic institutional dumping. |
| **`DOF-13`** | **Spot Moneyness Delta ($\Delta_{\text{spot}}$)** | $\$ (P_{\text{spot}} - K)$ | Real-time distance between BTC spot index and strike price. |
| **`DOF-14`** | **Strike Velocity ($v_{\text{spot}}$)** | $\$/\text{s}$ (10s Derivative) | First derivative of spot price drift. Anticipates queue walk-aways. |
| **`DOF-15`** | **Cancel-to-Trade Ratio ($CTR$)** | Ratio $[0.0, \infty)$ | Measures competing market-maker spoofing and liquidity pulling. |
| **`DOF-16`** | **Failure Mode Code** | `MODE_G`, `MODE_Q`, `MODE_E`, `MODE_M` | Categorical failure attribution for post-settlement counterfactual analysis. |

### Class III: Non-Fill Forensic Degrees of Freedom (Microstructure Autopsy DOFs)
These forensic DOFs explain *the physical orderbook failure mechanics* when a resting order fails to fill:

| ID | Degree of Freedom (DOF) | Target / Type | Forensic Physical Meaning |
| :--- | :--- | :--- | :--- |
| **`DOF-17`** | **Queue Depth Deficit ($\Delta Q_{\text{FIFO}}$)** | Contracts (Integer) | Contracts executed at our price level vs contracts ahead of us in line before price walked. |
| **`DOF-18`** | **Spot Walkaway Velocity ($v_{\text{walkaway}}$)** | $\$/\text{s}$ (Float) | Rate of spot price moving away from strike while order was resting on the book. |
| **`DOF-19`** | **Competitor Leapfrog Count ($N_{\text{leapfrog}}$)**| Integer Count | Number of competing market maker orders that stepped ahead of our bid at `Touch + 1¢`. |
| **`DOF-20`** | **Sub-Cent Tick Residual ($\epsilon_{\text{tick}}$)** | Cents ($0.0¢ - 1.0¢$) | Mathematical distance between continuous model fair value and discrete integer tick. |
| **`DOF-21`** | **Resting Lifespan ($\Delta t_{\text{rest}}$)** | Seconds (Float) | Active lifespan of the maker limit order on Kalshi's book before timeout or cancellation. |
| **`DOF-22`** | **Fill Hazard Intensity Rate ($\lambda_{\text{hazard}}$)**| Events/sec (Float) | Empirical probability density of fill per second given prevailing volume velocity. |
| **`DOF-23`** | **Pre-Expiry Liquidity Evaporation ($\mathcal{L}_{\text{freeze}}$)**| Ratio $[0.0, 1.0]$ | Rate of spread blowout and depth evaporation as $\tau \rightarrow 180\text{s}$ (TWAP window). |

---

## 4. Forensic Autopsy of Non-Fills: The "Winner's Curse" & CLOB Physics

In maker order execution, non-fills are governed by an asymmetric statistical trap known as the **Winner's Curse**:

$$\mathbb{P}(\text{Fill} \mid \text{Market Moves In Our Favor}) \ll \mathbb{P}(\text{Fill} \mid \text{Market Moves Against Us})$$

When the bot's prediction is correct, nobody wants to trade against us, and our maker order is starved of fills. When the bot's prediction is wrong, informed aggressors eagerly hit our bid.

Every non-fill is driven by one or more of six physical CLOB failure mechanisms:

```
               ┌────────────────────────────────────────────────────────┐
               │           THE 6 PHYSICAL NON-FILL MECHANISMS           │
               └───────────────────────────┬────────────────────────────┘
                                           │
         ┌──────────────────┬──────────────┼──────────────┬──────────────────┐
         ▼                  ▼              ▼              ▼                  ▼
┌─────────────────┐ ┌───────────────┐ ┌─────────┐ ┌───────────────┐ ┌─────────────────┐
│ 1. FIFO Queue   │ │ 2. Spot Drift │ │ 3. HFT  │ │ 4. 1¢ Tick    │ │ 5. TWAP Gamma   │
│    Priority     │ │    Walkaway   │ │ Leapfrog│ │ Discretization│ │    Evaporation  │
│ ΔQ_FIFO > 0     │ │ v_walkaway >  │ │ N_leap  │ │ ε_tick trap   │ │ L_freeze > 0.7  │
│ (Stuck in line) │ │ $12/sec       │ │ > 2 MMs │ │ (2.5% step)   │ │ (τ < 180s)      │
└─────────────────┘ └───────────────┘ └─────────┘ └───────────────┘ └─────────────────┘
```

1. **FIFO Queue Priority Deficit (`DOF-17`):** Kalshi enforces strict First-In, First-Out priority. If 40 contracts sit ahead of our bid, a 10-contract sell order fills them; if spot moves up, our order is bypassed and left behind.
2. **Spot Velocity Walk-Away (`DOF-18`):** Bitcoin spot discoveries on Binance/Coinbase move with high velocity. If spot moves away from the strike at $> \$12/\text{s}$, fair value moves from $42¢ \rightarrow 48¢$. Resting at $42¢$ is dead; nobody crosses to hit us.
3. **Competing Maker Leapfrogging (`DOF-19`):** Competing HFT algorithms detect tick deltas and immediately bid $1¢$ ahead of us (e.g. from $41¢ \rightarrow 42¢$), absorbing incoming retail sell flow.
4. **The 1-Cent Tick Discretization Trap (`DOF-20`):** Kalshi prices only in whole cents. On a $40¢$ contract, $1¢$ is a massive $2.5\%$ price increment. When fair value is $41.4¢$, bidding $41¢$ underbids and misses; bidding $42¢$ gives away edge.
5. **Time-in-Force Lifetime Discrepancy (`DOF-21`):** Premature cancellation cancels an order right before natural retail liquidity crosses the book, or excessive holding exposes the order to adverse selection.
6. **Pre-Expiry TWAP Gamma Evaporation (`DOF-23`):** In the final 180 seconds, market makers pull quoting algorithms to avoid 60s TWAP settlement risk. Spreads widen to $15¢$, and passive maker fills freeze to zero.

---

## 5. The Selection Protocol: 6-Trade Evaluation & Total Assessment Arbitration

Crucially, **we do NOT implement or hardcode these DOFs into the active bot today**. 

Instead, they represent our **Degrees of Freedom Reserve**. The system delegates the selection, activation, and tuning of these DOFs to our two proven empirical assessment mechanisms:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        EMPIRICAL DOF SELECTION ARBITRATION                             │
├──────────────────────────────────────────┬─────────────────────────────────────────────┤
│ 1. AUTONOMOUS 6-TRADE BATCH EVALUATION   │ 2. TOTAL 24-HOUR FORENSIC ASSESSMENT        │
│    (Micro-Level Optimization)            │    (Macro-Level Strategy Evolution)         │
├──────────────────────────────────────────┼─────────────────────────────────────────────┤
│ • Trigger: After every 6 completed       │ • Trigger: Daily 24-hour audit              │
│   trades (docs/AUTONOMOUS_6_TRADE_*.md). │   (docs/GeneralAssesment 001.md).           │
│ • Net PnL > $0.00: Auto-extends session; │ • Forensic review across all batches and    │
│   active parameters remain locked.       │   market sessions.                          │
│ • Net PnL ≤ $0.00: Auto-disarms and      │ • Evaluates session bifurcation (e.g. Day   │
│   audits the 6-trade batch.              │   vs Night, Trend vs Chop win rates).       │
│ • Selects Class II & III Micro DOFs      │ • Selects Class I Macro DOFs                │
│   (e.g. adjusts Queue Distance DOF-08    │   (e.g. adjusts Volatility Threshold DOF-01 │
│   if Leapfrog DOF-19 is high; tightens   │   or Chop Entry Limit DOF-04 to plug        │
│   Expiry Window DOF-11 if L_freeze       │   overnight leaks).                         │
│   DOF-23 causes execution stalls).       │                                             │
└──────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 6. Counterfactual Settlement Reconciliation Engine

Because Kalshi binary options have fixed expiration timestamps (e.g. 10:00, 10:15, 10:30, 10:45), every unfulfilled intent can be deterministically reconciled at expiration.

### Counterfactual PnL Formula
For any unexecuted intent with intended side $S \in \{\text{yes}, \text{no}\}$ and intended price $P_{\text{intended}}$:

$$\Pi_{\text{counterfactual}} = \begin{cases}
(\$1.00 - P_{\text{intended}}) \times \text{Size} & \text{if Settlement} = S \quad (\textbf{Would have WON}) \\
(-P_{\text{intended}}) \times \text{Size} & \text{if Settlement} \neq S \quad (\textbf{Would have LOST})
\end{cases}$$

### Two Critical Diagnostic Ratios:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COUNTERFACTUAL DIAGNOSTIC RATIOS                                │
├──────────────────────────────────────────┬─────────────────────────────────────────────┤
│ 1. DISASTER AVERSION RATIO (DAR)         │ 2. ALPHA STARVATION RATIO (ASR)             │
├──────────────────────────────────────────┼─────────────────────────────────────────────┤
│                                          │                                             │
│       Count(Vetoed & Would Have LOST)    │       Count(Unfilled & Would Have WON)      │
│ DAR = ───────────────────────────────    │ ASR = ────────────────────────────────      │
│            Total Vetoed Intents          │            Total Unfilled Intents           │
│                                          │                                             │
│ High DAR (> 70%) = Guardrails are saving │ High ASR (> 65%) = Engine is underbidding   │
│ real capital from toxic market crashes.  │ queue; leaving easy money on the table.     │
└──────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 7. Granular Implementation Checklist (Future Codification Patch)

> [!IMPORTANT]
> **Strict Implementation Invariant:** All tasks below are strictly **unticked (`[ ]`)**. They represent the future engineering roadmap. Each checkbox will be ticked **`[x]` strictly upon code completion and ASVL test verification** during a future authorized patch cycle. Active production code remains 100% untouched today.

### Module 1: Non-Fill Event Interception & Tracking
- [ ] **Task 1.1:** Create `src/kalshi_sim/ml/unfill_forensic_tracker.py` to intercept maker order timeouts, cancellations, and queue expirations.
- [ ] **Task 1.2:** Implement FIFO queue depth calculator measuring traded volume vs contracts ahead (`DOF-17`).
- [ ] **Task 1.3:** Implement spot drift walkaway tracker calculating spot velocity during resting lifetime (`DOF-18`).
- [ ] **Task 1.4:** Implement competitor leapfrog detector monitoring top-of-book stepping (`DOF-19`).
- [ ] **Task 1.5:** Append non-fill forensic records asynchronously to `data/non_fill_forensics.jsonl` with $< 0.05\text{ms}$ latency impact.

### Module 2: Settlement Counterfactual Reconciler
- [ ] **Task 2.1:** Implement `src/kalshi_sim/ml/shadow_reconciler.py` to reconcile unresolved non-fills at 15m expiration against official settlement.
- [ ] **Task 2.2:** Calculate automated Counterfactual PnL, Disaster Aversion Ratio (DAR), and Alpha Starvation Ratio (ASR).
- [ ] **Task 2.3:** Categorize non-fills into `LUCKY_MISS` (disaster averted) vs `PAINFUL_MISS` (alpha starvation).

### Module 3: DOF Feature Store & Analytics API
- [ ] **Task 3.1:** Implement REST endpoint `GET /api/shadow/non_fill_diagnostics` exposing summary metrics and failure mode distributions.
- [ ] **Task 3.2:** Expose correlation matrix between `DOF-17` through `DOF-23` and counterfactual settlement win rates.

### Module 4: Dashboard UI Telemetry
- [ ] **Task 4.1:** Author `frontend/src/components/parenthub/ShadowTelemetryCard.tsx` displaying capital saved by guardrails vs alpha lost to non-fills.
- [ ] **Task 4.2:** Add non-fill autopsy breakdown modal in the Live Workbench tab.

### Module 5: 6-Trade Evaluation & Continuous Learning Integration
- [ ] **Task 5.1:** Wire non-fill diagnostics into the 6-trade evaluation gate in `src/kalshi_sim/quant/assessment_evaluator.py` to dynamically recommend DOF adjustments.
- [ ] **Task 5.2:** Feed counterfactual non-fill samples into the offline Bayesian retraining pipeline (`continuous_trainer.py`).

---

## 8. Quant Council Assessment & Conclusion

1. **Non-fills are not random:** They are governed by the physics of FIFO queue priority, spot drift velocity, competitor leapfrogging, and pre-expiry gamma freezing.
2. **The 23 Master DOFs** (`DOF-01` through `DOF-23`) form our complete strategic reservoir for all future market conditions.
3. **The 6-Trade Evaluation batches and Total Assessments will empirically select, tune, and promote these DOFs**, while the granular implementation tasks remain unticked until officially coded and verified under ASVL.

---

*Formulated and ratified by the Quant Council on October 11, 2026. Stored in `docs/` for assessment and future implementation.*
