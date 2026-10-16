# Degree-of-Freedom (DoF) Autonomous Repair Protocol & 6-Trade Evaluation Circuit

## 1. Executive Summary & Philosophy

In algorithmic trading on high-frequency binary option CLOBs (such as Kalshi 15-minute events), **static hard-coding of every theoretical edge-case filter strangles the trading engine's Degrees of Freedom (DoF)**. Excessive upfront constraints create "paralysis by analysis," leading to zero fills, missed high-probability setups, and overfitted rules that underperform when market regimes shift.

The **Degree-of-Freedom (DoF) Autonomous Repair Protocol** establishes a dual-speed architecture:
1. **Unrestricted Baseline Freedom:** During clean market regimes (where the fleet is winning $\ge 67\%$ of 15m cycles), both ETH and BTC engines operate with maximum degrees of freedom, capturing clean spreads, high EV momentum, and decisive taker executions.
2. **Autonomous Empirical Remediation:** The system audits trading performance in **6-trade evaluation batches**. The moment a specific failure fingerprint (e.g., `ERR_DISPERSION_EXCURSION`, `ERR_TWAP_PIN_VICTIM`, `ERR_DOOMED_HOLD_TO_ZERO`) is empirically recorded in settled trades, the corresponding **DoF Patch** is automatically armed.
3. **Graceful De-escalation:** If an armed patch operates for 18 consecutive trades (3 batches) with zero occurrences of the error and positive net PnL, the governor automatically de-escalates back to baseline freedom.

---

## 2. The DoF Patch Matrix & Error Fingerprints

```
                                [ 6-TRADE BATCH SETTLEMENT ]
                                             |
             +-------------------------------+-------------------------------+
             |                               |                               |
[ ERR_DISPERSION_EXCURSION ]      [ ERR_TWAP_PIN_VICTIM ]         [ ERR_DOOMED_HOLD_TO_ZERO ]
             |                               |                               |
       DoF-01: Armed                   DoF-02: Armed                   DoF-03: Armed
   Dynamic Volatility Moat         60s Trailing TWAP Guard        Stepped Liquidity Salvage
```

### Detailed Patch Taxonomy

| Patch ID | Target Error Code | Empirical Trigger Condition (in 6-Trade Batch) | Autonomous Remediation Action | De-escalation Condition |
| :--- | :--- | :--- | :--- | :--- |
| **DoF-01** | `ERR_DISPERSION_EXCURSION` | $\ge 1$ loss where spot crossed strike mid-cycle without toxic order flow | Replaces static entry moat with rolling 1m volatility scaling: $\text{Moat} = \max(\text{BaseMoat}, \; 2.0 \cdot \sigma_{\text{1m}} \cdot \sqrt{\tau/60})$. In early cycle ($\tau > 720\text{s}$), doubles moat requirement. | 18 consecutive cycles with 0 dispersion excursions and WR $\ge 67\%$. |
| **DoF-02** | `ERR_TWAP_PIN_VICTIM` | $\ge 1$ loss where spot price was favorable at expiry but CME CF Benchmarks 60s TWAP failed | Enforces continuous 60s TWAP integral calculation during $\tau \in [1\text{s}, 60\text{s}]$. If remaining seconds cannot mathematically pull the average across the strike, executes immediate salvage. | 18 consecutive cycles with 0 TWAP pin failures. |
| **DoF-03** | `ERR_DOOMED_HOLD_TO_ZERO` | $\ge 1$ loss where contract expired to $\$0.00$ because resting book bids were $<\$0.15$ | Activates stepped salvage cascade down to $\$0.10$ if adverse OFI exceeds $-0.70$, salvaging remaining capital before orderbook liquidity completely evaporates. | 18 consecutive cycles with 0 hold-to-zero wipeouts. |
| **DoF-04** | `ERR_SALVAGE_WHIPSAW` | $\ge 1$ trade salvaged at a loss, but the market subsequent to exit rebounded and would have won | Enforces a 2-tick persistence filter ($\ge 3$ consecutive seconds of adverse spot) + confirmed negative OFI before triggering salvage at $\tau > 300\text{s}$. | 18 consecutive cycles with 0 whipsaw premature exits. |
| **DoF-05** | `ERR_MOMENTUM_EXHAUSTION` | $\ge 1$ loss entered at the extreme top or bottom of an overextended wick | Blocks taker orders when 3m RSI $> 80$ or upper/lower wick-to-body ratio $> 2.5\times$ (Barnaby Retail Inversion Gate). | 18 consecutive cycles with 0 wick exhaustion traps. |

---

## 3. Architecture & Data Structures

### State File: `data/active_dof_patches.json`
The live patch state is tracked per asset (`ETH` and `BTC`) and loaded atomically with zero float overhead:

```json
{
  "version": "1.0",
  "last_updated": "2026-10-16T07:30:00Z",
  "ETH": {
    "dof_01_vol_moat": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_DISPERSION_EXCURSION",
      "cycles_since_activation": 0,
      "params": { "k_vol_mult": 2.0, "early_cycle_mult": 2.0 }
    },
    "dof_02_twap_guard": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_TWAP_PIN_VICTIM",
      "cycles_since_activation": 0,
      "params": { "window_seconds": 60, "min_margin_cents": 0.01 }
    },
    "dof_03_stepped_salvage": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_DOOMED_HOLD_TO_ZERO",
      "cycles_since_activation": 0,
      "params": { "floor_price": "0.10", "ofi_urgency_threshold": -0.70 }
    },
    "dof_04_salvage_persistence": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_SALVAGE_WHIPSAW",
      "cycles_since_activation": 0,
      "params": { "persistence_seconds": 3.0, "tau_gate_seconds": 300.0 }
    },
    "dof_05_anti_exhaustion": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_MOMENTUM_EXHAUSTION",
      "cycles_since_activation": 0,
      "params": { "rsi_ceiling": 80.0, "wick_ratio_ceiling": 2.5 }
    }
  },
  "BTC": {
    "dof_01_vol_moat": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_DISPERSION_EXCURSION",
      "cycles_since_activation": 0,
      "params": { "k_vol_mult": 2.0, "early_cycle_mult": 2.0 }
    },
    "dof_02_twap_guard": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_TWAP_PIN_VICTIM",
      "cycles_since_activation": 0,
      "params": { "window_seconds": 60, "min_margin_cents": 0.01 }
    },
    "dof_03_stepped_salvage": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_DOOMED_HOLD_TO_ZERO",
      "cycles_since_activation": 0,
      "params": { "floor_price": "0.10", "ofi_urgency_threshold": -0.70 }
    },
    "dof_04_salvage_persistence": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_SALVAGE_WHIPSAW",
      "cycles_since_activation": 0,
      "params": { "persistence_seconds": 3.0, "tau_gate_seconds": 300.0 }
    },
    "dof_05_anti_exhaustion": {
      "active": false,
      "triggered_in_batch": null,
      "error_code": "ERR_MOMENTUM_EXHAUSTION",
      "cycles_since_activation": 0,
      "params": { "rsi_ceiling": 80.0, "wick_ratio_ceiling": 2.5 }
    }
  }
}
```

---

## 4. Integration with Autonomous Batch Supervisor

1. At the completion of each 6-trade evaluation batch, `AutonomousBatchSupervisor.evaluate_batch()` extracts settled trades.
2. The `DofPatchGovernor` scans the failure codes of any losses.
3. If an error matches an active deficiency trigger, the governor updates `data/active_dof_patches.json`.
4. The live engines (`EthBot1V4Engine` and `BtcBot1V4Engine`) load active patches dynamically at the beginning of each cycle, enforcing the patch without needing process restarts or dropping ticks.
5. All transitions are logged with Quant Council telemetry for complete forensic auditability.
