# Script to synchronize documentation with Dynamic Shadow Re-Admission Engine

# 1. Update OPERATIONAL_SCHEDULE_QATAR_TIME.md
with open('docs/02_TRADING_SYSTEM/OPERATIONAL_SCHEDULE_QATAR_TIME.md', 'r', encoding='utf-8') as f:
    text = f.read()

dynamic_section = """
---

## 3. Dynamic Shadow Re-Admission Engine ("Looking Forward While Looking at the Past")

Markets are non-stationary. A region that was historically a "losing chop zone" may transform into a high-momentum winning session as macro liquidity shifts. To ensure the bot adapts without risking capital blindly, the fleet deploys **Autonomous Shadow Re-Admission**:

```mermaid
stateDiagram-v2
    direction LR
    SHADOW : Shadow Observation (Zero Capital)
    PROBATION : Probationary Live (1 Contract)
    GOLDEN : Approved Golden Window (Full Live)

    SHADOW --> PROBATION : >= 3 Consecutive Winning Shadow Cycles
    PROBATION --> SHADOW : 1-Loss Reversion Shield (Instant Revocation)
    PROBATION --> GOLDEN : Trailing Win Rate >= 65% across 10 Cycles
```

### Operational Rules:
1. **Shadow Mode Observation**: During off-peak or non-golden hours, the bot actively streams Binance L2 order flow and generates ONNX inferences. Zero capital is committed.
2. **Dynamic Re-Admission Gate**: If an off-peak session records **$\ge 3$ consecutive winning shadow cycles**, it is promoted to `PROBATIONARY_LIVE` status in [`session_dynamic_readmission.json`](file:///f:/012D_TRADE/Kalshi%20Simulator/data/session_dynamic_readmission.json).
3. **1-Loss Reversion Shield**: Any probationary hour that incurs a single real-capital loss is immediately stripped of live trading authority and returned to Shadow Mode.
4. **Dynamic Storm Breakout Override**: If a sudden macro breakout occurs during an off-peak hour ($|S - K| \ge \$10.00$ on ETH / $\$85.00$ on BTC in confirmed STORM regime), the time filter dynamically grants a 1-cycle execution pass.
"""

if "## 3. Dynamic Shadow Re-Admission Engine" not in text:
    text += dynamic_section
    with open('docs/02_TRADING_SYSTEM/OPERATIONAL_SCHEDULE_QATAR_TIME.md', 'w', encoding='utf-8') as f:
        f.write(text)

# 2. Update AGENT_REGISTRY.md
with open('docs/03_AGENTS/AGENT_REGISTRY.md', 'r', encoding='utf-8') as f:
    text = f.read()

old_guard = "### 2.9 Guardrails & Micro-Bankroll Sizing Agent"
new_guard = """### 2.8 Dynamic Session Timing & Shadow Re-Admission Engine
- **Primary Source:** [`src/kalshi_sim/ml/session_timing_guard.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/session_timing_guard.py)
- **Why do I exist?** To balance historical win-rate priors with real-time market evolution by maintaining strict Golden Sessions while dynamically re-admitting off-peak hours that demonstrate consistent shadow profitability.
- **What value do I create?** Eliminates the $150.01 toxic dead-zone drawdown while continuously observing live L2 ticks to unlock new emerging trading regimes.
- **How am I measured?** Zero capital bleed in unproven hours, latency of shadow promotion (< 100ms), 100% adherence to the 1-loss reversion shield.

### 2.9 Guardrails & Micro-Bankroll Sizing Agent"""

if "### 2.8 Dynamic Session Timing" not in text:
    text = text.replace(old_guard, new_guard)
    with open('docs/03_AGENTS/AGENT_REGISTRY.md', 'w', encoding='utf-8') as f:
        f.write(text)

print("Documentation successfully updated with Dynamic Shadow Re-Admission specifications!")
