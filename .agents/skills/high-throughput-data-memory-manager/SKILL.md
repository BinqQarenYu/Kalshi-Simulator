---
name: high-throughput-data-memory-manager
description: Expert AI quantitative data architect specializing in ultra-large financial dataset ingestion, zero-copy memory ring buffers, LRU cache eviction, asynchronous disk offloading, and instantaneous human-machine UI/UX synchronization.
---

# High-Throughput Quantitative Data & Memory Architecture Skill

## 1. Core Mission & Philosophy
The **High-Throughput Data & Memory Architect** is designed to handle gigabyte-scale and terabyte-scale financial market data streams (Level-2 order book deltas, tick prints, OHLCV aggregates, 28-dimensional microstructure feature tensors) with deterministic microsecond latency, strictly bounded memory footprints, and instant human-machine UI/UX responsiveness.

---

## 2. Quantitative Memory Management Standards

### A. Zero-Copy Circular Ring Buffers
- Never dynamically allocate unbounded Python lists or JavaScript arrays during real-time tick streaming.
- Utilize fixed-capacity circular ring buffers (`RingBuffer` / `collections.deque(maxlen=N)` / typed `Float64Array` buffers) with $O(1)$ push, pop, and contiguous slice access.
- When new ticks arrive, overwrite the oldest elements in place without triggering runtime Garbage Collection (GC) pauses.

### B. High-Speed Asynchronous Disk Offloading
- Offload market microstructure data to disk in background asynchronous worker tasks (`TickWriter` / DuckDB / Parquet / compressed JSONL).
- Ensure file I/O operations never block the event loop or introduce jitter into order matching or WebSocket broadcasting.

### C. Active Memory Eviction & Dynamic Working Sets
- Enforce LRU (Least Recently Used) and TTL (Time-To-Live) cache eviction policies on inactive market tickers and closed expiry contracts.
- Isolate the **Active Working Set** (hot RAM) for the active trading market and lazily page historical data from disk only when requested by analytics.

---

## 3. Instantaneous UI/UX Synchronization Principles

### A. Sub-Millisecond Frontend State Dispatch
- Minimize React virtual DOM reconciliation overhead by separating hot data streams (price tickers, depth ladders, chart canvas) from static control UI.
- Use `useLayoutEffect` and direct GPU canvas context painting (`setTransform`) combined with `ResizeObserver` caching to achieve 60–120 FPS fluid rendering.

### B. Zero-Delay Hardware Acceleration
- Eliminate CSS animation transitions on high-frequency components (order book depth bars, ticker changes) that fight sub-50ms data updates.
- Use `will-change: transform, width` and CSS hardware acceleration to offload depth bar and trajectory rendering to the GPU.

---

## 4. Operational Execution Runbook
When designing or optimizing data systems:
1. **Profile Memory Allocation**: Inspect object counts, buffer sizes, and memory usage per active symbol.
2. **Implement Ring Buffers**: Cap in-memory history to the required visual/analytical horizon (e.g. 500 ticks hot).
3. **Flush to Persistent Storage**: Write completed time frames and settled contract ticks to append-only disk files.
4. **Verify Zero Regressions**: Run test suites (`pytest tests/`) and bundle builds (`npm run build`) via the ASVL loop.
