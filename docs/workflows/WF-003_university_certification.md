# WF-003: University Certification & Seal of Excellence

> **Workflow ID:** WF-003  
> **Classification:** Automated Strategy Governance & Certification  
> **Frequency:** On-Demand (triggered when candidate bot passes incubation phase)  
> **Prerequisites:** Lane 2 Incubator maturity, zero-loss safety violations, mathematical invariant adherence.

---

## 1. Overview & Objective

The **University Certification & Seal of Excellence** gauntlet is the sovereign gatekeeper governing real-money trading authorization across the Kalshi algorithmic terminal.

In accordance with institutional standards:
- **Zero Bypass Rule**: No autonomous bot may deploy live real capital without a valid, automated SHA-256 Seal of Excellence written to disk (data/seal_of_excellence.json).
- **Target Bots**:
  - Bot 1: 3_step_domination_bot (Certified)
  - Bot 3: macro_trend_dominion (Certified)
  - Bot 2: dual_onnx (Lane 2 Incubator Candidate)

---

## 2. Certification Gauntlet Standards

To earn a cryptographic Seal of Excellence, a candidate bot must execute across multi-regime historical market feeds and satisfy strict empirical thresholds:

| Invariant / Metric | Standard Required | Failure Action |
| :--- | :--- | :--- |
| **Financial Math** | Strict Decimal arithmetic (Zero float tolerance) | Immediate Disqualification |
| **Win Rate** | >= 78.5% across >= 250 contiguous cycles | Retention in Lane 2 |
| **Profit Factor** | >= 1.85 post-Kalshi taker fee deduction | Retention in Lane 2 |
| **Max Drawdown** | <= 12.0% of cumulative equity curve | Retention in Lane 2 |
| **CFTC Wash-Trading Shield** | 100% rejection of opposing cycle orders | Immediate Disqualification |
| **In-Flight Intent Lock** | Sub-millisecond race condition prevention | Immediate Disqualification |

---

## 3. Step-by-Step Execution Guide

### Step 1: Pre-Gauntlet Invariant Verification
Before running the gauntlet, verify backend unit tests and mathematical invariants:
`ash
python -m pytest tests/test_trading_invariants.py -v
python -m pytest tests/test_seal_of_excellence.py -v
`

### Step 2: Triggering On-Demand University Test Gauntlet
The user explicitly commands: check bot if it is time to test for excellence.

Execute the test suite via:
`ash
python -m kalshi_sim.university_runner --strategy dual_onnx --cycles 300
`

### Step 3: Seal Generation & Disk Verification
Upon passing all benchmarks, the system computes the SHA-256 hash of the strategy weights, parameters, and historical run log:
`ash
python -m kalshi_sim.university_runner --verify-seal
`
File location: data/seal_of_excellence.json

### Step 4: Promotion to Mother Dash Lane 1
Once verified on disk, Mother Dash (server.py) and the docked Baby Bot console automatically unlock the strategy for Live Trading (Lane 1), capped strictly at 1 micro-contract per asset.

---

## 4. Rollback & Decertification

If a live-sealed bot violates risk boundaries in production:
1. Revoke the disk seal:
   `ash
   python -m kalshi_sim.university_runner --revoke-seal dual_onnx
   `
2. The bot is immediately demoted back to Lane 2 Incubator mode.
