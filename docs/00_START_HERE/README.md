# Kalshi Autonomous Quantitative Platform — Master Navigation Index

**System:** Kalshi Autonomous Multi-Asset High-Frequency & Quantitative Engine  
**Classification:** Enterprise Documentation Knowledge Base  
**Current Production Version:** Bot 1 V4 (Dual-Fleet: BTC Quolas & ETH Domination)  
**Active Production Branch:** `zero_hallucination_mode` (AWS EC2 `13.63.158.94`)  

---

## 1. Master Documentation Hierarchy

Welcome to the institutional knowledge system of the Kalshi Simulator. All system documentation, operational runbooks, algorithmic specifications, and forensic archives are organized into 12 structured tiers:

```
docs/
├── 00_START_HERE/           <-- You are here: Master index & quick onboarding
│   └── README.md
├── 01_ARCHITECTURE/         <-- System topology, knowledge graph, and component map
│   ├── SYSTEM_MAP.md
│   └── KNOWLEDGE_GRAPH.md
├── 02_TRADING_SYSTEM/       <-- Multi-asset bots, warriors, regions, and pricing math
│   ├── BOT1_V4_SPECIFICATION.md
│   ├── ETH_DOMINATION_SPECIFICATION.md
│   ├── DUAL_WARRIOR_4_REGIONS.md
│   ├── BIMODAL_MAKER_TAKER_RESEARCH.md
│   └── TEMPORARY_TAKER_MOMENTUM_TRIAL_SPECIFICATION.md
├── 03_AGENTS/               <-- Comprehensive agent registry, council, and truth oracles
│   └── AGENT_REGISTRY.md
├── 04_WORKFLOWS/            <-- Production workflows, failure modes, and recovery
│   └── WORKFLOW_REGISTRY.md
├── 05_DATA/                 <-- SQLite Schema V5, ring buffers, and JSON state ledgers
│   └── DATA_REGISTRY.md
├── 06_OPERATIONS/           <-- AWS EC2 deployment, systemd daemons, and runbooks
│   └── SERVICE_REGISTRY.md
├── 07_GOVERNANCE/           <-- Regulatory laws, scale-up rules, and constitutional shields
│   └── CONSTITUTION_AND_LAWS.md
├── 08_METRICS/              <-- Financial, statistical, and latency formulations
│   └── METRIC_REGISTRY.md
├── 09_REPORTS/              <-- Chronological directory of 6-trade evaluations (#91 - #133+)
│   └── ASSESSMENT_INDEX.md
├── 10_AUTONOMY/             <-- Objectives, learning loops, audit loops, and criteria
│   ├── OBJECTIVES.md
│   ├── LEARNING_LOOP.md
│   ├── AUDIT_LOOP.md
│   ├── SELF_IMPROVEMENT.md
│   └── SUCCESS_CRITERIA.md
├── diagrams/                <-- Mermaid architecture and sequence diagrams
│   ├── ARCHITECTURE_DIAGRAMS.md
│   └── WORKFLOW_DIAGRAMS.md
└── DOCUMENTATION_MIGRATION_PLAN.md  <-- Complete repo audit & migration blueprint
```

---

## 2. Core Invariants (The 5 Absolute Laws)

Every human operator and AI agent interacting with this repository is strictly bound by the Core Operational Directives defined in [`AGENTS.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/AGENTS.md):

1. **Zero Float Financial Math:** Never use IEEE-754 floating-point math (`float` in Python / native `number` in JS) for pricing, balances, or fees. Always use `decimal.Decimal` and `decimal.js`.
2. **Quantitative & Execution Guardrails:**
   - **1-Trade-Per-Cycle:** Once an engine enters a 15M cycle, it locks until expiration.
   - **Micro-Bankroll Sizing:** Strictly 1 contract per trade while equity is under $\$50.00$.
   - **Seal of Excellence:** Live capital deployment requires a verified SHA-256 seal on disk.
3. **ASVL (Autonomous Self-Verification Loop):** Always execute local and remote test suites (`pytest`) before declaring any task complete.
4. **Token & Context Bloat Hygiene:** Never read entire `.jsonl` files or unbounded logs. Use bounded slices and batch tool calls.
5. **Upgrade & Cache Invalidation Protocol (Law 6):** When upgrading models or code, forcefully apply changes by restarting background daemons and clearing RAM caches. Do not assume hot-reloading works.

---

## 3. Fast-Track Navigation for Operators

- **To inspect system components & services:** Read [`docs/01_ARCHITECTURE/SYSTEM_MAP.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/01_ARCHITECTURE/SYSTEM_MAP.md) and [`docs/06_OPERATIONS/SERVICE_REGISTRY.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/06_OPERATIONS/SERVICE_REGISTRY.md).
- **To understand how trades are executed:** Read [`docs/diagrams/WORKFLOW_DIAGRAMS.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/diagrams/WORKFLOW_DIAGRAMS.md) and [`docs/04_WORKFLOWS/WORKFLOW_REGISTRY.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/04_WORKFLOWS/WORKFLOW_REGISTRY.md).
- **To review agent roles & KPIs:** Read [`docs/03_AGENTS/AGENT_REGISTRY.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/03_AGENTS/AGENT_REGISTRY.md).
- **To audit database schemas & tables:** Read [`docs/05_DATA/DATA_REGISTRY.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/05_DATA/DATA_REGISTRY.md).
- **To check scale-up milestones:** Read [`docs/10_AUTONOMY/SUCCESS_CRITERIA.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/10_AUTONOMY/SUCCESS_CRITERIA.md).
