# Data Integrity & Truth Enforcement Rules

To ensure reliable quantitative backtesting, paper forward validation, and live trading, the platform enforces strict data integrity rules.

---

## 🔒 1. Single Source of Truth & Zero-Mock Guarantee

- **Strict Live Ground Truth**: When running paper simulation or live demo trading, all order books, strike prices, trade executions, and timestamps originate exclusively from live Kalshi exchange WebSocket streams and institutional Bitcoin Spot feeds (Coinbase/Binance).
- **No Synthetic Fallback**: If an exchange feed disconnects, the system pauses execution with explicit warnings and triggers exponential backoff reconnection rather than generating fake or synthetic ticks.

---

## 🕒 2. Eastern Time (`America/New_York`) Exclusivity

All market operations strictly adhere to Eastern Time:
1. **Target Strike Expiry Time**: Displays in Eastern Time (e.g. `1:30 PM ET`).
2. **Cycle Time Windows**: Displays full Eastern Time ranges (e.g. `August 30, 1:15 – 1:30 PM ET`).
3. **15-Minute Countdown Timer**: Synchronized with sub-second accuracy to official Kalshi cycle close boundaries (`:00`, `:15`, `:30`, `:45`).

---

## 🔢 3. Zero Floating-Point Tolerance (`Decimal` Precision)

- Native IEEE-754 floating-point arithmetic (`float` in Python / native `number` in JS) is strictly forbidden for all financial calculations.
- Python uses `decimal.Decimal` and TypeScript uses string-wrapped / fixed precision representations for:
  - Account balances & equity
  - Contract entry & settlement prices
  - Strike price diffs ($S_t - K$) and percentage diffs
  - Profit and Loss ($\text{PnL}$) and fee calculations

---

## 🛡️ 4. Invariant Guarantees Enforced by `AgentIntegrityCheck`

The background guardian daemon (`AgentIntegrityCheck`) runs continuously in the background (every 2.0s), auditing and enforcing the following 10 core mathematical, microstructure, latency, and truth invariants:

---

### 🧮 A. Mathematical & Financial Invariants

| Invariant Name | Mathematical Formulation | Enforced Bound / Condition | Automated Action on Violation |
| :--- | :--- | :--- | :--- |
| **Decimal Strictness** | $\text{Type}(\text{Balance}, \text{Equity}, \text{PnL}) \equiv \text{Decimal}$ | Zero IEEE-754 binary floating-point drift | Immediate type rejection |
| **Equity Reconciliation** | $\text{Equity} = \text{Balance} + \sum \text{Unrealized P&L}$ | $|\text{Equity} - (\text{Cash} + \text{Unrealized})| < \$0.0001$ | Critical trading halt & alert |
| **Binary Payoff Mechanics** | $\text{Payout per Contract} \in \{\$1.00, \$0.00\}$ | $\text{Cost} + \text{PnL} \equiv \text{Size} \times \$1.00 \text{ or } \$0.00$ | Critical audit flag & log |
| **Collateral Solvency** | $\text{Cash Balance} \ge \$0.00$ | Zero uncollateralized deficit margin | Order rejection |
| **Unrealized Mark Invariant** | $\text{Unrealized P&L} = (\text{MarkPrice} - \text{EntryPrice}) \times \text{Size}$ | Computed on live inside-touch bids | Real-time ledger sync |

---

### ⚡ B. Microstructure & Order Book Invariants

| Invariant Name | Rule / Condition | Threshold | Automated Action on Violation |
| :--- | :--- | :--- | :--- |
| **CLOB Sequence Continuity** | Delta sequence continuity: $\text{seq}_{t} = \text{seq}_{t-1} + 1$ | 0 missed packets allowed | Invalidate book $\rightarrow$ Full REST snapshot resync |
| **Uncrossed Order Book** | $\text{Best YES Bid} + \text{Best NO Bid} \le 1.00$ | Spread $\ge \$0.00$ | Re-align inside touch ladder |
| **Order Book Depth Liveness** | Order book must contain active bids and asks | Updated within last 5 seconds | Stale book warning & discovery refresh |

---

### ⏱️ C. Clock, Timer & Settlement Invariants

| Invariant Name | Rule / Condition | Threshold | Automated Action on Violation |
| :--- | :--- | :--- | :--- |
| **15M Cycle Monotonicity** | Expiry countdown $T_{\text{rem}}$ decrements continuously | $T_{\text{rem}} \in [0, 900]$ seconds | Sub-second timer resync |
| **Eastern Time Format** | All timestamps terminate in `ET` with New York offset | `America/New_York` strict | Timezone re-formatting |
| **Price Diff Parity** | $\text{Diff} = S_t - K$ and $\text{Diff \%} = \frac{S_t - K}{K} \times 100\%$ | Synchronous across hero, chart, EV & logs | Real-time tick broadcast |

---

### 🚀 D. Latency & Truth Guarantees

| Invariant Name | Rule / Condition | Enforced Bound | Automated Action on Violation |
| :--- | :--- | :--- | :--- |
| **Sub-250ms Latency Guard** | Tick processing and ONNX tensor evaluation time | Latency $< 250\text{ms}$ | GC throttle & thread pool offload |
| **Live Truth Invariant** | Zero synthetic or randomized data permitted in live mode | $\text{Data Source} \equiv \text{Kalshi Exchange}$ | Graceful pause / reconnection |

