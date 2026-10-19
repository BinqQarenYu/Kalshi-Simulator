# The Unified One-Decision Framework (Sweet Spot Edition)

## 1. Executive Summary & Context
On October 19, 2026, an institutional upgrade pack ("Unified One-Decision Framework", 12-Gate Trade Qualification) was submitted for architectural review.
Following an institutional roundtable involving **QuoQuo** (Repository Archivist & Ground-Truth Oracle) and the **Quant Council** (Koko, Dr. Nash, Vance, Silas, The Jackal, Barnaby, Apex), the full 12-file rewrite was assessed as a high-risk over-engineering hazard that would cause:
1. **Trade Starvation:** 4 compounding conservative penalty layers (G4 uncertainty lower bound + G7 net EV + G8 extra safety margin + G12 adverse slippage) resulting in $\sim 0$ trades.
2. **Mathematical Mismatch:** Fractional Kelly sizing (G11) on a micro-bankroll account ($\$35\text{--}\$75$), which is strictly capped by Law 2 at **1 contract ($\le \$0.48$ max risk)**.
3. **Execution Latency:** Multi-file async indirection adding delay in sub-second orderflow windows.
4. **Live System Instability:** Breaking the active AWS EC2 monolithic service on Port 8000.

**The Sweet Spot Decision:**  
The Council unanimously approved the **Surgical "Sweet Spot" Integration**:
- Embed the high-value gates (**G1 Contract Truth & Settlement Parity**, **G5 Executable Book Depth**, and **G12 Adverse 1-Tick Slippage Stress Test**) directly into `Bot1V4DominationEngine` (`src/kalshi_sim/ml/bot1_v4_engine.py`).
- Emit an immutable `QualificationTicket` for every evaluation cycle.
- Wire skipped candidate tickets into the **6-Trade Batch Supervisor and AI Assessor** for **Counterfactual Regret Learning** (auditing False Negatives vs True Negatives).
- Preserve all hard invariants: Port 8000 monolithic execution, strict Decimal financial math, 1 contract per trade, and 1-trade-per-cycle locks.

---

## 2. The 3 Golden Gates

```
[ Incoming Tick / Cycle ]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│   BtcBot1V4Engine / EthBot1V4Engine (In-Place Guard)   │
│                                                        │
│  Gate 1: Contract Truth & CF Benchmarks Expiry Parity  │
│          • Valid strike & spot price > $0              │
│          • Expiration remaining T > 120s               │
│            (Silas 60s TWAP settlement pinning veto)    │
│                                                        │
│  Gate 5: Vance Executable CLOB Depth                   │
│          • Live book inside ask depth ≥ 1 contract     │
│          • Reconstructed NO book depth verified        │
│                                                        │
│  Gate 12: Adverse Execution 1-Tick Stress Test         │
│          • Stressed Price = Limit Price + $0.01        │
│          • Stressed Net EV must remain > $0.00         │
│                                                        │
│  Micro-Bankroll Sizing Clamp:                          │
│          • Approved contracts strictly capped at 1     │
│          • Net risk budget strictly ≤ $0.48            │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            IMMUTABLE QUALIFICATION TICKET              │
│                                                        │
│   Action: BUY_YES | BUY_NO | WAIT                      │
│   First Failed Gate: [e.g. G12_ADVERSE_EXECUTION]      │
│   Telemetry: Calibrated Prob, Spot, Strike, Spread     │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
    [ Executed Trade ]           [ Skipped (WAIT) ]
             │                           │
             ▼                           ▼
    6-Trade Ledger               Skipped Tickets Buffer
             │                           │
             └─────────────┬─────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│        6-Trade Batch Supervisor & AI Assessor          │
│   (Audits Wins/Losses + Counterfactual Regrets)        │
└────────────────────────────────────────────────────────┘
```

### Gate 1: Contract Truth & Settlement Expiration Parity
- **Institutional Authority:** Silas (TWAP Settlement Arbiter).
- **Invariants Checked:**
  - Strike price $> 0$ and spot price $> 0$.
  - Expiration remaining $T_{\text{rem}} > 120\text{s}$. If $T_{\text{rem}} \le 120\text{s}$, new entries are vetoed (`first_failed_gate = "G1_CONTRACT_TRUTH_PINNING"`). CF Benchmarks calculates Kalshi settlement over the trailing 60 seconds; entering in the final 2 minutes exposes capital to irreversible TWAP pinning.

### Gate 5: Executable CLOB Depth Availability
- **Institutional Authority:** Vance (CLOB Microstructure & Execution).
- **Invariants Checked:**
  - Verifies that the targeted side's orderbook has executable depth $\ge 1$ contract at or below our price ceiling.
  - Never assumes fill at `best_yes_ask` on an empty or phantom book.
  - Failure Action: `first_failed_gate = "G5_NOT_EXECUTABLE_NO_DEPTH"`, `recommended_side = "wait"`.

### Gate 12: Adverse Execution 1-Tick Stress Test
- **Institutional Authority:** Dr. Nash (Quantitative Mathematics) & The Jackal (Exploit Adversary).
- **Invariants Checked:**
  - In fast markets, a 1-tick adverse fill ($+\$0.01$ cost) can occur before network arrival.
  - Stressed Net EV:
    $$\mathbb{E}[\text{Stressed Net PnL}] = P_{\text{win}}(1 - (P_{\text{entry}} + 0.01)) - (1 - P_{\text{win}})(P_{\text{entry}} + 0.01) - \text{Fee}$$
  - If $\mathbb{E}[\text{Stressed Net PnL}] \le \$0.00$, the margin of safety is too razor-thin to risk capital.
  - Failure Action: `first_failed_gate = "G12_ADVERSE_EXECUTION"`, `recommended_side = "wait"`.

---

## 3. The Counterfactual Regret Learning Upgrade

### The Prior Blind Spot
Previously, the `ContinuousExperienceBuffer` and `ai_assessor.py` only evaluated **trades that were actually executed**. When the bot chose `WAIT` (80%–90% of cycles), those skipped opportunities were discarded.

### The Upgrade Mechanism
1. Every cycle evaluation generates a `QualificationTicket`.
2. When the engine has a candidate side (`yes` or `no`) but gate checks force `WAIT`, the ticket is recorded in the **Skipped Qualification Tickets Buffer** (`_skipped_qualification_tickets`).
3. During the 6-trade batch review, `ai_assessor.py` inspects both:
   - **Settled Batches (6 trades):** Win rate, net PnL, loss cause attribution.
   - **Skipped Candidate Tickets:** Identifies **False Negatives** (trades blocked by conservative filters where the market subsequently moved in the predicted direction) versus **True Negatives** (trades blocked where the market collapsed, saving capital).
4. Gemini utilizes this counterfactual telemetry to propose bounded adjustments to `ALLOWED_PARAMETER_BOUNDS` (e.g., fine-tuning `min_ev_dollars` or `discount_limit_price` for the active market regime).
5. All parameter updates apply strictly to the **next batch** via `bot_parameters_domination.json` and `truth_synchronizer.py`. In-flight weights remain completely immutable.

---

## 4. Architectural Verification Matrix
- **Zero Float:** All monetary calculations, balances, strike diffs, and EV hurdle checks remain in `decimal.Decimal`.
- **Micro-Bankroll Clamp:** `approved_contracts = min(requested, 1)` strictly enforced.
- **Single Process:** Port 8000 monolith hosts both BTC and ETH engines and their dedicated batch supervisors.
- **Protective Exits:** Take-profit, trailing ratchet, and salvage exits bypass entry gates and are never suppressed.
