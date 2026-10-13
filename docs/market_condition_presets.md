# Market Condition Presets Documentation

## Overview

The `AgentGuardrails` class includes a **market condition presets** feature that allows the trading bot to dynamically adjust its guardrail parameters based on a high‑level market regime. This helps the bot stay adaptive to volatility, liquidity, and risk characteristics that differ throughout the trading day.

## Preset Definitions

| Condition | Description | `min_order_interval_seconds` | `max_risk_pct_per_trade` | `vpin_toxic_threshold` |
|-----------|-------------|-----------------------------|--------------------------|------------------------|
| **choppy** | Aggressive, fast‑moving market with frequent price swings. | 5.0 | 0.10 (10 % of equity) | 0.80 |
| **stormy** | Highly volatile environment often driven by major news releases. | 5.0 | 0.15 (15 % of equity) | 0.85 |
| **bleed** | Moderately volatile market where risk is rising but not extreme. | 10.0 | 0.20 (20 % of equity) | 0.90 |
| **heal** | Calm, low‑volatility market – the safest regime. | 30.0 | 0.05 (5 % of equity) | 0.70 |

*All numeric values are the defaults that will be applied when the corresponding condition is selected.*

## How It Works

- The presets are stored in a private dictionary `_MARKET_PRESETS` inside `AgentGuardrails.__init__`.
- The method `apply_market_condition(self, condition: str) -> None` looks up the preset by name.
- If the condition is recognized, each key/value pair in the preset is **set on the instance** using `setattr`, effectively overriding the current guardrail settings.
- A log entry is emitted for every updated attribute:
  ```python
  logger.info("Guardrail %s set to %s due to %s market condition", key, value, condition)
  ```
- If an unknown condition is supplied, a warning is logged and no changes are made.

## Usage Example

```python
from kalshi_sim.agent_guardrails import AgentGuardrails

# Initialise guardrails with default parameters
guardrails = AgentGuardrails()

# Switch to a more aggressive regime during a volatile period
guardrails.apply_market_condition("stormy")

# The guardrail attributes have now been updated:
print(guardrails.min_order_interval_seconds)  # => 5.0
print(guardrails.max_risk_pct_per_trade)     # => Decimal('0.15')
print(guardrails.vpin_toxic_threshold)      # => 0.85
```

## Extending the Presets

If you need additional market regimes, you can extend `_MARKET_PRESETS` by subclassing `AgentGuardrails` or by directly modifying the dictionary after instantiation:

```python
class CustomGuardrails(AgentGuardrails):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._MARKET_PRESETS["custom"] = {
            "min_order_interval_seconds": 2.0,
            "max_risk_pct_per_trade": Decimal("0.12"),
            "vpin_toxic_threshold": 0.75,
        }

# Now you can apply the custom condition
custom = CustomGuardrails()
custom.apply_market_condition("custom")
```

## Integration Points

- **Risk Management** – The adjusted `max_risk_pct_per_trade` directly influences the bankroll sizing logic in `validate_pre_trade_intent`.
- **Order Throttling** – Changing `min_order_interval_seconds` alters the cooldown throttling for automated bots.
- **Adverse‑Selection Protection** – The `vpin_toxic_threshold` feeds into the VPIN toxicity veto, preventing trades when order‑flow toxicity is too high.

By leveraging these presets, the simulation can more realistically reflect how professional desks adjust their risk appetite throughout different market conditions.
