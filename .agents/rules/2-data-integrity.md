---
trigger: always_on
glob: "**/*"
description: Data integrity, Eastern Time exclusivity, countdown timer parity, and order book synchronization standards.
---

# 2. Data Integrity & Market Synchronization Standards

## 1. Eastern Time (`America/New_York`) Exclusivity
- All timestamps, contract expiry times (e.g. `5:30 PM ET`), and market duration headers must strictly reflect Eastern Time (ET).
- Never display raw UTC or unlocalized local machine time on trading headers or market banners.

## 2. 15-Minute Countdown Timer Parity
- The countdown timer represents exact time remaining to the active contract's expiration boundary (:00, :15, :30, :45 ET).
- The application timer must be **identical** to the official Kalshi web timer with sub-second synchronization ($T_{\text{rem}} \in [0, 900]$s).

## 3. Spot Price ($S_t$) & Target Strike ($K$) Parity
- **"TO BEAT" Target Strike ($K$)**: Must strictly reflect the active 15-minute event target strike.
- **"NOW" Bitcoin Spot Price ($S_t$)**: Must stream live from authenticated CME CF Bitcoin Real-Time Index (`cfbenchmarks_value_5hz`) with official 60s TWAP (`avg_60s_data`) for exact settlement parity.
- **Price Diff**: $\text{Diff} = S_t - K$ must be calculated with `Decimal` precision on every tick.

## 4. L2 CLOB Sequence Continuity & Uncrossed Books
- Local order books must continuously validate sequence (`seq`) numbers. If a sequence gap or out-of-order delta occurs, immediately invalidate the local book and trigger a full snapshot resync.
- **Uncrossed Book Invariant**: $\text{Best YES Bid} + \text{Best NO Bid} \le 1.00$ must hold at all times.
