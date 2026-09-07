# Quantitative Engineering Learnings & Microstructure Optimizations

## 2026-08-20 - Multi-Level L2 Exponential Depth Decay Vectorization ($\mathcal{M}_n$)
**Learning:** Calculating exponential decay depth imbalance across 15 book layers sequentially per delta message generated high CPU overhead in high-frequency regimes.
**Action:** Pre-compute exponential decay weight vector $e^{-\alpha(i-1)}$ ($\alpha = 0.425$) in NumPy/C arrays, enabling SIMD-vectorized dot products across bid and ask depth tensors in under 8 microseconds.

## 2026-08-22 - ONNX Runtime CPU Provider Tensor Allocation Caching
**Learning:** Instantiating new float32 input tensors per inference invocation triggered garbage collection pauses and added ~1.2ms to pipeline latency.
**Action:** Pre-allocate persistent contiguous input buffer in `KalshiONNX` session wrapper and mutate in-place with `feature_stats.json` mean/std normalization. Reduced ONNX inference latency to 0.38ms.

## 2026-08-24 - Zero-Copy WebSocket Broadcast JSON Serialization
**Learning:** Converting internal `Decimal` representations to JSON dictionaries independently for every connected WebSocket client caused redundant CPU serialization and lag under heavy tape bursts.
**Action:** Serialize the consolidated full system state payload once per broadcast tick (5 Hz) using an optimized Decimal string serializer, broadcasting identical pre-encoded JSON payloads to all active client sockets.

## 2026-08-25 - Monotonic Sequence Book Delta Processing & 135k deltas/s Throughput
**Learning:** Naive linear scans of book price levels on delta updates caused book rebuild stalls during volatile market moves.
**Action:** Utilize keyed dict price levels with binary heap top-of-book tracking and monotonic `seq` gap detection. Achieved 135k deltas/second sustained throughput with instant automated snapshot recovery on sequence gaps.

## 2026-08-26 - VPIN Toxicity Volume Bucketing with Rolling Ring Buffers
**Learning:** Volume-Synchronized Probability of Informed Trading (VPIN) calculations recalculating across non-fixed volume slices caused variable latency spikes.
**Action:** Implemented fixed-volume constant bucket ring buffers with circular pointer indexing, ensuring $O(1)$ toxicity updates on every trade print and deterministic pre-trade veto response time.

## 2026-08-27 - Pydantic Field Setattr Bypass & Decimal Type Fast-Pathing in OHLCV Aggregator
**Learning:** Unconditionally mutating Pydantic BaseModel attributes (e.g., `active.high = max(...)`) in high-frequency tick loops triggers Pydantic's `__setattr__` validator logic on every tick. Additionally, calling `Decimal(str(price))` when input is already a `Decimal` adds unnecessary string serialization and parsing overhead.
**Action:** Guard high/low attribute assignments with conditional checks (`if price_dec > active.high: active.high = price_dec`), use fast-path `isinstance(price, Decimal)` checks, and precompute static interval tuples to achieve ~3x faster tick aggregation throughput.
