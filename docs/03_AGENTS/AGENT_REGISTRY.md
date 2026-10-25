# Master Agent Registry & Quantitative Fleet Manifest

**Governance Standard:** AGENTS.md Multi-Agent Council & Autonomous Execution Framework  
**Verification Standard:** ASVL (Autonomous Self-Verification Loop) & Empirical Telemetry  

---

## 1. Fleet Overview

The Kalshi Simulator operates an autonomous, hierarchical multi-agent fleet structured into 4 operational tiers:
1. **Execution Vessels:** Bot 1 V4 Engines (BTC Quolas & ETH Domination).
2. **Sub-Tactical Execution Warriors:** Warrior 1 (Storm Breakout) & Warrior 2 (Chop Harvester).
3. **Advisory, Forensics & Risk Oracles:** Kev AI, Guardrails, Wash Coordinator, Experience Buffer, Batch Supervisor.
4. **Institutional Council & Truth Guardians:** Agent QuoQuo, Agent POE, Agent Law & Order, Councilors (Silas, Nash, Elena, Koko, Vance, Dexter, Atticus).

---

## 2. Core Agent Specifications

### 2.1 Bot 1 V4 (BTC Quolas Execution Engine)
- **Primary Source:** [`src/kalshi_sim/ml/bot1_v4_engine.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/bot1_v4_engine.py)
- **Why do I exist?** To capture statistical edges in 15-minute Bitcoin (`KXBTC15M`) binary options using real-time Binance Order Book Imbalance (OBI) and HMM regime tracking.
- **What value do I create?** Generates positive mathematical expectancy while enforcing strict 1-trade-per-cycle locks and micro-bankroll sizing armor.
- **How am I measured?** Win Rate ($\ge 60\%$), Profit Factor ($\ge 1.50$), Brier Calibration Score ($< 0.25$), Zero Wash Violations.
- **How do I improve?** Autonomous feedback loops driven by 6-trade batch supervisor autopsies and Platt scaling adjustments in the Experience Buffer.

### 2.2 Bot 1 V4 (ETH Domination Execution Engine)
- **Primary Source:** [`src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py)
- **Why do I exist?** To execute dedicated, asset-isolated 15-minute Ethereum (`KXETH15M`) binary options contracts without cross-asset BTC contamination.
- **What value do I create?** Deploys dual-warrior execution (breakout vs deep maker discount) calibrated to Ethereum's specific dispersion and tick dynamics.
- **How am I measured?** Realized Net PnL, Win Rate ($\ge 60\%$), Execution Latency ($< 500\text{ms}$), Slippage ($0.0\text{¢}$).
- **How do I improve?** Ingests pure ETH cycle experiences into `data/kalshi_history_eth.db` and queries shadow consensus from Kev AI Oracle.

### 2.3 Warrior 1: Storm Hunter (Momentum & Breakout)
- **Primary Source:** Embedded within `Bot1V4Engine` and `EthBot1V4Engine`.
- **Why do I exist?** To capitalize on high-volatility regime expansions and directional orderflow runs when spot price breaks away from strike.
- **What value do I create?** Enters high-conviction breakout trades ($0.42–$0.45 pricing) before market makers widen spreads or reprice binary probabilities.
- **How am I measured?** Breakout success rate, adverse excursion post-fill, speed of fill ($T_2 - T_1 < 250\text{ms}$).
- **How do I improve?** Dynamically scales strike proximity buffer during double-wick volatility spikes.

### 2.4 Warrior 2: Chop Harvester (Mean-Reversion Maker)
- **Primary Source:** Embedded within `Bot1V4Engine` and `EthBot1V4Engine`.
- **Why do I exist?** To harvest retail spread inefficiencies and time decay during compressed, range-bound market conditions.
- **What value do I create?** Captures deep-discount limit entries ($0.38–$0.42) with zero Kalshi taker fees between 150s and 450s before expiration.
- **How am I measured?** Limit fill rate, profit factor in Chop regions, avoided theta traps.
- **How do I improve?** Tightens entry bounds when Orderflow Variance (VPIN) exceeds 0.25.

### 2.5 Kev AI Decision Oracle (Shadow Co-Pilot)
- **Primary Source:** [`src/kalshi_sim/ml/kev_oracle.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/kev_oracle.py)
- **Why do I exist?** To act as a zero-overhead, sub-2ms heuristic and probabilistic directional validator for every proposed order.
- **What value do I create?** Detects subtle misalignments between orderflow imbalance and strike geometry, providing instant validation or vetoes.
- **How am I measured?** Recommendation accuracy, agreement rate with engine wins, sub-2ms response latency.
- **How do I improve?** Continuously cross-references settled outcomes against shadow recommendations in `data/eth_win_loss_reports.json`.

### 2.6 Autonomous Batch Supervisor
- **Primary Source:** [`src/kalshi_sim/batch_supervisor.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/batch_supervisor.py)
- **Why do I exist?** To audit live trading performance in non-overlapping 6-trade batches and dynamically apply validated parameter tweaks.
- **What value do I create?** Eliminates human latency in adjusting parameters to changing volatility regimes while strictly containing parameter blast-radius.
- **How am I measured?** Batch pass rate ($\ge 4\text{W}-2\text{L}$), reduction in repeated failure codes, zero parameter regressions.
- **How do I improve?** Evaluates failure autopsies against deterministic quant playbooks and writes structured markdown chronicles to `docs/`.

### 2.7 AI Forensic Assessor (Gemini Diagnostic Core)
- **Primary Source:** [`src/kalshi_sim/ai_assessor.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ai_assessor.py)
- **Why do I exist?** To conduct zero-hallucination, unvarnished forensic autopsies on completed 6-trade batches.
- **What value do I create?** Converts raw cycle telemetry, orderbook dynamics, and loss codes into actionable parameter modifications and failure scorecards.
- **How am I measured?** Audit factual accuracy, adherence to allowed parameter ranges, prevention of avoidable loss repetitions.
- **How do I improve?** Grounds every assessment strictly in empirical database rows (`trade_failure_autopsies`) and AGENTS.md laws.

### 2.8 Continuous Experience Buffer & Platt Calibrator
- **Primary Source:** [`src/kalshi_sim/ml/experience_buffer.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/experience_buffer.py)
- **Why do I exist?** To maintain rolling memory of settled trade experiences and calibrate raw model probabilities against exchange reality.
- **What value do I create?** Computes online Brier scores and dynamically scales Platt $\alpha$ and $\beta$ multipliers to eliminate model overconfidence.
- **How am I measured?** Brier score calibration error ($\Delta < 0.05$), Platt alpha stability ($0.8 \le \alpha \le 1.2$).
- **How do I improve?** Prunes underperforming regime quadrants and price deciles across settled cycles.

### 2.9 Guardrails & Micro-Bankroll Sizing Agent
- **Primary Source:** [`src/kalshi_sim/guardrails.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/guardrails.py), [`.agents/skills/agent-guardrails/SKILL.md`](file:///.agents/skills/agent-guardrails/SKILL.md)
- **Why do I exist?** To protect trading capital against ruinous loss streaks, fat-finger sizing errors, and account drawdowns.
- **What value do I create?** Enforces strict 1-contract micro-bankroll caps, consecutive loss circuit breakers (3 losses = pause), and daily drawdown stops.
- **How am I measured?** Zero capital-depletion incidents, 100% adherence to scale-up thresholds ($40 and $50 gates).
- **How do I improve?** Tightens risk constraints in high-bleed regimes and increases cooldowns during abnormal exchange spread widening.

### 2.10 Anti-Wash Trading & Execution Coordinator
- **Primary Source:** [`src/kalshi_sim/live_coordinator.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/live_coordinator.py), [`.agents/skills/agent-law-order/SKILL.md`](file:///.agents/skills/agent-law-order/SKILL.md)
- **Why do I exist?** To guarantee regulatory compliance with CFTC wash-trading rules and prevent multi-bot trade cannibalism.
- **What value do I create?** Synchronously acquires atomic in-flight locks before order submission; blocks opposing side entries on the same market.
- **How am I measured?** Zero wash trades executed, zero double-order bursts, 100% lock release durability.
- **How do I improve?** Benchmarks lock acquisition overhead ($< 5\text{ms}$) and audits order intent queues.

### 2.11 Agent QuoQuo (Archivist & Ground-Truth Oracle)
- **Primary Source:** [`.agents/skills/agent-quoquo/SKILL.md`](file:///.agents/skills/agent-quoquo/SKILL.md)
- **Why do I exist?** To act as the authoritative repository librarian, distinguishing canonical production logic from scratch code and graveyard artifacts.
- **What value do I create?** Protects LLM token contexts by delivering precise catalog cards and preventing redundant codebase re-inventing.
- **How am I measured?** Accuracy of citations, zero hallucinations of file paths, and adherence to read-only authority.
- **How do I improve?** Updates the Master Index and catalogs newly established architectural patterns daily.

### 2.12 Agent POE (Post-Occupancy Evaluator & LangGraph Quant Engine)
- **Primary Source:** [`.agents/skills/agent-poe/SKILL.md`](file:///.agents/skills/agent-poe/SKILL.md), [`src/kalshi_sim/ml/poe_graph_evaluator.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/poe_graph_evaluator.py)
- **Why do I exist?** To serve as the cold empirical truth auditor and quantitative reasoning engine, executing a 5-stage LangGraph workflow to isolate failure mechanisms and compute closed-form parameter calibrations.
- **What value do I create?** Audits code reality against user requirements, flags fantasy approvals, and certifies production readiness.
- **How am I measured?** Zero false passes, 100% empirical grounding in `pytest` test outputs and physical system telemetry.
- **How do I improve?** Stress-tests edge cases and refuses certification whenever an invariant is breached.

### 2.13 Council of Specialized Advisors
- **Primary Source:** [`src/kalshi_sim/council/`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/council/)
- **Advisors:**
  1. **Silas:** TWAP gravity & CF Benchmarks 60s pin auditor.
  2. **Nash:** CLOB orderbook microstructural imbalance specialist.
  3. **Elena:** Statistical arbitrage and market maker spread optimizer.
  4. **Koko:** Retail positioning inversion and psychological liquidity traps.
  5. **Vance:** Institutional delta flow and smart volume tracker.
  6. **Dexter:** Adversarial exploit hunter and edge stress-tester.
  7. **Atticus:** Chief council moderator and consensus synthesizer.
- **Why do we exist?** To provide adversarial, multi-perspective quantitative debate on edge sustainability before capital deployment.
- **What value do we create?** Stress-tests trading parameters across 7 orthogonal market hypotheses, filtering out false signals.
- **How are we measured?** Strategy win rate, drawdown avoidance during macro regime shifts.
- **How do we improve?** Re-weights advisor consensus voting based on trailing predictive accuracy.
