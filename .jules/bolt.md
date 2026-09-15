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

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
## 2026-09-03 - O(1) Version-Backed Float Depth Tuple Caching in L2BookState
**Learning:** Re-converting `Decimal` prices and quantities to `float` across 30 depth levels in per-tick feature extraction (`[float(qty) for _, qty in top_yes]`) consumed >50% of feature extraction execution time (~10.3 µs out of ~20.5 µs per tick) due to CPython `Decimal.__float__` conversion overhead.
**Action:** Added `get_depth_float_tuples(n)` to `L2BookState` leveraging existing `_BookDict._version` mutation tracking to memoize float-converted depth tuples in O(1) time (~0.4 µs on cache hit). Updated `KalshiOrderflowFeatureExtractor` and `GoldOrderflowFeatureExtractor` to fast-path float tuple consumption, reducing tick feature extraction latency from ~20.5 µs to ~11.9 µs (~1.72x speedup).

## 2026-09-03 - Unrolled Fixed-Depth Top-5 Level Volume Summation in Gold Feature Extractor
**Learning:** Calling `sum(bid_sizes[:5])` and `sum(ask_sizes[:5])` inside per-tick feature extraction created list slicing (`[:5]`) allocations and generic iterator/function call overhead on every tick.
**Action:** Unroll top-5 volume summation using direct index addition (`bid_sizes[0] + bid_sizes[1] + bid_sizes[2] + bid_sizes[3] + bid_sizes[4]`), safely guarded by prior depth list padding (to `target_depth` = 15). Reduced feature extraction volume sum latency by ~13%.

## 2026-09-14 - Decimal Constant Pre-Allocation & Float Fast-Pathing in Stage 2 EV Engine
**Learning:** In `StatisticalEVEngine.compute_optimal_execution()`, instantiating temporary `Decimal` objects from string literals (`Decimal("0.50")`, `Decimal("0.00")`, `Decimal("1.00")`, etc.), evaluating gross EV for both YES and NO sides even when one side had negative edge, and performing redundant float-to-Decimal conversions added ~12.1 µs overhead per execution calculation tick.
**Action:** Pre-allocated static `Decimal` constants at module level (`_DEC_0_00`, `_DEC_0_01`, `_DEC_0_06`, `_DEC_0_50`, `_DEC_0_90`, `_DEC_0_99`, `_DEC_1_00`), fast-pathed market ask `Decimal`/`float` handling, and evaluated directional edge in fast float space prior to Decimal payoff computation. Reduced `compute_optimal_execution` latency from ~30.2 µs to ~18.1 µs per call (~40% speedup).

## 2026-09-03 - C-Level `itemgetter` Keying & Decimal Constant Pre-Allocation in L2 Orderbook Walking
**Learning:** Using `lambda x: x[0]` as the sorting key in `sorted(book_side.items(), key=lambda x: x[0], reverse=True)` inside `OrderSimulator._walk_book` invoked Python function call overhead for every level in the L2 book during VWAP fill simulation. Additionally, re-instantiating `Decimal("0.0001")`, `Decimal("0.0")`, and `Decimal("1.0")` inside the loop added repeated object allocation cost (~35.1 µs per call).
**Action:** Use pre-allocated C-level `_PRICE_GETTER = operator.itemgetter(0)` and module-level static Decimal constants (`_DEC_0_0001`, `_DEC_0_00`, `_DEC_1_00`), reducing `_walk_book` latency from ~35.1 µs to ~21.5 µs per call (~1.63x speedup).

## 2026-09-03 - C-Level operator.itemgetter Key Lookup in Order Book Level Walking
**Learning:** Using `key=lambda x: x[0]` inside `sorted(book_side.items(), ...)` in high-frequency order walking loop creates Python function frame creation and invocation overhead on every level sort call (~4.53 µs per call).
**Action:** Replace `lambda x: x[0]` with pre-allocated module-level `_PRICE_GETTER = operator.itemgetter(0)` and eliminate redundant `if/else` branching. Reduced sorting latency from 4.53 µs to 2.87 µs per call (~36.5% speedup / ~1.66 µs saved per order walk).

## 2026-09-03 - Itemgetter Price Sorting, Pre-Tuple Thresholds & Hex UUIDs in Order Book Simulation
**Learning:** Sorting L2 book price levels using Python `key=lambda x: x[0]` functions inside `_walk_book()`, creating `str(uuid.uuid4())[:8]` string formats, re-instantiating `Decimal("1")` objects, and iterating over `.items()` dicts in velocity checks added ~30 µs latency per order simulation.
**Action:** Use `_PRICE_GETTER = operator.itemgetter(0)` for C-level sorting, deduplicate YES/NO walk conversion, pre-allocate Decimal constants (`_DEC_1`, `_DEC_0_0001`, `_DEC_1_0`, `_DEC_0_0`), pre-compute `_SPOT_VELOCITY_ITEMS` tuple, and use `uuid.uuid4().hex[:8]`. Reduced `_walk_book` latency from 28.59 µs to 17.56 µs (~1.63x speedup) and market order simulation latency by ~19.2%.

## 2026-09-03 - C-Level Itemgetter Sorting & Branch Deduplication in Order Book Walking
**Learning:** Sorting price levels with Python `key=lambda x: x[0]` inside `OrderSimulator._walk_book` invoked Python function calls per level. In addition, identical sorting and price conversion operations were redundantly duplicated across `OrderSide.YES` / `OrderSide.NO` `if/else` branches.
**Action:** Replace `lambda x: x[0]` sorting key with module-level C-extension `_PRICE_GETTER = operator.itemgetter(0)` and remove redundant branch duplication and unused lambda instantiations, reducing level sorting latency in order book walking from 17.46 µs down to 11.38 µs (~1.53x speedup).

## 2026-09-03 - Tuple Direct Sorting & Decimal Quantize Constant Pre-Allocation in L2 Order Book Walking
**Learning:** In order book depth walking routines (`_walk_book`), passing `key=lambda x: x[0]` to `sorted(book_side.items(), reverse=True)` incurred CPython function call overhead (~0.85 µs per call) even though price keys are strictly unique `Decimal` objects where native tuple comparison compares price elements directly. Additionally, re-parsing `Decimal("0.0001")` strings inside `quantize()` calls on every order fill added object allocation overhead.
**Action:** Remove `key=lambda` on dictionary item sorts, eliminate redundant branch logic in book walking, and pre-allocate `_DEC_0_0001` at module level, reducing `_walk_book` latency from 14.49 µs to 12.47 µs per call (~1.16x speedup).

## 2026-09-03 - Unrolled Fixed-Depth Top-5 Level Volume Summation in Gold Feature Extractor
**Learning:** Calling `sum(bid_sizes[:5])` and `sum(ask_sizes[:5])` inside per-tick feature extraction created list slicing (`[:5]`) allocations and generic iterator/function call overhead on every tick.
**Action:** Unroll top-5 volume summation using direct index addition (`bid_sizes[0] + bid_sizes[1] + bid_sizes[2] + bid_sizes[3] + bid_sizes[4]`), safely guarded by prior depth list padding (to `target_depth` = 15). Reduced feature extraction volume sum latency by ~13%.
