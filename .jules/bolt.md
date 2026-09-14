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

## 2026-08-28 - Small Array NumPy Overhead vs Pure Python List Precomputation
**Learning:** Calling `np.median` or creating tiny 15-28 element NumPy arrays inside high-frequency per-tick loops adds C-API array construction and boxing overhead that is significantly slower than native Python list sorting and pre-computed tuple lookups.
**Action:** Pre-compute exponential decay tuples in `__init__`, use fast list sorting for small rolling deques (≤100 items), and use reciprocal multiplication (`1.0 / baseline_volume`) to reduce feature extraction latency from ~160μs to ~95μs per tick.

## 2026-08-29 - Pydantic Model Instantiation Bypass in High-Frequency ML Feature Extraction
**Learning:** Calling `book.get_depth(15)` inside the per-tick feature extraction loop instantiated ~30 Pydantic `OrderBookLevel` objects on every tick, triggering Pydantic model validation and object allocation overhead that consumed ~66% of tick processing time.
**Action:** Implemented `book.get_depth_tuples(n)` on `L2BookState` to return raw `(price, quantity)` tuple pairs directly and fast-path feature extraction, reducing ML feature extraction latency from ~95μs to ~32μs per tick (~3x throughput boost).

## 2026-08-30 - O(1) Version-Backed Depth Tuple Caching in L2BookState
**Learning:** Executing `sorted(self.yes_book.items(), key=_PRICE_GETTER, reverse=True)[:n]` on every feature extraction tick introduced redundant sorting overhead (~13.5 µs) even when order book states were unchanged between reads across ticks.
**Action:** Leveraged existing `_BookDict._version` mutation tracking in `L2BookState.get_depth_tuples(n)` to cache sorted depth tuples. Reduced `get_depth_tuples` cache hit time to ~0.3 µs (~40x faster) and overall feature extraction tick latency from ~38.6 µs to ~23.7 µs (~38% speedup).

## 2026-08-31 - O(1) Running CVD & Persistent ONNX Input Tensor Buffers
**Learning:** Computing `sum()` over 5-minute rolling trade deques on every tick and allocating NumPy arrays for small statistics (median, stddev on ≤100 items) or ONNX input dicts per tick incurred linear loop overhead and GC pauses.
**Action:** Maintain running CVD totals incrementally on trade push/pop, replace small-sample NumPy calls with pure Python arithmetic/sorting, and mutate pre-allocated ONNX input buffers in-place (`copy=False`).

## 2026-09-01 - Zero-Copy Ring Buffer C-Level Range Slicing
**Learning:** In `ZeroCopyRingBuffer`, computing `to_list()` and `get_tail(n)` using Python `for i in range(...)` loops with modulo arithmetic per item introduced significant interpreter loop and index computation overhead under high-frequency stream querying.
**Action:** Replace element-by-element range loops with C-level list range slicing (`self._buffer[head:] + self._buffer[:head]` and single/double range slices `self._buffer[start_idx:end_idx]`). Reduced `get_tail(100)` latency from ~23.8 µs down to ~1.16 µs per call (~20.6x speedup) and `to_list()` latency from ~50.6 µs down to ~5.78 µs per call (~8.75x speedup).

## 2026-09-02 - Decimal Constant Pre-Allocation & Int Fast-Path in Kalshi Taker Fee Calculation
**Learning:** Re-instantiating `Decimal("0.01")`, `Decimal("0.99")`, `Decimal("7.0")`, `Decimal("1.00")`, `Decimal("100")`, `Decimal("0.02")` from strings and calling `Decimal(str(contracts))` for integer contract counts inside `calculate_kalshi_taker_fee()` created string parsing and allocation overhead on every trade/order fill simulation (~5.80 µs per call).
**Action:** Pre-allocate static Decimal constants at module level (`_DEC_0_01`, `_DEC_0_99`, `_DEC_7_0`, `_DEC_1_00`, `_DEC_100`, `_DEC_0_02`, `_DEC_0_00`) and fast-path integer contract parsing (`Decimal(contracts)` if `isinstance(contracts, int)` else `Decimal(str(contracts))`), reducing taker fee calculation latency from 5.80 µs to 3.10 µs per call (~1.87x speedup).

## 2026-09-03 - O(1) Version-Backed Float Depth Tuple Caching in L2BookState
**Learning:** Re-converting `Decimal` prices and quantities to `float` across 30 depth levels in per-tick feature extraction (`[float(qty) for _, qty in top_yes]`) consumed >50% of feature extraction execution time (~10.3 µs out of ~20.5 µs per tick) due to CPython `Decimal.__float__` conversion overhead.
**Action:** Added `get_depth_float_tuples(n)` to `L2BookState` leveraging existing `_BookDict._version` mutation tracking to memoize float-converted depth tuples in O(1) time (~0.4 µs on cache hit). Updated `KalshiOrderflowFeatureExtractor` and `GoldOrderflowFeatureExtractor` to fast-path float tuple consumption, reducing tick feature extraction latency from ~20.5 µs to ~11.9 µs (~1.72x speedup).
