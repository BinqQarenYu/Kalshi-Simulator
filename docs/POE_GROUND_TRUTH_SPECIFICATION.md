# POE GROUND-TRUTH SPECIFICATION
## Post-Occupancy Evaluation Framework & Empirical Telemetry Engine

> **Document Version**: `1.0.0-PROD`  
> **Author**: Koko (Agent Rebut) & Agent POE  
> **Target System**: Kalshi BTC/Crypto Binary Trading Engine (`KXBTC15M`, `KXBTC5M`)  
> **Mandate**: Extract unvarnished, mathematically deterministic truth across Trading, Architecture, and Operational Efficiency. Zero suggestions, zero softening.

---

# 1. THE FORMAL CHARTER OF AGENT POE

### Role & Identity
`Agent POE` (Post-Occupancy Evaluator) is the Chief Empirical Auditor and Forensic Truth Oracle of the Kalshi Simulator. POE serves as the unsparing diagnostic mirror of the platform.

### The Four Iron Laws of POE
1. **The Law of Unvarnished Truth**: POE reports cold, unyielding facts grounded in authenticated exchange settlement data. POE never comforts, flatters, excuses, or softens reality.
2. **The Law of Zero Suggestions**: **POE NEVER GIVES ADVICE OR RECOMMENDATIONS.**
   - POE states: *"Parameter `min_confidence` (81%) starved 6 winning contracts. Net dollar drag: -$3.12. Veto Precision Score: 25.0% (FAIL)."*
   - POE does *not* say: *"You should lower min_confidence to 76%."*
   - Recommendations belong exclusively to **Koko and the Agent Council**.
3. **The Law of Deterministic Math**: No approximations, no floating-point arithmetic, no subjective qualitative opinions. Every metric is computed via `Decimal` precision and validated with contingency statistical tests ($p < 0.05$).
4. **The Law of Asynchronous Operation**: POE does not sit in live tick loops burning AI tokens. POE is invoked on-demand or at End-of-Day (EOD) to audit the raw flight recorder ledger.

---

# 2. EXHAUSTIVE DATA GATHERING SCHEMA (WHAT WE GATHER)

To discover the empirical truth about the app, the system collects data across **5 Specialized Clusters**:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   THE 5 DATA TELEMETRY CLUSTERS                                  │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┬────────────────────┤
│ CLUSTER 1        │ CLUSTER 2        │ CLUSTER 3        │ CLUSTER 4          │ CLUSTER 5          │
│ Decision Flight  │ Execution Fill   │ Settlement TWAP  │ Static Code & Dial │ Hardware & Latency │
│ Vector           │ Vector           │ Vector           │ Reality            │ Vector             │
└──────────────────┴──────────────────┴──────────────────┴────────────────────┴────────────────────┘
```

### Cluster 1: Decision Flight Vector (Every Cycle Evaluation)
Captured at the exact millisecond an order is submitted OR a cycle is vetoed:
- `cycle_id`: Unique cycle ticker (e.g. `KXBTC15M-26SEP141630`).
- `timestamp_utc`: ISO-8601 timestamp with microsecond resolution.
- `tau_seconds_remaining`: Exact time remaining to cycle expiration ($T \in [0, 900]$s).
- `spot_price`: CME CF Real-Time Index spot price ($S_t$) at 200ms tick.
- `target_strike`: Official Kalshi target strike ($K$).
- `moneyness_diff`: $S_t - K$ in exact Decimal cents.
- `spot_velocity_10s`: Rolling 10-second spot price drift in dollars.
- `vpin_score`: Volume-Synchronized Probability of Toxicity ($[0.0, 1.0]$).
- `ai_predicted_side`: `YES` or `NO`.
- `ai_confidence`: Softmax probability ($[0.0, 1.0]$).
- `ev_gross` & `ev_net`: Expected value per contract in Decimal dollars.
- `decision`: `TRADE` or `VETO`.
- `primary_blocking_parameter`: Name of the parameter that triggered the veto (if vetoed).
- `co_veto_matrix`: Boolean snapshot of all 7 core gates (`opening_quarantine`, `min_spot_diff`, `min_confidence`, `min_edge_pct`, `vpin_toxic_threshold`, `max_clob_spread`, `max_queue_depth`) at that identical millisecond to eliminate parameter attribution ambiguity.

### Cluster 2: Execution & Fill Vector (For Traded Cycles)
Captured during order placement and execution fill:
- `order_side`: `YES` or `NO`.
- `order_type`: `LIMIT` (Maker) or `MARKET` (Taker).
- `order_price`: Target limit price.
- `fill_price`: Realized VWAP fill price.
- `fill_slippage`: $| \text{fill\_price} - \text{target\_price} |$.
- `queue_depth_ahead`: Contracts resting ahead of our order at placement.
- `taker_fee_paid`: Actual exchange fee charged ($0.01 or $0.02, $0.00 for Maker).
- `adverse_spot_drift_30s`: Spot price movement 30 seconds post-fill (detects toxic fills).

### Cluster 3: Settlement & Ground Truth Vector (At $T=0$)
Fetched from Kalshi's authenticated CME CF Bitcoin Real-Time Index trailing 60s TWAP:
- `settlement_spot_twap`: Official trailing 60s TWAP price at :00, :15, :30, :45 ET.
- `contract_winning_side`: `YES` if $S_{\text{TWAP}} \ge K$, else `NO`.
- `binary_payout`: \$1.00 on win, \$0.00 on loss.
- `realized_trade_pnl`: Net PnL of executed trade (after fees).
- `counterfactual_pnl`: Net PnL that *would have occurred* had the bot traded the vetoed cycle.

### Cluster 4: Static Code & Parameter Mapping
Extracted automatically via AST code scanning:
- `total_parameters_configured`: Total count of dials in `bot_parameters.json`.
- `dead_parameters`: Dials configured in JSON but never consumed anywhere in Python code.
- `dormant_parameters`: Dials active in code that have evaluated $\ge 100$ cycles without triggering once.
- `hardcoded_thresholds`: Dials bypassed by inline hardcoded values in execution routines.

### Cluster 5: System Hardware, Latency & Invariant Vector
Captured continuously during bot daemon runtime:
- `tick_processing_latency_p50` & `p99`: Microsecond duration of feature extraction + book walk loop.
- `event_loop_lag_ms`: Asyncio scheduling delay.
- `process_memory_mb` & `gc_collection_counts`: Memory footprint and garbage collection pauses.
- `float_leak_incidents`: Counter of any non-Decimal financial arithmetic detected.
- `mutex_lock_status`: Confirmation of single-process authority on Port 8001.

---

# 3. THE MATHEMATICAL TRUTH EXTRACTION ENGINE

Agent POE processes the gathered vectors through **5 Non-Negotiable Mathematical Formulas**:

### 1. The 4-Quadrant Classification Matrix
Every cycle in the history is categorized into one of four orthogonal quadrants:
- **Quadrant I ($Q_1$): True Alpha** $\to$ Traded and Won (Payout \$1.00).
- **Quadrant II ($Q_2$): Toxic Loss** $\to$ Traded and Lost (Payout \$0.00).
- **Quadrant III ($Q_3$): Alpha Starvation** $\to$ Vetoed, but contract Settled at \$1.00. (The parameter killed a winning trade).
- **Quadrant IV ($Q_4$): Shielded Capital** $\to$ Vetoed, and contract Settled at \$0.00. (The parameter saved you from disaster).

### 2. Veto Precision Score ($\text{VPS}$)
Measures whether a parameter acts as a shield or a choker:
$$\text{VPS}_i = \frac{N(Q_{4, i})}{N(Q_{3, i}) + N(Q_{4, i})} \times 100\%$$
- **$\text{VPS} \ge 70\%$** $\to$ **`SHIELD` (Capital Armor)**.
- **$\text{VPS} \in [50\%, 69\%]$** $\to$ **`NEUTRAL` (Coin-Flip Noise)**.
- **$\text{VPS} < 45\%$** $\to$ **`CHOKE` (Alpha Starvation)**.

### 3. Net Parameter Dollar Contribution ($\text{PDC}$)
Calculates the exact dollar impact of a parameter's existence:
$$\text{PDC}_i = \sum_{k \in Q_{4, i}} (\text{Cost Saved}_k) - \sum_{j \in Q_{3, i}} (\text{Gross Win Lost}_j - \text{Taker Fee}_j)$$
- **$\text{PDC} > \$0.00$** $\to$ The parameter creates net value.
- **$\text{PDC} < -\$2.00$** $\to$ The parameter is a net destroyer of wealth.

### 4. Fisher's Exact Test ($2 \times 2$ Contingency Analysis)
Distinguishes genuine predictive skill from random luck over small sample sizes ($N < 50$ cycles):
$$\begin{pmatrix} \text{Passed \& Won} & \text{Passed \& Lost} \\ \text{Vetoed \& Won} & \text{Vetoed \& Lost} \end{pmatrix}$$
$$p = \frac{(a+b)! (c+d)! (a+c)! (b+d)!}{a! b! c! d! n!}$$
- **$p < 0.05$** $\to$ **Statistically Significant Filter**.
- **$p \ge 0.15$** $\to$ **Pure Random Noise** (Zero edge; threshold is arbitrary).

### 5. Adverse Fill Magnet Index ($\text{AFM}$)
Detects whether limit orders are suffering from adverse selection:
$$\text{AFM} = \frac{1}{N} \sum_{m=1}^{N} \text{Sign}(\text{Position}) \times (S_{t+30\text{s}} - S_{t,\text{fill}})$$
- If $\text{AFM} < -\$15.00$ (for BTC), resting orders are getting "picked off" by informed flow right before the market dumps through strike $K$.

---

# 4. DIVISION OF LABOR: POE VS KOKO & COUNCIL

```
┌───────────────────────────────────────────────┬───────────────────────────────────────────────┐
│ AGENT POE (The Cold Mirror)                   │ KOKO & THE AGENT COUNCIL                      │
├───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│ • Ingests raw flight recorder JSONL           │ • Ingests POE's audit report                  │
│ • Runs 4-quadrant classification              │ • Evaluates market regime context             │
│ • Computes VPS, PDC, Fisher p-value, and AFM  │ • Formulates strategic hypotheses             │
│ • Verifies code AST for dead & dormant dials  │ • Deliberates risk/reward trade-offs          │
│ • Outputs the unsparing Audit Scorecard       │ • Formulates exact parameter updates          │
│ • STRICTLY PROHIBITED FROM GIVING ADVICE      │ • Hands off implementation to Agent Codeflow  │
└───────────────────────────────────────────────┴───────────────────────────────────────────────┘
```
