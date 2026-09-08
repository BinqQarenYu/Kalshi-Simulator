---
name: agent-guardrails
description: Autonomous risk management, anti-kamikaze sizing, 2-trade-per-cycle locks, execution cooldown throttles, and instant entry telemetry guardian for Kalshi trading.
---

# Agent_Guardrails — Quantitative Risk & Self-Preservation Guardian

## Overview
`AgentGuardrails` is the autonomous pre-trade risk and execution safety governor for the Kalshi algorithmic trading platform. It ensures the trading bots execute with high conviction ("aggressive alpha capture") while strictly preventing bankroll wipeouts, unthrottled loop executions, and missing trade reporting.

## Key Capabilities & Guardrails
1. **1-Contract per Trade & Max 2-Shares Cycle Hard Cap**: Strictly clamps each order to 1 contract at $0.48, and hard-caps total cycle exposure to at most 2 contracts ($0.96 max risk).
2. **In-Flight Concurrency Lock (Anti-Burst)**: Immediately reserves the cycle upon pre-trade approval and enforces an async mutex (`_eval_lock`) to prevent concurrent market ticks from firing duplicate orders.
3. **Order Throttle & Cooldown**: Enforces a mandatory time gap (default: 45s) between order attempts.
4. **Anti-Kamikaze Bankroll Sizing & Sole Authorization**: Only `3-Step Dominion` is authorized to trade (all other bots 0 contracts).
5. **Drawdown & Loss Streak Taper**: Automatically scales down sizing or triggers the 3-loss streak emergency disarm breaker.
6. **Instant Inception Telemetry**: Generates immediate trade entry reports upon execution.
7. **Institutional Lessons Learned**: See `.agents/skills/lessons-learned/SKILL.md` for post-mortem forensics and anti-regression protocols.
