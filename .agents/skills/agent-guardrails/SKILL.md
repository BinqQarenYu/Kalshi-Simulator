---
name: agent-guardrails
description: Autonomous risk management, anti-kamikaze sizing, 1-trade-per-cycle locks, execution cooldown throttles, and instant entry telemetry guardian for Kalshi trading.
---

# Agent_Guardrails — Quantitative Risk & Self-Preservation Guardian

## Overview
`AgentGuardrails` is the autonomous pre-trade risk and execution safety governor for the Kalshi algorithmic trading platform. It ensures the trading bots execute with high conviction ("aggressive alpha capture") while strictly preventing bankroll wipeouts, unthrottled loop executions, and missing trade reporting.

## Key Capabilities & Guardrails
1. **1-Trade-Per-Cycle Lock**: Restricts automated systems to at most 1 trade entry per 15-minute / 5-minute contract cycle.
2. **Order Throttle & Cooldown**: Enforces a mandatory time gap (default: 45s) between order attempts.
3. **Anti-Kamikaze Bankroll Sizing**: Restricts allocation to 5–10% max equity risk and caps micro-bankrolls at 1–4 contracts.
4. **Drawdown & Loss Streak Taper**: Automatically scales down sizing to 1 contract if consecutive losses or drawdowns occur.
5. **Instant Inception Telemetry**: Generates immediate trade entry reports upon execution.
