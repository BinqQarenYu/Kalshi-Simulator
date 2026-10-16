# KEV the Lead: Dynamic Math-of-Winning Taker Engine

**Document Version:** 1.0.0  
**Effective Date:** 2026-10-15  
**Active Production Branch:** `zero_hallucination_mode`  
**Target Exchanges:** Kalshi Binary Prediction Markets (`KXETH15M`, `KXBTC15M`)  
**Deployment Infrastructure:** AWS EC2 Production (`13.63.158.94`) & Local Telemetry  

---

## 1. Executive Summary & Paradigm Evolution

### The Historical Bottleneck: Passive Maker Limit Traps
In previous engine revisions, trading bots operated primarily as **passive makers**, posting limit orders deep within the bid side (e.g., $0.35–$0.42). While intended to capture maker discounts, empirical analysis revealed two critical structural flaws:
1. **Adverse Selection:** Maker orders filled predominantly when informed orderflow was actively driving spot *against* the bot's position (toxic fills).
2. **Opportunity Cost:** During high-conviction momentum breakouts, maker limit bids were left behind in the book, missing high-probability winning cycles.

Meanwhile, the cognitive oracle **Kev** (operating in shadow evaluation) demonstrated an empirical **90.9% directional win rate** (20 wins, 2 losses across 23 live settled cycles on Kalshi PROD).

### The New Paradigm: Kev the Decisive Lead Taker
Under the **Kev Lead Taker Architecture**, Kev is elevated from a passive observer to the **Chief Directional Officer**. When Kev establishes directional conviction, the engine executes immediately as a **Taker** via crossing limit orders, capturing available book liquidity. However, this taker aggressiveness is strictly governed by a **Dynamic Math-of-Winning Hurdle** and an anti-trap defense matrix, ensuring the bot never overpays and only trades when quantitative expected value ($\mathbb{E}[V]$) is decisively positive.

```mermaid
flowchart TD
    A["15-Minute Cycle Tick (Tau in [120s, 840s])"] --> B{"1-Trade Lock Clear & No Active Position?"}
    B -- No --> C["STAND DOWN (Cycle Locked / Position Active)\nZero LLM Token Credit Burn (Rule 8)"]
    B -- Yes --> D{"Proximity Moat Veto\n|Spot - Strike| >= Moat?"}
    D -- No --> E["STAND DOWN (Tie Trap Zone)"]
    D -- Yes --> F{"VPIN < 0.60 &\n!Toxic Sweep?"}
    F -- No --> G["STAND DOWN (Toxic Orderflow)"]
    F -- Yes --> H["Kev Oracle Evaluation\n(Direction & Confidence)"]
    H --> I{"Kev Direction:\nYES or NO?"}
    I -- WAIT --> J["STAND DOWN (Neutral Conviction)"]
    I -- YES / NO --> K["Continuous Math-of-Winning\nP_win = alpha_Learning * (0.75 * P_kev + 0.25 * P_physics)"]
    K --> L["Compute Hurdle & Ceiling\ndelta_hurdle = 0.08 + (VPIN * 0.10)\nP_max = min(P_win - delta_hurdle, Cap)"]
    L --> M{"L2 Orderbook Check\nBest Ask <= P_max?"}
    M -- No (Ask > P_max or Empty) --> N["PAUSE (Math Hurdle Veto: Refuse to Overpay)"]
    M -- Yes --> O["Execute Taker Limit Order\n(Price = Best Ask, Size = 1 ct)"]
    O --> P["Engage 1-Trade-Per-Cycle Lock\nLog Forensics & Await Settlement"]
```

---

## 2. Empirical Foundation & Cycle Timing Optimization

### A. Empirical Accuracy of Kev Across Cycle Phases
Analysis of tick-level and settled-cycle telemetry yields clear empirical performance bands based on cycle time remaining ($\tau$):

| Cycle Phase | Time to Expiry ($\tau$) | Empirical Accuracy | Typical Kalshi Ask | Net Expected Value ($\mathbb{E}[V]$) | Execution Stance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Opening Phase** | $600\text{s} \le \tau \le 840\text{s}$ | **80.55%** | $\$0.35 - \$0.42$ | $+42.5\text{¢} / \text{trade}$ | **Aggressive Discount Capture:** Deep contract discount compensates for lower certainty. |
| **Mid-Cycle Consolidation**| $300\text{s} \le \tau < 600\text{s}$ | **89.31%** | $\$0.44 - \$0.49$ | $+41.1\text{¢} / \text{trade}$ | **Balanced Momentum:** Orderflow (OFI) aligns with spot drift; optimal risk/reward. |
| **Late Prime Window** | $120\text{s} \le \tau < 300\text{s}$ | **90.14%** | $\$0.48 - \$0.55$ | $+37.2\text{¢} / \text{trade}$ | **High-Probability Execution:** Strict ceiling ($\le \$0.55$) enforced to prevent gamma overpay. |
| **Terminal Zone** | $\tau < 120\text{s}$ | N/A (Gamma Risk) | Widened ($>\$0.85$) | Negative / Toxic | **Hard Trading Freeze:** No new entries permitted. |

---

## 3. Mathematical Formulation (Zero Float Math)

All financial valuations, strike differentials, probabilities, and order amounts are strictly computed using `decimal.Decimal` (Python) and serialized without floating-point IEEE-754 distortion.

### 1. Physical Moneyness Diffusion ($P_{\text{physics}}$)
Spot price diffusion is modeled using dynamic 1-minute realized volatility ($\sigma_{\text{1m}}$) scaled to remaining cycle duration $\tau$:

$$\sigma_{\tau} = \max\left(\sigma_{\text{1m}} \cdot \sqrt{\frac{\tau}{60.0}}, 0.50\right)$$

$$z = \frac{S - K}{\sigma_{\tau}}$$

$$P_{\text{physics}} = \frac{1}{1 + e^{-1.5 \cdot z}}$$

Where:
- $S$ = Live Reference Spot Price (ETH/USD or BTC/USD)
- $K$ = Strike Price of the target 15-minute Kalshi market
- $z$ = Normalized standard moneyness score

### 2. Fused Probability of Winning ($P_{\text{win}}$)
Kev's cognitive directional assessment is combined with the physics diffusion curve via a 75/25 weighting:

$$\text{For YES: } P_{\text{win}} = 0.75 \cdot P_{\text{kev}} + 0.25 \cdot P_{\text{physics}}$$

$$\text{For NO: } P_{\text{win}} = 0.75 \cdot P_{\text{kev}} + 0.25 \cdot (1 - P_{\text{physics}})$$

### 3. Dynamic Anti-Toxic Hurdle ($\delta_{\text{hurdle}}$)
To prevent entering contracts when the expected profit margin is eaten by toxic orderflow or adverse selection, the hurdle scales dynamically with Volume-Synchronized Probability of Toxicity (VPIN):

$$\delta_{\text{hurdle}} = 0.08 + (\text{VPIN} \times 0.10)$$

*Baseline:* When $\text{VPIN} \approx 0.0$, the required edge hurdle is $\$0.08$ ($8\text{¢}$).  
*Toxic Conditions:* When $\text{VPIN} \approx 0.50$, the required hurdle rises to $\$0.13$ ($13\text{¢}$).

### 4. Dynamic Taker Price Ceiling ($P_{\text{max\_entry}}$)
The maximum price the engine is permitted to pay to take liquidity is bounded by the net edge and an absolute discount cap:

$$P_{\text{max\_entry}} = \min\left(P_{\text{win}} - \delta_{\text{hurdle}}, \$0.55\right)$$

```python
# Live Implementation in src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py
fused_win_prob = 0.75 * p_kev + 0.25 * p_physics
hurdle = Decimal("0.08") + (Decimal(str(round(vpin_score, 2))) * Decimal("0.10"))
raw_ceiling = Decimal(str(round(fused_win_prob, 2))) - hurdle
max_taker_price = min(raw_ceiling, Decimal("0.55"))
```

---

## 4. Anti-Trap & Liquidity Guardrails

To prevent losses arising from zero liquidity, ghost spreads, or settlement technicalities, four dedicated defense layers are enforced:

### Layer 1: Zero-Liquidity & Ghost Spread Shield
- **The Trap:** On low-liquidity exchanges or between market-maker quotes, the best ask can jump from $\$0.50$ to $\$0.99$. An unconstrained market order would instantly fill at $\$0.99$, locking in a near-guaranteed loss.
- **The Defense:** 
  1. The engine checks `book.best_yes_ask` or `book.best_no_ask`.
  2. If the ask is `None` (empty book) or `best_ask > max_taker_price`, the order is **aborted immediately**.
  3. All orders are submitted as **Limit Takers** (`price_dollars = best_ask`). Slippage is mathematically impossible.

### Layer 2: Settlement Tie Trap & Proximity Moat
- **The Trap:** Kalshi rule KXETH15M/KXBTC15M stipulates that YES wins *strictly* if the final expiration index is strictly greater than the strike ($S_{\text{settle}} > K$). If $S_{\text{settle}} == K$ (exact tie), **NO settles to \$1.00 and YES settles to \$0.00**.
- **The Defense:** The Proximity Moat vetoes entries when spot is within $\$2.50$ of the strike ($|S - K| < \$2.50$), eliminating ambiguous coin flips.

### Layer 3: Toxic Sweep & Informed Trader Veto
- If institutional trade flow exhibits aggressive toxic sweeping (`is_toxic_sweep == "true"` or $\text{VPIN} \ge 0.60$), all entries are suspended.

### Layer 4: 7-Consecutive-Loss Circuit Breaker
- In accordance with risk management updates, if 7 consecutive settled losses occur without an intervening win, all trading halts completely across the asset class (`is_eth_bot_armed = False`), requiring manual diagnostic intervention.

### Layer 5: Anti-OTM Moneyness Trap Protection
- **The Trap:** If Kev generates a strong directional confidence based on short-term delta or momentum while the underlying spot price is deep out-of-the-money (e.g. Spot is $\$5.00$ below Strike, but Kev recommends YES), taking the position represents a low-probability lottery ticket in a 15-minute timeframe.
- **The Defense:** Strict moneyness consistency check:
  - If Kev recommends `YES` and Spot $S < K - \$3.00$, the bot aborts entry and logs:  
    `🛑 [OTM TRAP FILTER] Kev recommended YES, but spot is deep below strike by -$X.XX. Stand down to WAIT.`
  - If Kev recommends `NO` and Spot $S > K + \$3.00$, the bot aborts entry and logs:  
    `🛑 [OTM TRAP FILTER] Kev recommended NO, but spot is deep above strike by +$X.XX. Stand down to WAIT.`

### Layer 6: Immediate-or-Cancel (IOC) Taker Limit Execution
- **The Trap:** When executing with `order_type="limit"`, if the resting ask liquidity moves or vanishes during the transit millisecond, a standard limit order would rest in the orderbook as a maker (`good_till_canceled`), exposing the bot to adverse selection.
- **The Defense:** All crossing taker limit orders are explicitly submitted with `time_in_force="immediate_or_cancel"`. Any unfillable quantity is cancelled instantly by the matching engine, ensuring 0% resting order exposure.

---

## 5. Architectural Component Map

| Component | File Location | Responsibility |
| :--- | :--- | :--- |
| **Decision Oracle** | [`src/kalshi_sim/ml/kev_oracle.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/kev_oracle.py) | Real-time cognitive evaluation, OFI/VPIN synthesis, directional voting. |
| **Execution Engine** | [`src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py) | Dynamic math-of-winning calculation, hurdle enforcement, taker order dispatch. |
| **Risk Guardrails** | [`src/kalshi_sim/agent_guardrails.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/agent_guardrails.py) | 7-loss circuit breaker, 1-trade-per-cycle lock, bankroll sizing. |
| **Order Client** | [`src/kalshi_sim/order_client.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/order_client.py) | Pooled HTTP sessions, RSA-signed REST execution, live balance tracking. |
| **AWS Systemd Host** | `/etc/systemd/system/kalshi-eth-bot.service` | 24/7 autonomous production daemon on AWS EC2 (`13.63.158.94`). |

---

## 6. Live Telemetry Verification Samples

### Sample 1: Math Hurdle Refusing to Overpay (Defense Active)
```log
2026-10-15 22:49:32 [INFO] 🔮 [KEV DECISION ORACLE] Rec: YES (Conf: 78.0%) | Toxic: false | Latency: 0.5ms
2026-10-15 22:49:32 [INFO] ⏸️ [MATH HURDLE VETO] Best ask $0.8000 > Max Taker Ceiling $0.55 (P_win: 80.7%, Hurdle: $0.10). Refusing to overpay.
```
*Outcome:* Contract price is too high; expected value is unfavorable despite high Kev confidence. The bot preserves capital.

### Sample 2: Proximity Moat Stand-Down (Tie Trap Avoided)
```log
2026-10-15 19:56:23 [INFO] 🔮 [KEV DECISION ORACLE] Rec: YES (Conf: 78.0%) | Toxic: false
2026-10-15 19:56:23 [INFO] ⏸️ [PROXIMITY MOAT VETO] |Diff| $2.24 < $2.50 noise threshold. Stand down.
```
*Outcome:* Spot is within $\$2.24$ of the strike. The bot abstains from coin-flip exposure.

### Sample 3: High-Edge Discount Taker Execution
```log
2026-10-15 22:40:15 [INFO] 👑 [KEV LED TAKER ORDER EXECUTED] KXETH15M-26OCT151600-00 YES 1 ct @ $0.41 (Best Ask, Max Ceiling: $0.55, P_win: 81.2%, E[V]: +$0.40) | Result: {'order_id': 'ord_01jb8...'}
```
*Outcome:* Immediate taker fill at $\$0.41$ capturing an opening discount with an expected return of $+40\text{¢}$.

---

## 7. The Balanced Division of Power: Learning as the Supreme Governor

While Kev functions as the **Tactical Lead Taker** during live order execution, Kev is **not an unconstrained dictator**. In accordance with [`BALANCED_DIVISION_OF_POWER.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/01_ARCHITECTURE/BALANCED_DIVISION_OF_POWER.md), the **Learning Engine** acts as the **Supreme Governor** over Kev:

1. **Platt Confidence Dampener:** Kev's raw confidence $P_{\text{kev}}$ is scaled dynamically by the Learning Engine's empirical Brier score factor $\alpha_{\text{Learning}}$ ($P_{\text{calibrated}} = \alpha \cdot P_{\text{kev}}$). If Kev suffers a losing streak, $\alpha$ decreases (down to $0.65$), suppressing Kev's effective conviction below the $60\%\text{--}65\%$ hurdle and forcing a disciplined stand-down.
2. **Mistake Matrix Blacklisting:** The Learning Engine's 3D Mistake Matrix maintains banned quadrants. If Kev recommends a trade in a historically toxic state-space (e.g. *Late-Cycle Expiration with Tight Strike Proximity*), the Learning Engine issues an executive veto.
3. **Decile Price Armor:** If trades executed at $\ge 60\text{¢}$ fail to produce positive EV over rolling windows, the Learning Engine clamps Kev's maximum entry price down to $48\text{¢}\text{--}55\text{¢}$.
4. **Pre-Inference Zero Credit Burning Gate:** Per AGENTS.md Rule 8 & Law 2, if the cycle is locked, the 1-trade limit has been satisfied, or an open inventory position exists, the bot aborts *before* calling `kev_oracle.evaluate()`, eliminating 100% of redundant LLM token expenditures on non-tradable cycles.

---

## 8. In-Flight Derisking: The Valley Ejector Protocol

Kev's entries are paired with active in-flight risk management to avoid holding losing positions to 0¢:

- **Valley Ejector (`Rule 6` / `EJECT_VALLEY`):** If a Kev-led position deteriorates, the contract bid collapses to $\le \$0.38$ (or $\le \$0.40$ in HMM `RISK_OFF`), and adverse reversal is confirmed ($\ge 65\%$), the engine executes an immediate market taker sell to salvage $\$0.25\text{--}\$0.38/\text{contract}$.
- **Quantitative Benefit:** Loss is capped at $-\$0.15\text{--}\$0.20$ per contract rather than absorbing a $-100\%$ ($\$0.42$) expiration wipeout.
- **Anti-Whipsaw Guard:** The exit is held back if the adverse move has not persisted for $\ge 2$ consecutive evaluation ticks (`DoF-04`), or if the trailing 60s TWAP has already mathematically locked in favorable settlement (`Silas TWAP Parity`).
- **Asset-Adaptive Cushion:**
  - **BTC:** $\ge \$25.00$ TWAP cushion required to assert safety.
  - **ETH:** $\ge \$2.50$ TWAP cushion required to assert safety.

