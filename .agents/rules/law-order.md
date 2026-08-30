# CFTC & Kalshi Legal, Regulatory & API Compliance Rules

## 1. Statutory & Regulatory Invariants (CFTC / CEA)
- **Zero Tolerance for Wash Trading**:
  - Never allow an order to be submitted that matches or crosses with an existing open/resting order from the same account.
  - Immediate pre-trade check: $\text{Opposing Resting Order at same/crossing price} \implies \text{REJECT & LOG VIOLATION}$.
- **Zero Tolerance for Spoofing & Layering**:
  - Never submit phantom orders or rapid cancellation floods intended to manipulate the orderbook depth.
  - Maintain Order-to-Trade Ratio (OTR) under strict regulatory safety thresholds.
- **CFTC Recordkeeping (Rule 1.31)**:
  - All order lifecycle events (submissions, cancels, fills, rejects) must be recorded in durable append-only storage with millisecond timestamps.

## 2. Kalshi Terms of Service & API Constraints
- **Cryptographic Security & Secret Isolation**:
  - Never log, stream, or bundle private RSA keys (`.pem`), API secrets, or unredacted signatures.
- **Environment Isolation**:
  - Mock, backtest, and algorithmic development must strictly hit `demo` endpoints (`demo-api.kalshi.co`).
  - Production endpoints (`api.kalshi.com`) are reserved strictly for explicit `mode === 'live'` execution with verified credentials.
- **Rate Limit Quotas**:
  - Adhere to token-bucket rate limits ($20\text{ req/s}$ public, $30\text{ req/s}$ authenticated).
  - Exponential backoff must be used upon encountering HTTP 429.
- **Position Limits**:
  - Enforce per-market contract maximums (default: 250 contracts per market, max $25,000 retail exposure cap).

## 3. Autonomous Compliance Gatekeeper (`AgentLawOrder`)
- The backend `AgentLawOrder` evaluates all pre-trade requests and exposes real-time compliance telemetry at `GET /api/compliance/status` and `GET /api/compliance/dos-and-donts`.
- If any critical regulatory violation is detected, `AgentLawOrder` immediately halts trading and alerts the operator.
