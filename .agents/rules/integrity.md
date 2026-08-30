---
trigger: always_on
glob: "**/*"
description: Continuous code, math, latency, and truth integrity rules for Kalshi Simulator.
---

# Continuous Integrity & Truth Enforcement Rules

## 1. Zero Mathematical Tolerance
- **Strict Decimal Arithmetic**: Never calculate balances, PnL, mark prices, strike differences, or payouts with IEEE-754 floats (`float` in Python / native `number` in JS).
- **Exact Invariants**:
  - $\text{Equity} = \text{Cash Balance} + \sum \text{Unrealized PnL}$
  - $\text{Realized PnL} = \sum \text{Settlement PnL}$
  - $\text{Payout per Contract} \in \{\$1.00, \$0.00\}$

## 2. Microstructure & Latency Constraints
- **L2 CLOB Sequence Continuity**: Sequence gaps in WebSocket feeds must trigger immediate snapshot invalidation and resynchronization.
- **Uncrossed Order Books**: $\text{Best YES Bid} + \text{Best NO Bid} \le 1.00$ must hold at all times.
- **Sub-250ms Latency Guard**: Market data staleness in live regimes must remain strictly below 250ms.

## 3. Truth Ingestion & Zero-Mock Guarantee
- When `mode === 'live'`, zero mock, randomized, or synthetic data is permitted. If live exchange feeds drop, the system enters reconnection/graceful pause, never fallback to synthetic data.

## 4. Background Auditor (`Agent_integrity_check`)
- The backend `AgentIntegrityCheck` daemon runs continuously in the background to detect flaws, log invariant metrics, and broadcast real-time integrity telemetry (`GET /api/integrity/status` and WebSocket payload).

## 5. Kalshi Timer, Time & Price Invariant Rules
- **Rule Enforcement**:
  - Timer countdown $T_{\text{rem}} \in [0, 900]$ seconds for 15-minute cycles.
  - Expiration time format must terminate in `ET` with Eastern Time offset.
  - Price diff invariant: $\text{Diff} = S_t - K$ must match exactly between hero, charts, and probability models.
  - $\text{Equity} = \text{Balance} + \sum \text{Unrealized PnL}$ with zero float drift.
