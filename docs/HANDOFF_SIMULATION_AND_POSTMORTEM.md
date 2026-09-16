# MASTER ARCHITECTURAL HANDOFF SPECIFICATION
## System Upgrades: Adversarial Simulation (`SimSim` / `IncubatorAgent`) & Ground-Truth Post-Mortem Diagnostic Engine

- **Author:** Koko (Agent Rebut)
- **Target Branch:** `First_live_trade`
- **Execution Target:** Agent Codeflow & Technical Implementation Fleet
- **Status:** APPROVED FOR IMPLEMENTATION
- **Date:** September 14, 2026

---

## 1. Executive Summary & Objective

This specification establishes the blueprint for two interconnected quantitative systems designed to eliminate the "Simulation Mirage" and provide deterministic post-mortem diagnostics:

1. **The Adversarial Simulation & Incubation Engine**:
   Upgrades `OrderSimulator` (offline replay) and `IncubatorAgent` (Lane 2 live shadow paper trading) from idealized "vacuum" physics to a viscous, competitive CLOB environment with synthetic wire latency, FIFO queue exhaustion, algorithmic quote cancellation, asymmetric adverse selection, and 60-second CME CF settlement parity.
2. **The Ground-Truth Post-Mortem Diagnostic Engine**:
   Builds an NTSB-caliber black box flight recorder for all 96 daily contract cycles (:00, :15, :30, :45 ET). It strictly classifies losses into deterministic categories (parameter leaks vs. normal statistical variance vs. guardrail dormancy), audits un-traded cycles (The Ghost Ledger), enforces two-sided counterfactual parameter tuning, and forbids any hallucination or synthetic data fabrication.

---

## 2. Engine 1: Adversarial Simulation & Incubation Upgrade

### A. Trans-Pacific Wire Latency Buffer ($\Delta t_{\text{wire}}$)
- **Physics**: Public internet packets from East Asia to AWS `us-east-1` (Virginia) take 350–500ms round-trip.
- **Formulation**:
  $$\Delta t_{\text{wire}} \sim \text{Clip}\left(\mathcal{N}(\mu = 350\text{ms}, \sigma = 40\text{ms}), 280\text{ms}, 600\text{ms}\right)$$
- **Execution**:
  - **Track A (`SimSim` Offline Replay)**: Signal at timestamp $T_{\text{sig}}$ evaluates matching against book at $T_{\text{eval}} \ge T_{\text{sig}} + \Delta t_{\text{wire}}$.
  - **Track B (`IncubatorAgent` Live Shadow)**: Order intent enters an asynchronous non-blocking delay queue (`asyncio.sleep(0.350)`). Top ask is re-sampled at $T + 350\text{ms}$. If quote was swept or widened, apply +1¢ slippage or register `MISSED_DUE_TO_LATENCY`.

### B. Virtual FIFO Queue & Dynamic Quote Cancellation ($Q_{\text{ahead}}$)
- **Physics**: Resting limit orders sit behind existing volume. When spot moves toward the bid, 40–70% of resting volume cancels (market maker quote pulling).
- **Formulation**:
  - Initial snapshot: $Q_0 = \text{BookDepth}(P_{\text{limit}})$.
  - Effective queue: $Q_{\text{eff}} = Q_0 \times (1 - C_{\text{cancel}})$ with $C_{\text{cancel}} = 0.50$.
  - Matching condition: Decrement strictly by real trade volume on the public trade tape (`trades` WebSocket channel):
    $$Q_{\text{ahead}}(t) = \max\left(0, Q_{\text{ahead}}(t-1) - V_{\text{trade}}\right)$$
  - Fills occur **ONLY** when $Q_{\text{ahead}} == 0$.
  - If cycle time remaining $T_{\text{rem}} \le 270\text{s}$ and $Q_{\text{ahead}} > 0$, order is marked `EXPIRED_UNFILLED`.

### C. Asymmetric Adverse Selection & Toxic Flow Filter ($P_{\text{fill}}$)
- **Physics**: Aggressive market orders (takers) are front-run when spot moves favorably, but filled with 100% certainty when toxic inventory dumps against the trade.
- **Formulation**:
  - Rolling 10s spot velocity Z-score: $Z_v = (v_{\text{spot}} - \mu_v) / \sigma_v$.
  - For BUY YES:
    $$P_{\text{fill}}(Z_v) = \begin{cases} 
    1.00 & \text{if } Z_v \le -1.0\sigma \quad \text{(Toxic flow: 100\% filled)} \\
    \max(0.20, 1.0 - 0.4 \cdot Z_v) & \text{if } Z_v > 0 \quad \text{(Favorable flow: 80\% penalty / slips +1¢)}
    \end{cases}$$

### D. Exact 60-Second CME CF TWAP Settlement Parity
- **Physics**: Kalshi `KXBTC15M` contracts settle on trailing 60-second TWAP from :14:00 to :15:00 ET, never instantaneous spot.
- **Formulation**:
  $$\text{TWAP}_{60} = \frac{1}{N} \sum_{i=1}^{N} S(t_i) \quad \text{for } t_i \in [T_{\text{settle}} - 60\text{s}, T_{\text{settle}}]$$
  $$\text{Outcome} = \begin{cases} \text{YES\_WIN}, & \text{if } \text{TWAP}_{60} \ge K \\ \text{NO\_WIN}, & \text{if } \text{TWAP}_{60} < K \end{cases}$$

### E. Rigid Kalshi Taker Fee Schedule
- Maker Resting Orders: **$0.00** fee.
- Taker Aggressive Orders:
  $$\text{Fee} = \max\left(\$0.01, \min\left(\$0.02, \frac{\lceil 0.07 \times C \times P \times (1 - P) \times 100 \rceil}{100}\right)\right)$$

---

## 3. Engine 2: Ground-Truth Post-Mortem Diagnostic Engine

### A. The 4 Deterministic Loss Buckets
Every losing trade must be classified using deterministic boolean logic directly on telemetry (zero LLM narrative hand-waving):

```python
# 1. Parameter Leak (Calibration Error)
is_category_b = (
    trade.entry_price > max_allowed_entry_price          # Bought > $0.52
    or abs(trade.entry_spot - trade.target_strike) < min_spot_distance  # In Dead Zone (< $25)
    or trade.time_remaining_s < min_entry_cutoff_seconds # Entered late (T < 270s)
)

# 2. Guardrail Dormancy (Late or Silenced Veto)
is_category_c = (
    trade.spot_velocity_z_score >= 2.50                  # Adverse drift was active
    and trade.guardrail_veto_fired is False              # But guardrail failed to block
)

# 3. Microstructure Execution Trap
is_category_d = (
    trade.actual_slippage >= Decimal("0.02")             # Slipped >= 2¢ due to latency
    or trade.fee_drag_pct >= Decimal("0.10")             # Fee ate >= 10% of theoretical EV
)

# 4. Normal Statistical Loss (Expected Probability Variance)
is_category_a = (
    not is_category_b 
    and not is_category_c 
    and not is_category_d
)
```

### B. The Ghost Ledger (Full 96-Cycle Accounting)
- A 24-hour trading day contains exactly **96 fifteen-minute cycles**.
- Every cycle where the bot did NOT trade must be logged with its exact evaluation snapshot:
  - `VETO_RAZOR_THIN_DEAD_ZONE`: $|S_t - K| \le \$25.00$
  - `VETO_OPENING_QUARANTINE`: $T_{\text{rem}} > 810\text{s}$ (Cycle noise dissipation)
  - `VETO_LATE_CUTOFF`: $T_{\text{rem}} < 270\text{s}$ (Entry window closed)
  - `VETO_SPREAD_LIQUIDITY`: $\text{Spread} > 5¢$ or $\text{Depth} < 3$ contracts
  - `VETO_VELOCITY_SPIKE`: Adverse front-run velocity active ($Z_v \ge 2.5\sigma$)
  - `VETO_MODEL_UNCERTAINTY`: Model probability below hurdle ($P < 52\%$)

### C. Two-Sided Counterfactual Matrix (Anti-Cherry-Picking)
- Parameter recommendations must report the full confusion matrix across all historical cycles:
  $$\Delta \text{Net EV} = (\text{Losses Prevented} \times \text{Avg Loss Payout}) - (\text{Wins Sacrificed} \times \text{Avg Win Payout})$$
- If $\Delta \text{Net EV} \le 0$, the parameter adjustment is strictly rejected as an **overfitting trap**.

### D. The 4 Anti-Hallucination Laws
1. **Telemetry Anchor Invariant**: Every metric must map to an exact timestamped row in SQLite / JSONL. If data dropped during a network blip, output `DATA_GAP: UNRECORDED`; never guess or interpolate.
2. **Deterministic Boolean Predicates**: Classification is 100% programmatic code, zero subjective storytelling.
3. **Strict 96-Cycle Grid**: Zero unrecorded cycles in daily reports.
4. **Two-Sided Audit**: Every optimization lever must evaluate both positive and negative consequences.

---

## 4. Implementation Blueprint for Agent Codeflow

### Phase 1: Post-Mortem & Diagnostic Classifier Module
- Create `src/kalshi_sim/post_mortem_engine.py`:
  - `PostMortemClassifier`: Evaluates Category A, B, C, D using boolean predicates.
  - `GhostLedgerTracker`: Reconciles 96 daily cycles and logs veto telemetry snapshots.
  - `CounterfactualTuner`: Computes two-sided matrix for candidate parameter shifts.
- Create `tests/test_post_mortem_engine.py`: 100% test coverage on classification, veto logging, and anti-hallucination data gap handling.

### Phase 2: Adversarial Simulation Upgrade
- Update `src/kalshi_sim/order_simulator.py`:
  - Integrate `synthetic_wire_latency_ms` delay buffer.
  - Implement FIFO `queue_ahead` depletion based on public tape trade events.
  - Add asymmetric adverse selection velocity penalty ($P_{\text{fill}}$).
- Update `src/kalshi_sim/incubator_agent.py`:
  - Enforce asynchronous latency buffer on shadow entries.
  - Wire exact 60s CME CF TWAP settlement and strict taker fee deductions.
- Create `tests/test_adversarial_simulation.py`: Unit tests validating wire delay, queue exhaustion, and adverse fill slippage.

### Phase 3: Reporting & UI Hooks
- Upgrade `data/win_loss_reports.json` schema to include:
  - `loss_category`: `"CATEGORY_A" | "CATEGORY_B" | "CATEGORY_C" | "CATEGORY_D" | null`
  - `veto_reason`: string or null
  - `wire_latency_ms`: int
  - `twap_settlement_used`: bool
- Connect diagnostics to the Mother Dashboard on port 8000.

---

## 5. Blast-Radius Protection & Invariants

- **Untouchable Modules**:
  - `src/kalshi_sim/api_client.py` (Live API transport)
  - `src/kalshi_sim/process_lock.py` (Port 8001 execution authority)
  - `src/kalshi_sim/live_coordinator.py` (Anti-wash trading shields)
- **Math Invariant**: Zero IEEE-754 floats for monetary logic; strictly Python `decimal.Decimal`.
- **Sizing Invariant**: Micro-bankroll protection locked at 1 contract for accounts $<\$75$.
