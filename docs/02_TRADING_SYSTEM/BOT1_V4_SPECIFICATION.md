# Institutional Specification: Bot 1 V4 (QuoLas BTC Domination Engine)

**Path:** `docs/02_TRADING_SYSTEM/BOT1_V4_SPECIFICATION.md`  
**Classification:** Core Quantitative Architecture Specification  
**Asset Target:** Kalshi Bitcoin 15-Minute Binary Contracts (`KXBTC15M`)  
**Underlying Feed:** Binance BTC/USDT Spot WebSocket + Coinbase Pro Spot Feed  
**Execution Venue:** Kalshi Central Limit Order Book (CLOB)  
**Production Daemon:** Systemd `kalshi-bot.service` (AWS EC2)  
**Mathematical Precision:** Strict Zero-Float Math (`decimal.Decimal` in Python, `decimal.js` in TypeScript)  

---

## 1. Executive Strategy Architecture

Bot 1 V4 ("QuoLas") executes defense-first quantitative trading on Kalshi 15-minute Bitcoin binary options. The engine prohibits any single heuristic or naked technical indicator from initiating an order. Decisions pass through an immutable 6-tier evaluation and execution pipeline combining low-latency ONNX microstructural inferences, Gaussian Hidden Markov Model (HMM) macro regime classification, continuous walk-forward Platt calibration, multi-regime execution warriors, strict micro-bankroll sizing, and an autonomous in-flight asymmetric profit harvesting engine.

```mermaid
flowchart TD
    MarketFeeds["Market Data: Binance BTC/USDT + Kalshi L2 CLOB"] --> T1_Filters
    
    subgraph T1_Filters ["Tier 1: Pre-Trade Microstructure & Safety Shields"]
        F1["Max Turnover Lock: 1 Trade / 15M Cycle"]
        F2["Frozen Sensor / Dead Book Veto"]
        F3["VPIN Flow Toxicity Filter: VPIN < 0.65"]
        F4["Spread Corridor Cap: Spread <= $0.05"]
        F5["Asset Isolation Gate: Reject non-BTC symbols"]
        F6["Adverse Selection OFI Shield: Veto if OFI < 0.00 opposing"]
        F7["Macro-Trend Cushion: Diff >= $65.00 if counter-trend"]
        F8["Physics Dispersion Gate: P(Physics) >= 58.0%"]
    end
    
    T1_Filters --> T2_Intelligence
    
    subgraph T2_Intelligence ["Tier 2: Multi-Model Intelligence & Calibration"]
        ONNX["quolas.onnx: L2 Softmax [UP, DOWN, WAIT]"]
        HMM["HMMBrain: 5m Macro State (BULL / BEAR / CHOP)"]
        EXP["ContinuousExperienceBuffer: Mistake Pruner & Dynamic Platt (A, B)"]
        Bayes["Bayesian Fusion Core: Posterior P_win via Gaussian Erf x ONNX"]
    end
    
    T2_Intelligence --> T3_Routing
    
    subgraph T3_Routing ["Tier 3: Regime Detection & Warrior Dispatch"]
        Regime{"detect_market_regime()"}
        W1["Warrior 1 (Storm Hunter): Breakout / Limit $0.46 - $0.55"]
        W2["Warrior 2 (Chop Harvester): Range / Limit $0.38 - $0.42 Maker"]
        BD["Bleed Defender: Double-Wick Trap Filter & Stand-Down"]
        HP["Healing Protocol: Shadow Quarantine (2 Consecutive Wins Re-arm)"]
    end
    
    Regime -->|STORM| W1
    Regime -->|CHOP| W2
    Regime -->|BLEED| BD
    Regime -->|HEALING| HP
    
    W1 --> T4_Gates
    W2 --> T4_Gates
    BD --> T4_Gates
    HP --> T4_Gates
    
    subgraph T4_Gates ["Tier 4: Execution & Risk Management Gates"]
        G1["Opening Quarantine: T > 780s (Wait for settlement wave)"]
        G2["Late Pin Freeze: T < 150s (Chop) / T < 60s (Storm)"]
        G3["Dynamic Proximity Moat: |Spot - Strike| >= Moat"]
        G4["ONNX Consensus Veto: WAIT >= 70% Aborts Entry"]
        G5["Expected Value Hurdle: Net EV >= +$0.02"]
        G6["Anti-Kamikaze Sizing: Fixed 1 Contract ($0.38 - $0.55 risk)"]
    end
    
    T4_Gates --> OrderDispatch["Kalshi REST API: Place Limit Buy Order"]
    OrderDispatch -->|Fill Recorded| OpenPosition["Portfolio: Position Active (has_open_pos = True)"]
    
    OpenPosition --> T6_Exit
    
    subgraph T6_Exit ["Tier 6: In-Flight Exit & Asymmetric Profit Harvesting Engine"]
        CLOB_Poll["1Hz Real-Time CLOB Polling (Bypasses Cycle Lock)"]
        R1["Rule 1: Asymmetric Tail Risk Ceiling (Bid >= $0.90-$0.94)"]
        R2["Rule 2: Spot Delta Front-Runner (Vacuum Defense)"]
        R3["Rule 3: Trailing Profit Ratchet & Breakeven Armor"]
        R4["Rule 4: Late-Cycle Gamma Harvest (15s < T <= 120s, Bid >= $0.85)"]
        R5["Rule 5: Reverse Conviction Take-Profit (ROI >= Min Target)"]
        R51["Rule 5.1: Mid-Cycle Bargain Harvest (Entry <= $0.45, ROI >= +70%, Bid >= $0.78, T >= 180s)"]
        R52["Rule 5.2: Fast Taker Win Lock (Crossing Spread with Fee Advantage)"]
    end
    
    T6_Exit -->|Exit Triggered| SellDispatch["Market Taker Sell Order (action='sell') -> Profit Banked"]
    T6_Exit -->|No Trigger & Safe| Settle["Hold to Expiration ($1.00 Settlement)"]
```

---

## 2. Mathematical Formulations & Invariants

### 2.1 Zero-Float Financial Standard
In accordance with Rule 1 of [`AGENTS.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/AGENTS.md), floating-point arithmetic is prohibited. All balances, contract prices, probability products, and EV metrics are processed via `decimal.Decimal` with explicit rounding modes (`ROUND_HALF_EVEN` or `ROUND_DOWN`):

```python
from decimal import Decimal, ROUND_HALF_EVEN

def compute_expected_value(p_win: Decimal, price_cents: Decimal, fee_cents: Decimal) -> Decimal:
    """Computes expected value using exact Decimal operations."""
    p_win = Decimal(str(p_win))
    price = Decimal(str(price_cents))
    fee = Decimal(str(fee_cents))
    cost = price + fee
    payout = Decimal("100.00")
    
    # EV = (p_win * (payout - cost)) - ((1 - p_win) * cost)
    ev = (p_win * (payout - cost)) - ((Decimal("1.00") - p_win) * cost)
    return ev.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
```

### 2.2 Microstructure Volume-Synchronized Probability of Toxicity (VPIN)
Informed toxic flow is measured over rolling volume buckets $V$:

$$\text{VPIN} = \frac{\sum_{\tau=1}^N |V_\tau^B - V_\tau^S|}{N \cdot V}$$

- If $\text{VPIN} > 0.65$: Entry is vetoed immediately (`ERR_TOXIC_FLOW`).

### 2.3 Bayesian Fusion Core
The uncalibrated physical strike-crossing probability $P_{\text{phys}}$ is computed via the Gaussian error function:

$$d_2 = \frac{\ln(S_t / K) - \frac{1}{2} \sigma^2 \tau}{\sigma \sqrt{\tau}}$$

$$P_{\text{phys}} = \Phi(d_2) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{d_2}{\sqrt{2}} \right) \right]$$

Posterior win probability blends $P_{\text{phys}}$ with the ONNX microstructural output $P_{\text{onnx}}$:

$$P_{\text{raw}} = w_{\text{macro}} \cdot P_{\text{phys}} + (1 - w_{\text{macro}}) \cdot P_{\text{onnx}}$$

### 2.4 Continuous Platt Scaling
To counter probability overconfidence, posterior probabilities pass through online walk-forward Platt scaling:

$$P_{\text{calibrated}} = \frac{1}{1 + \exp(A \cdot P_{\text{raw}} + B)}$$

Parameters $A$ and $B$ are updated dynamically in [`ContinuousExperienceBuffer`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/continuous_experience.py) after every settled cycle.

### 2.5 The Asymmetric Gamma Trap & Commonsense Harvest Formulation
Holding a binary contract into late settlement exposes capital to extreme asymmetric payoff skew. Let $P_{\text{bid}}$ be the current top-of-book bid on the CLOB, $P_{\text{entry}}$ be the execution purchase price, and $p_{\text{settle}}$ be the subjective probability of expiring in-the-money ($1.00 payout):

$$\mathbb{E}[\Delta \text{Hold}] = p_{\text{settle}} \cdot (\$1.00 - P_{\text{bid}}) - (1 - p_{\text{settle}}) \cdot P_{\text{bid}}$$

When a contract entered at deep discount (e.g. $P_{\text{entry}} = \$0.38$) surges to $P_{\text{bid}} = \$0.80$ (+110% gross ROI), the remaining upside is:
$$\text{Upside} = \$1.00 - \$0.80 = \$0.20$$
while the downside risk of holding to expiration is:
$$\text{Downside Risk} = \$0.80$$

The risk-reward ratio of holding is **$4:1$ negative**: the trader risks $\$0.80$ of banked equity to gain $\$0.20$. To make holding mathematically positive EV, the required survival probability is:
$$p^* = \frac{P_{\text{bid}}}{\$1.00} = \frac{\$0.80}{\$1.00} = 80.0\%$$

In a 15-minute event where 3–8 minutes ($T_{\text{rem}} \ge 180\text{s}$) remain, Bitcoin spot Brownian volatility ($\sigma_{1\text{m}} \approx \$14.00$) routinely causes $\$50-\$100$ whipsaws. Under such regime variance, true probability $p_{\text{settle}}$ rarely justifies an $80\%+$ hurdle. The **Commonsense Profit Harvest Engine** dictates that banking a $+70\%$ to $+110\%$ ROI immediately by selling to the resting bid is strictly superior in terms of long-term Kelly compound growth than gambling banked capital on late-cycle binary flips.

---

## 3. Six-Tier System Decomposition

### 3.1 Tier 1: Microstructure & Liquidity Shields
1. **Cycle Lock (1 Trade/Cycle):** Once an order is placed for contract cycle $C_i$, the bot locks until settlement $T_3$ of $C_i$. Wash trading and cannibalistic flip-flopping are physically prevented.
2. **Dead Book / Frozen Sensor Veto:** Verifies that bid-ask depth has updated within the last 3,000ms and both bid/ask quantities $\ge 1$.
3. **CLOB Spread Corridor:** If $\text{Ask} - \text{Bid} > \$0.05$, market liquidity is classified as illiquid and execution is aborted.

### 3.2 Tier 2: Machine Learning Intelligence
- **`models/quolas.onnx`:** High-frequency neural network computing order flow imbalance, micro-price velocity, and top-of-book skew. Returns 3 probabilities: $[P(\text{UP}), P(\text{DOWN}), P(\text{WAIT})]$. If $P(\text{WAIT}) \ge 0.70$, trade execution is blocked.
- **`HMMBrain` (Macro Markov Regime):** Evaluates rolling 5-minute OHLCV bars into 3 states:
  - `BULL_MOMENTUM`: Restricts directional bids to YES contracts.
  - `BEAR_MOMENTUM`: Restricts directional bids to NO contracts.
  - `STABLE_RANGE`: Permits dual-sided harvesting under Warrior 2 rules.

### 3.3 Tier 3: Market Regime Routing (One Boat, Two Warriors)
- **Warrior 1 (Storm Hunter):**
  - Triggered when 15-minute range $> \$165.00$ and $|\Delta \text{Spot}| > \$100.00$.
  - Entry bounds: Limit order between **`$0.46 - $0.55`**.
  - Minimum probability hurdle: $P_{\text{calibrated}} \ge 72.0\%$.
- **Warrior 2 (Chop Harvester):**
  - Triggered when 15-minute range $\le \$165.00$ and realized volatility $\sigma \le \$12.00$.
  - Entry bounds: Limit order strictly between **`$0.38 - $0.42`** (Maker limit only, $0.00 fee).
  - Timing corridor: Only between $150\text{s} \le T \le 450\text{s}$ to expiry.

### 3.4 Tier 4: Execution Timing Gates
- **Opening Quarantine ($T \ge 780\text{s}$):** The first 120 seconds of each 15-minute contract are quarantined to let opening volatility settle.
- **Late Pin Freeze ($T < 150\text{s}$ for Chop, $T < 60\text{s}$ for Storm):** Prevents entering during gamma expiration traps where spreads widen and manipulation spikes.

### 3.5 Tier 5: Micro-Bankroll Risk Guardrail
- Maximum position size is hardcoded to **1 contract per trade**.
- Maximum loss per cycle is bounded to the entry price ($\le \$0.55$).
- Scale-up is locked until balance reaches the required milestone ($40+ / $50+).

### 3.6 Tier 6: In-Flight Early Exit & Profit Harvesting Engine (`DominationExitEvaluator`)
Once an order is filled, the position is continuously evaluated at 1Hz against 6 quantitative exit rules.

#### Anti-Lockout Invariant (`has_open_pos` Cycle Lock Exemption)
`AgentGuardrails` strictly limits new entries to 1 trade per 15-minute cycle (`_cycle_locks`). However, to prevent premature lockout from blocking exits, [`strategy_evaluator.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/strategy_evaluator.py) inspects:
```python
has_open_pos = any(
    p.get_position(ticker) is not None
    for p in (portfolio_domination, portfolio_macro_trend, portfolio_dominion2, portfolio_onnx, portfolio_dual_onnx)
    if p is not None
)
if is_live and active_strategy_bot not in ("market_maker", ...):
    if not has_open_pos and (cycle_key in self._guardrails._cycle_locks or ticker in self._guardrails._cycle_locks):
        return  # Entry locked, but open positions PASS THROUGH
```
If an open position exists, the cycle lock check is bypassed, guaranteeing non-stop real-time exit evaluation.

#### Quantitative Exit Rules Hierarchy
1. **Rule 1: Asymmetric Tail Risk Ceiling (`TAKE_PROFIT_CEILING`)**:
   - Condition: $P_{\text{bid}} \ge \$0.90$ (or $\$0.94$ preset) and net PnL $> \$0.00$.
   - Confirmed either unconditionally (`require_reversal_for_tp_ceiling = False`) or upon adverse reversal probability $\ge \text{threshold}$.
2. **Rule 2: High-Frequency Spot Delta Front-Runner (`SPOT_DELTA_FRONT_RUN`)**:
   - Condition: $P_{\text{bid}} \ge \$0.85$ and 3-second adverse spot velocity exceeds dynamic threshold:
     - $T_{\text{rem}} \le 60\text{s}$: Silas TWAP Gravity Veto protects positions if TWAP cushion is safe ($v_{\text{sec}} < v_{\text{crit}}$).
     - $60\text{s} < T_{\text{rem}} \le 240\text{s}$: Transition zone evaluates dynamic moneyness velocity hurdle.
     - $T_{\text{rem}} > 240\text{s}$: Macro drift $Z\text{-Score} \ge 2.25\sigma$.
3. **Rule 3: High-Water Mark Trailing Ratchet & Deep Breakeven Armor (`TRAILING_PROFIT_RATCHET`)**:
   - Tier 2 & 3: Active once peak bid reaches $\ge \$0.88$. Trails peak with a $\$0.06 - \$0.08$ buffer.
   - Tier 1 Breakeven Armor: Active once peak reached $\ge \$0.85$ with $\ge +20\text{c}$ gain from entry. Exits at entry + fee to protect capital if price collapses.
4. **Rule 4: Late-Cycle Gamma Defense (`LATE_CYCLE_HARVEST`)**:
   - Condition: $15\text{s} < T_{\text{rem}} \le 120\text{s}$, $P_{\text{bid}} \ge \$0.85$, and $\text{ROI} \ge +15\%$.
   - Prevents binary expiration coin-flip risk.
5. **Rule 5: Dynamic Reversal Take-Profit Harvest (`TAKE_PROFIT_ROI`)**:
   - Condition: $\text{ROI} \ge \text{min\_take\_profit\_roi}$ and reverse indicator probability $\ge \text{dyn\_reversal\_threshold}$.
6. **Rule 5.1: Mid-Cycle Bargain Harvest & Doubt Engine (`ASYMMETRIC_PEAK_HARVEST` / `DOUBT_PROFIT_HARVEST`)**:
   - **The Commonsense Bargain Harvest**: If entered at bargain ($P_{\text{entry}} \le \$0.45$ with $\text{ROI} \ge +70\%$, or any entry with $\text{ROI} \ge +75\%$) and $P_{\text{bid}} \ge \$0.78$ with $T_{\text{rem}} \ge 180\text{s}$ (3 to 8 minutes remaining), liquidates immediately at market.
   - **The Council Doubt-Harvest Engine**: If upside captured $\ge 50\%$ and composite Doubt Score $\ge 0.80$ (blending neural probability erosion with adverse spot velocity).
7. **Rule 5.2: Fast Taker Win Lock (`FAST_WIN_LOCK_FEE_ADVANTAGE`)**:
   - Crosses spread with a market taker order, paying the $\$0.01$ fee to lock guaranteed cash: "A win is truly a win even with fees."

---

## 4. Configuration Parameter Manifest (`data/bot_parameters.json`)

| Parameter Name | Canonical Value | Data Type | Operational Function |
| :--- | :--- | :--- | :--- |
| `min_time_remaining` | `150` | `int` | Late pin cutoff in seconds for Chop regime |
| `max_time_remaining` | `780` | `int` | Opening quarantine in seconds |
| `storm_max_time_remaining`| `840` | `int` | Maximum time allowed for Storm entries |
| `storm_min_time_remaining`| `60` | `int` | Late pin cutoff in seconds for Storm regime |
| `min_edge` | `Decimal("0.02")`| `Decimal` | Net Expected Value minimum hurdle |
| `min_probability` | `Decimal("0.58")`| `Decimal` | Floor calibrated probability threshold |
| `max_price_cents` | `Decimal("55")` | `Decimal` | Hard ceiling for buy order limit price |
| `min_price_cents` | `Decimal("38")` | `Decimal` | Hard floor for buy order limit price |
| `max_spread_cents` | `Decimal("5")` | `Decimal` | Maximum CLOB bid-ask spread permitted |
| `vpin_threshold` | `Decimal("0.65")`| `Decimal` | Maximum permissible order flow toxicity |
| `proximity_moat` | `Decimal("25.00")`| `Decimal` | Minimum absolute dollar distance to strike |
| `enable_take_profit_ceiling` | `true` | `bool` | Enables Rule 1 & Rule 5.1 ceiling harvesting |
| `take_profit_price_threshold` | `Decimal("0.90")` | `Decimal` | Rule 1 tail risk take-profit ceiling |
| `asymmetric_peak_bid` | `Decimal("0.78")` | `Decimal` | Rule 5.1 asymmetric profit harvest floor |
| `enable_trailing_ratchet` | `true` | `bool` | Enables Rule 3 high-water mark trailing ratchet |
| `trailing_ratchet_buffer` | `Decimal("0.08")` | `Decimal` | Trail buffer subtracted from peak bid |
| `late_cycle_roi` | `0.15` | `float` | Rule 4 minimum ROI hurdle for $T \le 120\text{s}$ |
| `enable_doubt_harvest` | `true` | `bool` | Enables Rule 5.1 Bayesian doubt harvester |
| `doubt_threshold` | `0.80` | `float` | Minimum composite doubt score to trigger harvest |
| `enable_fast_win_lock` | `true` | `bool` | Enables Rule 5.2 taker spread-crossing win lock |

---

## 5. Audit, Forensics & Telemetry

Every settled contract triggers an automated telemetry record containing:
1. **$T_1$ (Decision):** Timestamp, feature vector, ONNX probabilities, HMM regime, selected Warrior.
2. **$T_2$ (Fill):** Order ID, execution price, fill latency in milliseconds, order type (Maker/Taker).
3. **$T_3$ (Settlement):** Official Kalshi settlement price, gross PnL, fee drag, final win/loss tag.
4. **Causal Mistake Attribution:** If the trade settled as a loss, the Autopsy Engine assigns an attribution code (`ERR_PIN_RISK`, `ERR_VOLATILITY_EXPANSION`, `ERR_SPREAD_SLIPPAGE`, etc.) and feeds it into the Mistake Matrix in [`ContinuousExperienceBuffer`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/continuous_experience.py).
