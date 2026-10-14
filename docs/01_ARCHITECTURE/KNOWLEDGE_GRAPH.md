# Enterprise Knowledge Graph & Concept Ontology

**System:** Kalshi Autonomous Multi-Asset Trading Engine  
**Classification:** Enterprise Conceptual Ontology & Code Linkage Graph  

---

## 1. Domain Ontology Overview

The knowledge graph defines explicit semantic links between **Financial Invariants**, **Algorithmic Strategies**, **Autonomous Agents**, **Physical Code Modules**, and **Persistent Storage**.

```mermaid
graph TD
    classDef law fill:#ffebee,stroke:#c62828,stroke-width:2px;
    classDef bot fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef db fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef agent fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px;

    L1[Zero Float Financial Math]:::law -->|Governs| C_CALC[Order Simulator / Fee Matrix]
    L2[Micro-Bankroll Sizing: <= 1 Contract]:::law -->|Restricts| G_SIZE[Guardrails Sizing Agent]:::agent
    L3[1-Trade-Per-Cycle Lock]:::law -->|Locks| B1[Bot 1 V4 Engines]:::bot
    L4[Strict Asset Isolation]:::law -->|Segregates| DB_BTC[(kalshi_history.db)]:::db
    L4 -->|Segregates| DB_ETH[(kalshi_history_eth.db)]:::db

    B1 -->|Spawns| W1[Warrior 1: Storm Breakout]
    B1 -->|Spawns| W2[Warrior 2: Chop Discount]
    B1 -->|Queries| KEV[Kev AI Decision Oracle]:::agent
    B1 -->|Feeds| EXP[Continuous Experience Buffer]
    EXP -->|Online Platt / Brier Tuning| SUP[Autonomous Batch Supervisor]:::agent
    SUP -->|Triggers Every 6 Trades| GEM[AI Assessor / Gemini Forensics]:::agent

    G_SIZE -->|Enforces| L2
    WASH[Anti-Wash Trading Shield]:::agent -->|Vetoes| B1
    SEAL[Seal of Excellence]:::law -->|Verifies Checksum| B1
```

---

## 2. Concept Relationship Dictionary

| Subject Concept | Relation | Target Concept | Code / File Anchor |
| :--- | :--- | :--- | :--- |
| **Zero Float Financial Math** | enforces | All Balance & Fee Computations | [`src/kalshi_sim/order_simulator.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/order_simulator.py) |
| **Micro-Bankroll Armor** | limits sizing to | 1 Contract ($<\$75 balance) | [`docs/SCALEUP.md`](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/SCALEUP.md) |
| **1-Trade-Per-Cycle Lock** | terminates loop on | 1 Completed Round-Trip | [`src/kalshi_sim/ml/bot1_v4_engine.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/bot1_v4_engine.py) |
| **Strict Asset Isolation** | partitions | BTC vs ETH History | [`src/kalshi_sim/db/queries.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/db/queries.py) |
| **Warrior 1 (Storm)** | executes on | Momentum Breakout ($0.42–$0.45) | [`src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py) |
| **Warrior 2 (Chop)** | executes on | Deep Discount Limit ($0.38–$0.42) | [`src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py) |
| **Kev Decision Oracle** | shadow-validates | Bayesian Direction & Strike | [`src/kalshi_sim/ml/kev_oracle.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/kev_oracle.py) |
| **Platt Scaling** | calibrates | Empirical Win Probabilities | [`src/kalshi_sim/ml/experience_buffer.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/experience_buffer.py) |
| **Batch Supervisor** | orchestrates | Continuous 6-Trade Evolution | [`src/kalshi_sim/batch_supervisor.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/batch_supervisor.py) |
| **AI Assessor** | conducts | Root-Cause Forensics | [`src/kalshi_sim/ai_assessor.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ai_assessor.py) |

---

## 3. Data & Entity Relationship Graph

```mermaid
erDiagram
    TRADE ||--o| SETTLEMENT : settles_into
    TRADE ||--o| LIFECYCLE_FORENSIC : generates
    SETTLEMENT ||--o| FAILURE_AUTOPSY : triggers_on_loss
    SETTLEMENT ||--o| EXPERIENCE_RECORD : ingests_into
    EXPERIENCE_RECORD ||--o{ BATCH_ASSESSMENT : groups_into_6

    TRADE {
        string trade_id PK
        string ticker
        string bot_type
        string side
        int contracts
        decimal entry_price
        decimal fees
        string execution_mode
        int timestamp_epoch_ms
    }

    SETTLEMENT {
        string settlement_id PK
        string ticker
        string outcome
        decimal pnl
        decimal settlement_price
        decimal balance_after
        int timestamp_epoch_ms
    }

    FAILURE_AUTOPSY {
        int id PK
        string trade_id FK
        string failure_code
        boolean is_counter_trend
        boolean was_salvageable
        decimal salvageable_cents_lost
    }
```
