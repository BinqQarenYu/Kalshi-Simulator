# Master Workflow Diagrams (Mermaid)

**Classification:** Algorithmic Workflow & Operational Process Sequences  
**Standard:** Mermaid Sequence & Flowchart Specification  

---

## 1. Trade Execution & Settlement Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant MKT as Binance / Coinbase L2
    participant BOT as Bot 1 V4 Engine
    participant KEV as Kev Decision Oracle
    participant COORD as Live Coordinator
    participant EXCH as Kalshi CLOB API
    participant TWAP as CF Benchmarks TWAP
    participant SETTLE as Server Settlements
    participant DB as SQLite DB Writer
    participant SUP as Batch Supervisor

    MKT->>BOT: Depth20 L2 Snapshot & AggTrade Tick
    BOT->>BOT: Compute OFI, VPIN & Bayesian P(win)
    BOT->>KEV: Query Shadow Oracle Validation
    KEV-->>BOT: Heuristic Bias (YES/NO/WAIT, Conf, Latency)
    
    rect rgb(240, 248, 255)
        Note over BOT,COORD: Regulatory & Risk Arbitration
        BOT->>COORD: Request Synchronous In-Flight Lock
        COORD->>COORD: Verify No Wash Trade & Balance Sizing
        COORD-->>BOT: Lock Granted (15s TTL)
    end

    BOT->>EXCH: Submit Signed Limit Order (1 Contract)
    EXCH-->>BOT: Order Placed (ID, T1 Timestamp)
    EXCH->>BOT: Fill Event (Price, Size, T2 Timestamp)
    BOT->>DB: Enqueue Trade & Lifecycle Forensics

    Note over BOT: 1-Trade-Per-Cycle Lock Activated

    rect rgb(255, 250, 240)
        Note over TWAP,SETTLE: Contract Expiration (T3)
        TWAP->>SETTLE: 60s Trailing TWAP Parity Price
        EXCH->>SETTLE: Official Settlement Notification
        SETTLE->>SETTLE: Zero Float Financial Math (Decimal PnL)
        SETTLE->>DB: Enqueue Settlement & Failure Autopsy
    end

    SETTLE->>SUP: Increment Settled Trade Counter
    opt Counter reaches 6 trades
        SUP->>SUP: Trigger 6-Trade Autonomous Evolution Cycle
    end
```

---

## 2. 6-Trade Autonomous Batch Evaluation & Healing Loop

```mermaid
flowchart TD
    CYCLE_END[Trade Settlement Event] --> ACCUM{Accumulated Matching Trades == 6?}
    ACCUM -->|No| WAIT_NEXT[Wait for Next Expiration]
    ACCUM -->|Yes| LOCK_BATCH[Freeze 6-Trade Window & Load Forensics]

    LOCK_BATCH --> QUERY_AUTOPSY[Query Failure Autopsies from Isolated DB]
    QUERY_AUTOPSY --> COMPUTE_METRICS[Compute Net Batch PnL, Win Rate & Brier Score]

    COMPUTE_METRICS --> EVAL_GATE{Batch Win Rate >= 4W-2L and PnL > $0.00?}

    EVAL_GATE -->|PASSED| GEMINI_TWEAK[Gemini Assessor Proposes Parameter Tweaks]
    GEMINI_TWEAK --> VALIDATE_TWEAK{Verify Tweaks Inside Allowed Blast-Radius?}
    VALIDATE_TWEAK -->|Valid| APPLY_PARAM[Persist Updated Parameters to bot_parameters.json]
    VALIDATE_TWEAK -->|Invalid / Out of Bounds| DISCARD_TWEAK[Discard Tweak & Keep Safe Defaults]

    EVAL_GATE -->|FAILED / DEFICIT| HEAL_MODE[Trigger Probationary Healing Mode]
    HEAL_MODE --> TIGHTEN_RISK[Tighten Proximity Moats & Enforce Min Hurdle Rate]

    APPLY_PARAM --> GEN_REPORT[Generate assessment_YYYY-MM-DD_#NUM_ASSET_.md]
    DISCARD_TWEAK --> GEN_REPORT
    TIGHTEN_RISK --> GEN_REPORT

    GEN_REPORT --> ASYNC_NOTIFY[Dispatch Async Email / UI Telemetry]
    ASYNC_NOTIFY --> RESET_COUNTER[Reset Batch Accumulator to 0]
```
