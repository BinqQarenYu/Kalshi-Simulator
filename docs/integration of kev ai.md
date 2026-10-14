# Institutional Specification & Task Contract: Integration of Kev AI

**Document Name:** `integration of kev ai.md`  
**Classification:** Quantitative Architecture Specification & Agent Codeflow Task Contract  
**Target Engine:** Kalshi Trading System & LangGraph Council Orchestrator  
**Model Family:** Kev AI Decision Models (`jaredpalmer/kev` by Jared Palmer)  
**Governing Laws:** AGENTS.md Laws 1 (Zero Float Math), 2 (Execution Guardrails), 7 (Zero Hallucination), 8 (Anti-Blackhole Token Conservation)  
**Status:** **RATIFIED FOR ATOMIC ASVL EXECUTION**  

---

## 1. Executive Summary & Strategic Rationale

Traditional generative LLMs (e.g. GPT-4, Gemini) generate text token-by-token. In ultra-low-latency financial decision making, this creates three critical vulnerabilities:
1. **High Latency:** Generative inferences take 1.5s–5.0s, far too slow for fast 15-minute CLOB cycles.
2. **Brittle Serialization:** Autoregressive text is prone to formatting deviations, broken JSON, and regex parsing failures.
3. **Credit/Token Burn:** Generative multi-agent debates burn thousands of cloud API credits per cycle (violating AGENTS.md Law 8).

**Kev AI** (`jaredpalmer/kev`) introduces a breakthrough architectural paradigm: **Prefill-Only Single-Forward-Pass Decision Modeling**.

```
┌────────────────────────────────────────────────────────┐
│ State Document (Context):                              │
│ Spot, Strike Distance, Tau, OFI, Micro-Price, CLOB     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Typed Questions (No Prompts/No Chat):                  │
│ 1. is_toxic_sweep: bool                                │
│ 2. regime: choice[CHOP, STORM, BLEED, HEALING]         │
│ 3. trade_direction: choice[YES, NO, WAIT]              │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼ (Single Forward Pass < 50ms)
┌────────────────────────────────────────────────────────┐
│ Calibrated Output Probabilities (Zero Float Math):     │
│ { is_toxic_sweep: Decimal("0.08"),                     │
│   regime: { CHOP: Decimal("0.82"), ... },              │
│   trade_direction: { YES: Decimal("0.85"), ... } }     │
└────────────────────────────────────────────────────────┘
```

By supplying a rich textual market state alongside structured typed questions, Kev executes a single forward pass over a frozen Qwen backbone with a pointer head, returning **exact, calibrated probability distributions in under 50ms** without generating conversational filler.

---

## 2. Blast-Radius Boundary Matrix

To guarantee that the live Ethereum trading daemon and existing BTC/ETH bots are protected against regressions, the following strict boundaries are enforced:

| Access Level | File Path | Exact Purpose |
| :--- | :--- | :--- |
| **Primary Target (Write)** | `src/kalshi_sim/ml/kev_oracle.py` | Core Kev Decision Oracle client, question types, circuit breaker, and shadow evaluator |
| **Primary Target (Write)** | `tests/test_kev_oracle.py` | Comprehensive ASVL unit and integration test suite |
| **Controlled Integration (Edit)**| `src/kalshi_sim/council/state.py` | Add typed fields for Kev evaluation scores to `CouncilState` |
| **Controlled Integration (Edit)**| `src/kalshi_sim/council/graph.py` | Add non-blocking `node_kev_evaluation` to LangGraph Council DAG |
| **Controlled Integration (Edit)**| `src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py` | Attach `KevDecisionOracle` in non-invasive **Shadow Mode** |
| **Context Only (Read-Only)** | `src/kalshi_sim/ml/experience_buffer.py` | Reference for mistake classifications and calibration |
| **Context Only (Read-Only)** | `data/seal_of_excellence.json` | Verification reference |
| **Forbidden Zone** | `src/kalshi_sim/db/**`, `data/*.db` | Existing SQLite databases and writers remain untouched |

---

## 3. Step-by-Step Granular Task Contract

```
┌────────────────────────────────────────────────────────────────────────┐
│               PHASE 1: SCHEMAS & KEV ORACLE SERVICE                    │
│      (KevQuestion, KevDecisionResult, KevDecisionOracle, Fallback)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ PASS: Zero Float & Fallback Tested
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│            PHASE 2: LANGGRAPH COUNCIL ARBITER INTEGRATION              │
│         (Typed State Containers & node_kev_evaluation in Graph)        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ PASS: Council Deliberation Verified
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│          PHASE 3: SHADOW-MODE INTEGRATION IN ETH BOT 1 V4              │
│         (Parallel Telemetry Logging without Live Route Mutating)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ PASS: Clean Non-Invasive Telemetry
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             PHASE 4: ASVL AUTOMATED VERIFICATION BATTERY               │
│               (Full Pytest Suite & Regression Verification)            │
└────────────────────────────────────────────────────────────────────────┘
```

### [Step 1: Schema & Core Oracle Client]
* **Target File:** [`src/kalshi_sim/ml/kev_oracle.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/kev_oracle.py)
* **Specific Actions:**
  1. Define `KevQuestionType` (`BOOLEAN`, `CHOICE`, `SCORE`).
  2. Define `KevQuestion` and `KevDecisionResult` with `decimal.Decimal` probabilities.
  3. Implement `KevDecisionOracle`:
     - Configurable endpoint (`/v1/systemone` or local Ollama/HTTP server).
     - Strict 80ms timeout circuit breaker: automatically falls back to deterministic rule-based heuristics if the local server is offline or times out.
     - Context builder formatting L2 orderbook, OFI, $\tau$, spot velocity, and VPIN into clean state text.
* **Definition of Done:** `KevDecisionOracle` instantiates, builds typed questions, evaluates state, and handles network timeouts without raising unhandled exceptions.

### [Step 2: LangGraph Council Arbiter Node]
* **Target Files:** [`src/kalshi_sim/council/state.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/council/state.py), [`src/kalshi_sim/council/graph.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/council/graph.py)
* **Specific Actions:**
  1. Add `kev_evaluation: Optional[Dict[str, Any]]` to `CouncilState`.
  2. Implement `node_kev_evaluation` in `graph.py` which presents the 6 councilors' votes to Kev and extracts calibrated consensus confidence.
  3. Route DAG through `node_kev_evaluation` before final solution synthesis.
* **Definition of Done:** `CouncilOrchestrator().deliberate(...)` executes end-to-end, logging calibrated Kev consensus scores.

### [Step 3: Shadow-Mode Telemetry in ETH Bot 1 V4]
* **Target File:** [`src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py)
* **Specific Actions:**
  1. Instantiate `KevDecisionOracle` in `EthBot1V4Engine.__init__`.
  2. In `run_cycle`, construct the market context document and trigger shadow evaluation in non-blocking manner.
  3. Log shadow comparison: `[KEV SHADOW ORACLE] Agreement with ONNX: True/False | Kev Conf: 84% | Decision: YES`.
  4. Preserve all live execution gates, 1-trade-per-cycle locks, and 1-contract micro-bankroll rules untouched.
* **Definition of Done:** The live runner logs Kev shadow telemetry with zero impact on order execution speed or reliability.

### [Step 4: ASVL Regression & Integrity Verification]
* **Target File:** [`tests/test_kev_oracle.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/tests/test_kev_oracle.py)
* **Specific Actions:**
  1. Author unit tests verifying:
     - Zero Float financial math on all probability fields.
     - Fallback circuit breaker behavior under simulated server downtime.
     - Question construction and single-pass answer parsing.
     - Council LangGraph DAG execution with Kev node.
  2. Run `python -m pytest tests/test_kev_oracle.py tests/test_eth_bot1v4.py tests/test_eth_db_and_learning_curve.py -q`.
* **Definition of Done:** 100% of tests pass with zero regressions across the codebase.

---

## 4. Operational Invariants Enforced

1. **Zero Float Standard:** All probabilities and scores returned by `KevDecisionOracle` are serialized as `decimal.Decimal` to prevent IEEE-754 drift.
2. **Sub-80ms Latency Budget:** Real-time cycle evaluation must never stall; the circuit-breaker aborts to baseline heuristics if inference exceeds 80ms.
3. **Micro-Bankroll Sizing Invariant:** Sizing remains locked at 1 contract max regardless of model conviction.
4. **Token Conservation:** All Kev inferences execute locally on workstation compute without external LLM API billing.
