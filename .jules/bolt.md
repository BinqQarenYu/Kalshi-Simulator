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

## 2026-08-27 - Deferred Pydantic Model Instantiation in L2 Order Book Depth Slicing
**Learning:** Instantiating Pydantic `OrderBookLevel` objects for all price levels in an order book dictionary before sorting and slicing `[:n]` generated severe Pydantic validation overhead (~2.4ms per 10k calls).
**Action:** Sort raw price-quantity dictionary items `(price, qty)` first, slice top `n` levels, and instantiate Pydantic `OrderBookLevel` objects only for the sliced slice. Reduced `get_depth` latency by 64% (~2.8x speedup).

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

## 2026-09-02 - Property Getter Bypass & Module-Level Decimal Zero Constant in L2 Delta Ingestion
**Learning:** Accessing `book.yes_book` / `book.no_book` Python property getters and calling `Decimal("0")` dynamically on every delta update in high-frequency WebSocket order book processing adds property lookup and object instantiation overhead.
**Action:** Access internal `book._yes_book` and `book._no_book` attributes directly in internal `OrderBookManager.apply_delta` loops and reuse a pre-computed module-level `_ZERO = Decimal("0")` constant. Reduced `apply_delta` latency from ~2.27 µs to ~1.54 µs per delta (~32% latency reduction / ~47% throughput boost).

## 2026-09-17 - O(1) Pre-Sorted Rolling Median Lookup for Dynamic Whale Detection
**Learning:** Calling `statistics.median` on list comprehensions constructed from deque dict items in `process_trade` caused $O(N \log N)$ sorting and list allocation overhead on every trade arrival.
**Action:** Utilize synchronized pre-sorted list (`bisect.insort`) alongside deque to compute median trade quantities in $O(1)$ time, reducing trade dynamic whale calculation latency from ~14.92 µs to ~0.67 µs per trade (~22x speedup).

## 2026-09-18 - Subclass `FastBook.copy()` In-Place C-Level Dict Cloning
**Learning:** Constructing a new `FastBook` subclass instance via `FastBook(dict(fb))` in `get_btc_l2_state()` snapshot creation forced full `__init__` recalculations (`max(self.keys())`) and item insertion overhead.
**Action:** Implemented custom `FastBook.copy()` using `FastBook.__new__(FastBook)` and C-level `dict.update(res, self)`, directly inheriting `_best` top-of-book indexing and `_version` tracking. Reduced order book snapshot copy latency from ~10.3 µs to ~5.0 µs per call (~2x speedup / 51% latency reduction).

## 2026-09-19 - O(1) Version-Backed Depth Tuple Caching in L2BookState.get_depth_raw
**Learning:** Re-executing `sorted(self.yes_book.items(), key=_PRICE_GETTER, reverse=True)[:n]` inside `get_depth_raw` on every feature extraction tick introduced redundant $O(N \log N)$ sorting overhead (~12.8 µs) even when order book states were unchanged between reads.
**Action:** Utilized version-backed `FastBook._version` mutation tracking in `L2BookState.get_depth_raw(n)` to cache sorted depth tuples. Reduced `get_depth_raw` read latency from ~12.8 µs to ~0.32 µs per call (~40x speedup / 97.5% latency reduction).

## 2026-09-20 - Binary Option Expected Value Payoff Identity Simplification
**Learning:** Calculating gross binary option expected value using full 5-operation Decimal arithmetic `p * (1 - K) - (1 - p) * K` adds unnecessary Decimal allocation and operator dispatch overhead per calculation.
**Action:** Simplify binary option expected value formula to mathematically equivalent single-subtraction `p - K` and use fast string formatting `f"{prob:.4f}"`. Reduced `StatisticalEVEngine.calculate_ev` latency from ~12.32 µs to ~9.14 µs per call (~25.8% latency reduction / 1.35x speedup).

## 2026-09-20 - Direct `__dict__` Mutation for High-Frequency Pydantic Candlestick Updates
**Learning:** Setting attributes on active Pydantic v2 `OHLCVCandle` model instances inside high-frequency tick loops triggers Pydantic `__setattr__` validator and field validation overhead on every tick update (~2.34 µs per tick).
**Action:** Access `candle.__dict__` directly when mutating active and backfilled candlestick fields (`high`, `low`, `close`, `volume`, `trades_count`) in `OHLCVAggregator.add_tick`. Reduced `add_tick` latency from ~10.06 µs down to ~6.44 µs per tick (~36% latency reduction / ~1.56x throughput boost).

## 2026-09-20 - Pure Python Scalar Math for 3-Class Softmax Temperature Scaling
**Learning:** Calling NumPy operations (`/`, `np.max`, `np.exp`, `.sum()`) on tiny 3-element output probability vectors inside high-frequency per-tick inference loops introduced C-API array construction, indexing, and boxing overhead (~17.2 µs).
**Action:** Use pure Python scalar arithmetic (`math.exp` and float operations) for small fixed-dimensional softmax vectors, reducing probability calibration latency to ~2.7 µs (~6.3x speedup / ~14.5 µs saved per ONNX inference tick).

## 2026-09-20 - $O(\log N)$ Binary Search Eviction in Pre-Sorted Feature Extractor Rolling Windows
**Learning:** Calling `list.remove(old_val)` when evicting elements from 100-element pre-sorted rolling trade and volume lists in `KalshiOrderflowFeatureExtractor` and `GoldOrderflowFeatureExtractor` performed an $O(N)$ linear equality scan across Python float objects.
**Action:** Replaced `list.remove(old_val)` with C-level binary search lookup `idx = bisect.bisect_left(sorted_list, old_val)` followed by `del sorted_list[idx]`. Reduced rolling window eviction loop execution time by ~1.7x (~41% speedup).

## 2026-09-20 - Pure Python Sample Standard Deviation vs statistics.stdev Overhead
**Learning:** Calling `statistics.stdev` on a small collection converts elements into Python `Fraction` objects for exact rational arithmetic, adding ~50 µs of fraction construction and conversion overhead per call in trade ingestion loops.
**Action:** Replaced `statistics.stdev` in VPIN price change processing with pure Python arithmetic standard deviation (`sum` and `sum((x - mean)**2)`). Reduced `process_trade` average latency from ~72.3 µs to ~22.9 µs per trade call (~3.15x speedup / 68% latency reduction).

## 2026-09-21 - Single-Pass Algebraic Trade Entropy Calculation
**Learning:** Computing Shannon trade size entropy over rolling trade history deques by allocating intermediate Python lists (`recent_sizes`, `probs`) via `itertools.islice` and list comprehensions introduced ~2.4 µs of Python list allocation and multi-pass loop overhead per trade update.
**Action:** Refactored `_update_cached_entropy` in `KalshiOrderflowFeatureExtractor` and `GoldOrderflowFeatureExtractor` to use the algebraic entropy expansion $H(P) = \log_2(S) - \frac{\sum s_i \log_2(s_i)}{S}$ in a single loop pass without list allocations. Reduced `_update_cached_entropy` latency from ~7.3 µs to ~4.9 µs per call (~33% latency reduction / ~1.47x speedup).
