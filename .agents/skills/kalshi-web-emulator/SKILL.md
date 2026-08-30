---
name: kalshi-web-emulator
description: Expert AI trading terminal emulator replicating the complete Kalshi Web trading platform capabilities, WebCLOB order book depth ladder, live price trajectories, 1-click execution slips, automated contract settlement, and AI microstructure copilot in a unified single-module engine.
---

# Kalshi Web Trading Platform Emulator Skill

## 1. Overview & Capabilities Matrix
The **Kalshi Web Emulator** unifies all discrete quantitative trading sub-systems into a single coherent engine that faithfully replicates the official Kalshi web application experience:

| Web Interface Feature | Emulation Engine Component | Alignment Standard |
| :--- | :--- | :--- |
| **Market Strike Discovery** | `MarketDiscoveryService` | Filters active 5m, 15m, 1h binary series (e.g. `KXBTC15M`, `KXBTC5M`) |
| **CLOB Depth Ladder** | `OrderBookManager` (L2 CLOB) | Aggregates price levels from 1¢ to 99¢ with cumulative depth percentages |
| **Live Price Trajectory** | `TargetChart` / Zero-Copy RingBuffer | Real-time "TO BEAT" target strike vs "NOW" BTC spot tracking |
| **1-Click Quick Trade Slip** | `KalshiLiveOrderClient` / `OrderSimulator` | Instant Up/Down (Yes/No) execution with limit/market routing and resting caps |
| **Portfolio & PnL Tracking** | `PortfolioManager` | Decimal precision cash balance, unrealized PnL, win-rate, and position ladder |
| **Automated Contract Settlement** | `SettlementService` | Evaluates spot vs strike at binary expiration with $1.00 or $0.00 cash settlement |
| **AI Microstructure Copilot** | `StatisticalEVEngine` & ONNX Model | 28-D tensor inference, directional probabilities, Kelly fraction, and VPIN toxicity veto |
| **High-Throughput RAM Telemetry** | `MarketDataMemoryManager` | 1,000-tick hot ring buffer with asynchronous non-blocking disk offloading |

---

## 2. Single-Module Architecture Pattern (`web_emulator.py`)
Rather than loosely coupling multiple disconnected background workers, the entire web platform state is orchestrated via `KalshiWebEmulator`:

```python
class KalshiWebEmulator:
    """Unified single-entrypoint emulator for the complete Kalshi Web platform."""
    
    def __init__(self, starting_capital: Decimal = Decimal("100.00"), mode: str = "live") -> None:
        ...

    def step(self, spot_price: Decimal, delta: Optional[dict] = None) -> dict:
        """Advance emulation step, update orderbook, run ONNX AI inference, and settle expired contracts."""
        ...

    def execute_order(self, request: LiveOrderRequest) -> LiveOrderResponse:
        """Process 1-click or custom limit order with pre-trade risk checks."""
        ...

    def get_web_state_payload(self) -> dict:
        """Produce full JSON state payload strictly matching frontend WebCLOB expectations."""
        ...
```

---

## 3. Web UI/UX & Architecture Alignment Guidelines
1. **Eastern Time (`America/New_York`) Exclusivity**: Always format event headers and countdown expirations in Eastern Time (e.g. `August 29, 05:30 - 05:45 AM ET`), never raw UTC or unlocalized local machine time.
2. **Identical 15-Minute Countdown Timer**: Sub-second synchronization against the active contract cycle boundary (:00, :15, :30, :45 ET).
3. **Decoupled Hot/Warm Path Architecture**:
   - **Hot Path (<1ms)**: L2 Orderbook delta processing, inside touch pricing, and immediate state updates.
   - **Warm Path (250ms)**: Isolated `AIWorker` executing 28-D tensor extraction, ONNX runtime inference, and EV/Kelly sizing to a thread-safe cache.
   - **Stream Gateway (15Hz–20Hz)**: Non-blocking in-memory reads (<0.001ms) with state-change coalescing.
4. **Strict Precision**: All monetary values, fees, slippage, and strike differences must maintain `Decimal` precision without IEEE 754 float drift.
5. **Zero-Mock Invariant**: In live/paper mode, all market feeds must originate from live exchange connections without synthetic fallbacks.
