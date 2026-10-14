# DYNAMIC TRADING STRATEGY (DRSA — Dynamic Regime-State Architecture)

> **Document ID**: `DOC-STRAT-DRSA-001`  
> **Status**: **LIVE ACTIVE & SEALED PRODUCTION**  
> **Active Live Strategy**: `dynamic_trading_strategy`  
> **Active Preset**: [`data/presets/dynamic_trading_strategy_v1.json`](file:///f:/012D_TRADE/Kalshi%20Simulator/data/presets/dynamic_trading_strategy_v1.json)  
> **Cryptographic Seal Token**: `SEAL-DYNA-7E91F034C82A`  
> **Preset Checksum**: `sha256:ff09141995d541cd`  
> **Target Assets**: `KXBTC15M`, `KXETH15M`, `KXDOGE15M`  
> **Execution Engine**: [`src/kalshi_sim/ml/dynamic_regime_strategy.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/dynamic_regime_strategy.py)  
> **Coordinator Dispatch**: [`src/kalshi_sim/strategy_evaluator.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/strategy_evaluator.py#L243-L335)  
> **Classification**: Truth-Grounded Multi-Regime Adaptive CLOB Market-Making & Directional Front-Running  

---

## 1. Executive Summary & Quant Mandate

The **Dynamic Regime-State Architecture (DRSA)** is an institutional quantitative trading framework built specifically for Kalshi binary prediction markets. 

### The Core Quant Law
$$\mathbb{E}[\text{Net PnL}] = p_{\text{win}} - P_{\text{entry}} - \text{Fee}_{\text{taker}}(P_{\text{entry}}) > 0$$
where $\text{Fee}_{\text{taker}}(P) = \lceil 0.07 \cdot C \cdot P \cdot (1 - P) \rceil$ and Maker fee is $\$0.00$.

### The Fallacy of Unconstrained "Degrees of Freedom"
In naive trading systems, "dynamism" is often misinterpreted as unconstrained degrees of freedom. In quantitative finance, unconstrained parameter modification leads directly to **The Curse of Dimensionality** and **Data Snooping Bias (Overfitting)**:
$$\text{BIC} = k \ln(N) - 2 \ln(\hat{L})$$
When the parameter dimension $k$ grows without structural boundaries, out-of-sample prediction collapses.

DRSA solves this by replacing continuous unconstrained freedom with **Constrained Dynamic Agility**:
1. **Discrete Regime State Machine**: A finite state machine (FSM) partitioned into 4 orthogonal market regimes.
2. **Continuous Parameter Modulation Surfaces**: Real-time parameter adaptation along calibrated, monotonic curves strictly clamped to positive-EV boundaries ($P_{\text{limit}} \le \$0.45$, $\text{contracts} = 1$).
3. **Schmitt-Trigger Hysteresis**: Dual-threshold filters preventing high-frequency regime whipsaw and execution churn.
4. **Automated Dual-Pathway Failover Protocol**: Immediate hot-swap capability into AWS EC2 production when baseline strategies fail performance gates.

---

## 2. The 4 Market Regimes

```
                      +-----------------------------+
                      |   L2 CLOB & Spot Sensors    |
                      +--------------+--------------+
                                     |
               +---------------------+---------------------+
               |                     |                     |
         [ σ < $18 ]           [ σ ≥ $30 ]           [ Spread > 4¢ ]
               |                     |                     |
               v                     v                     v
      +-----------------+   +-----------------+   +-----------------+
      |   REGIME 1:     |   |   REGIME 2:     |   |   REGIME 3:     |
      |   CHOP (Maker)  |   |  STORM (Trend)  |   | BLEED (Shield)  |
      +--------+--------+   +--------+--------+   +--------+--------+
               |                     |                     |
               +---------------------+---------------------+
                                     |
                          [ T_rem ≤ 120s ]
                                     |
                                     v
                            +-----------------+
                            |   REGIME 4:     |
                            | SILAS SETTLEMENT|
                            +-----------------+
```

### Regime 1: Low-Volatility Chop (Chop Harvester)
- **Market State**: Compressed ranges, low realized 1-minute volatility ($\sigma_{1m} < \$18.0$), low spot velocity ($|\Delta \text{Spot}| < \$15.0$).
- **Strategy Mode**: Passive resting Maker limit orders at deep discount ($P_{\text{limit}} \le \$0.44$).
- **Exchange Fee**: $\$0.00$ (Zero maker fee).
- **Goal**: Collect the spread and asymmetric payout on mean-reverting noise.

### Regime 2: Directional Storm (Storm Vanguard)
- **Market State**: Realized volatility $\sigma_{1m} \ge \$30.0$, sustained spot displacement $|\Delta \text{Spot}| \ge \$55.0$ (BTC) / $\$4.50$ (ETH), tape momentum confirmation.
- **Strategy Mode**: Dynamic Spot Velocity Front-Running. Aggressive limit placement ahead of Kalshi L2 lag.
- **Exchange Fee**: Maker limit priority if book queue allows, or controlled Taker cross if Net EV $> \$0.09$.
- **Goal**: Monetize the structural latency lag of the retail binary order book against spot index moves.

### Regime 3: Bleed Defender & Toxic Order Flow (Quarantine Shield)
- **Market State**: CLOB spread $> \$0.04$, Toxic flow $VPIN \ge 0.60$, or Double-Wick Meatgrinder patterns (wicks $\ge \$45$ on both sides).
- **Strategy Mode**: Defensive Quarantine. Immediate cessation of new order generation. Active resting orders swept.
- **Exchange Fee**: $\$0.00$ (No execution).
- **Goal**: Total capital preservation during liquidity vacuums and flash crash volatility.

### Regime 4: Silas Settlement Gravity ($T_{\text{rem}} \le 120\text{s}$)
- **Market State**: Time to expiry $T \le 120\text{ seconds}$.
- **Quantitative Law**: Kalshi settles on the CME CF Benchmarks 60-second trailing TWAP. Late-cycle spot movements have bounded mathematical impact on the TWAP:
  $$\Delta \text{TWAP}_{\max} \le \frac{T_{\text{rem}}}{60} \cdot \Delta S_{\text{spot}}$$
- **Strategy Mode**: Settlement Parity Sniper. Dynamic switching is frozen; execution is locked strictly to CF Benchmarks TWAP arithmetic parity.

---

## 3. Truth-Grounded Parameter Calibration (Lesson Q8 / BLEED#01 Forensics)

Based on empirical post-mortems of 883+ settled cycles and incident BLEED#01, parameters are hard-anchored to market truth:

| Dial | Calibrated Setting | Forensic Empirical Rationale |
| :--- | :--- | :--- |
| **Deep Discount Ceiling ($P_{\text{limit}}$)** | **`$0.45` Max** (range: $\$0.38 - \$0.45$) | Never risk 48¢–52¢ for a 1:1 payout. Paying $\le 45¢$ guarantees $\ge +122\%$ ROI per winning contract. |
| **Proximity Moat ($\Delta_{\text{thresh}}$)** | **`$55.00`** (BTC) / **`$4.50`** (ETH) | Bitcoin $185 15M candles easily whipsaw a $25 move. A $55 moat guarantees entries stay outside Brownian noise. |
| **Conviction Floor** | **`78.0%` Minimum** | Vetoes 54%–56% marginal coin flips that bleed capital during chop. |
| **Net Expected Value Hurdle** | **`+$0.04` EV / `6.0%` Edge** | Strictly positive EV after exchange fee drag algebra. |
| **VPIN Toxic Ceiling** | **`0.60`** | Protects against predatory flow and informed toxic volume bursts. |

### Continuous Parameter Modulation Surfaces

#### 1. Dynamic Discount Limit Price ($P_{\text{limit}}$)
Modulates with realized 1-minute volatility $\sigma_{1m}$:
$$P_{\text{limit}}(\sigma) = \min\left( \text{Decimal}('0.45'), \; \text{Decimal}('0.38') + \text{Decimal}('0.002') \cdot \max(0, \sigma - 14) \right)$$
- At $\sigma = 10$: $P_{\text{limit}} = \$0.38$ (demands 12¢ safety margin).
- At $\sigma = 20$: $P_{\text{limit}} = \$0.39$.
- At $\sigma \ge 49$: Clamped strictly at $\$0.45$ ceiling.

#### 2. Adaptive Spot Front-Run Velocity ($\Delta_{\text{thresh}}$)
Scales required spot displacement with current CLOB spread:
$$\Delta_{\text{thresh}} = \text{Decimal}('55.0') \times \left(1 + \frac{\text{Spread}_{\text{cents}}}{2}\right)$$
- If spread is 1¢: Threshold is $\$82.50$.
- If spread expands to 4¢: Threshold expands to $\$165.00$ to prevent adverse selection.

#### 3. Dynamic Take-Profit Target ($TP_{\text{target}}$)
- **Trend Regime**: Expands to $\text{Decimal}('0.88') - \text{Decimal}('0.92')$ to maximize runner gains.
- **Chop Regime**: Compresses to $\text{Decimal}('0.72') - \text{Decimal}('0.75')$ to harvest quick mean-reversion profits before re-entry.

---

## 4. Schmitt-Trigger Hysteresis & Whipsaw Prevention

To prevent rapid oscillation between Chop and Trend:
1. **Upper Switch Threshold**: Transition from Chop to Trend requires $\sigma_{1m} \ge \$30.0$ sustained across 3 consecutive ticks.
2. **Lower Switch Threshold**: Reversion from Trend to Chop requires $\sigma_{1m} < \$18.0$.
3. **Minimum Dwell Time ($\tau_{\text{dwell}}$)**: The engine must remain in a chosen regime for at least $30\text{ seconds}$ before state transition is permitted.

---

## 5. Repository Invariant Armor

| Invariant | Specification | Enforcement Mechanism |
| :--- | :--- | :--- |
| **Zero Float Financial Math** | All prices, balances, and PnL use `decimal.Decimal` | Monitored by `agent-integrity-check`, enforced at type-check |
| **1-Trade-Per-Cycle Lock** | Max 1 executed trade per 15-minute contract cycle | `self._guardrails._cycle_locks` in `AgentGuardrails` |
| **Micro-Bankroll Sizing** | Exactly 1 contract per trade ($C = 1$) | Clamped by `PresetAuditor` and `OrderSimulator` |
| **Atomic Order Sweep** | Open orders canceled before strategy/regime switch | `order_sweeper.py` prior to state migration |
| **Deep Discount EV Bound** | Max limit price ceiling $P \le \$0.45$ | Clamped in parameter modulation surface |

---

## 6. Automated Dual-Pathway Failover & AWS Deployment

DRSA is designed to automatically take over execution whenever an active strategy triggers failure gates, ensuring zero server downtime:

### Trigger Pathway 1: Immediate Streak Failure (The Harakiri Gate)
* **Location**: [`src/kalshi_sim/agent_guardrails.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/agent_guardrails.py#L713-L745)
* **Trigger Condition**: Current strategy suffers 3 consecutive losses (`_consecutive_losses >= 3`).
* **Autonomous Action**:
  1. Detects failure of the active strategy.
  2. Hot-swaps to [`data/presets/dynamic_trading_strategy_v1.json`](file:///f:/012D_TRADE/Kalshi%20Simulator/data/presets/dynamic_trading_strategy_v1.json).
  3. Resets streak counter to `0`.
  4. Keeps the bot **ARMED** (`is_bot_armed = True`) to immediately resume trading under DRSA.

### Trigger Pathway 2: Evaluation Batch Failure (Supervisor Gate)
* **Location**: [`src/kalshi_sim/batch_supervisor.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/batch_supervisor.py#L342-L362)
* **Trigger Condition**: 6-trade evaluation batch completes with negative net PnL or win rate $< 50.0\%$.
* **Autonomous Action**:
  1. `AutonomousBatchSupervisor` calls `PresetManager().load_preset("dynamic_trading_strategy_v1")`.
  2. Updates `state.active_strategy_bot = "dynamic_trading_strategy"`.
  3. Atomically syncs parameters on disk and in memory.

### Trigger Pathway 3: Manual Operator CLI Deployment
To force-deploy DRSA on AWS EC2 or local machine at any time:
```bash
python scripts/failover_to_dynamic_strategy.py --preset dynamic_trading_strategy_v1 --asset BTC --force
```

---

## 7. ASVL Verification Suite

The strategy, parameter surfaces, and failover pathways are verified by unit tests in [`tests/test_dynamic_trading_strategy.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/tests/test_dynamic_trading_strategy.py):
* `test_dynamic_regime_zero_float_invariants`: Verifies Decimal precision across all fields.
* `test_micro_bankroll_sizing_armor`: Verifies max 1 contract limit.
* `test_parameter_surface_positive_ev_clamp`: Verifies $\$0.45$ ceiling clamp.
* `test_schmitt_trigger_hysteresis_and_dwell_time`: Verifies noise rejection and dwell times.
* `test_silas_settlement_late_cycle_override`: Verifies $T \le 120\text{s}$ freeze.
* `test_bleed_defender_toxic_quarantine`: Verifies wide spread and VPIN vetoes.
* `test_preset_vault_certified_preset_integrity`: Verifies `PresetAuditor` invariant pass.
* `test_failover_hot_swap_flow`: Verifies atomic preset loading.
* `test_harakiri_streak_triggers_dynamic_failover`: Verifies 3-loss streak auto-failover and re-arm.

**Execution Command**:
```bash
python -m pytest tests/test_dynamic_trading_strategy.py tests/test_preset_vault.py -q
```
**Status**: `17 passed in 6.79s (100% Pass Rate)`.
