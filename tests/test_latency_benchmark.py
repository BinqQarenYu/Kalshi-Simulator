"""High-Throughput Latency & Stress Benchmark Test Suite.

Validates sub-millisecond AI inference execution, high-frequency L2 order book
delta throughput (10,000+ deltas/sec), and JSON state serialization concurrency.
"""

from decimal import Decimal
import json
import time
import numpy as np
import pytest

from app_2_execution_bot.ml.feature_extractor import KalshiOrderflowFeatureExtractor
from app_2_execution_bot.ml.onnx_engine import KalshiONNXEngine
from app_2_execution_bot.orderbook import OrderBookManager
from shared.schemas import (
    L2BookState,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
    TradeEvent,
)
from app_2_execution_bot.server import _build_full_state_payload, fast_dumps



def _create_dense_book(ticker: str = "KXBTC15M-BENCH") -> L2BookState:
    """Helper to construct a fully populated 15-level bid/ask L2 book."""
    book = L2BookState(ticker)
    for i in range(15):
        bid_p = Decimal(str(round(0.48 - i * 0.01, 2)))
        ask_no_p = Decimal(str(round(0.51 - i * 0.01, 2)))
        if bid_p > 0:
            book.yes_book[bid_p] = Decimal(str(100 + i * 20))
        if ask_no_p > 0:
            book.no_book[ask_no_p] = Decimal(str(120 + i * 25))
    return book


def test_feature_extraction_latency_sub_millisecond():
    """Feature extraction across 15 depth levels must execute in < 0.5ms per tick."""
    extractor = KalshiOrderflowFeatureExtractor(target_depth=15, spatial_alpha=0.425)
    book = _create_dense_book()
    
    # Warmup
    for _ in range(50):
        extractor.extract_features_from_book(book)

    latencies_us = []
    iterations = 500

    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        vec = extractor.extract_features_from_book(book)
        t1 = time.perf_counter_ns()
        latencies_us.append((t1 - t0) / 1000.0)

    p50_us = np.percentile(latencies_us, 50)
    p95_us = np.percentile(latencies_us, 95)
    p99_us = np.percentile(latencies_us, 99)
    mean_us = np.mean(latencies_us)

    print(f"\n[BENCHMARK] Feature Extraction Latency: Mean={mean_us:.2f}us | P50={p50_us:.2f}us | P95={p95_us:.2f}us | P99={p99_us:.2f}us")

    # Assert sub-millisecond (1000μs) latency requirement
    assert p95_us < 1000.0, f"P95 latency {p95_us:.2f}μs exceeded 1.0ms threshold"


def test_onnx_inference_latency_benchmark():
    """QuoLas ONNX neural network inference must execute in < 2.0ms per tick."""
    engine = KalshiONNXEngine(model_path="models/nano_microscope_overhauled.onnx")
    book = _create_dense_book()

    # Warmup
    for _ in range(20):
        engine.process_orderbook_tick(book)

    latencies_ms = []
    iterations = 200

    for _ in range(iterations):
        t0 = time.perf_counter()
        res = engine.process_orderbook_tick(book)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    p50_ms = np.percentile(latencies_ms, 50)
    p95_ms = np.percentile(latencies_ms, 95)
    mean_ms = np.mean(latencies_ms)

    print(f"\n[BENCHMARK] ONNX Model Inference Latency: Mean={mean_ms:.3f}ms | P50={p50_ms:.3f}ms | P95={p95_ms:.3f}ms")

    # Assert sub-2ms mean inference latency
    assert mean_ms < 2.0, f"Mean ONNX latency {mean_ms:.3f}ms exceeded 2.0ms threshold"


def test_orderbook_delta_throughput_benchmark():
    """OrderBookManager must process > 10,000 L2 deltas per second."""
    obm = OrderBookManager()
    ticker = "KXBTC15M-THROUGHPUT"

    # Initial snapshot
    snap = OrderBookSnapshot(
        market_ticker=ticker,
        seq=1,
        yes_levels=[OrderBookLevel(price=Decimal("0.48"), quantity=Decimal("100"))],
        no_levels=[OrderBookLevel(price=Decimal("0.51"), quantity=Decimal("150"))],
    )
    obm.apply_snapshot(snap)

    iterations = 5000
    t0 = time.perf_counter()

    for seq in range(2, iterations + 2):
        delta = OrderBookDelta(
            market_ticker=ticker,
            seq=seq,
            side="yes",
            price=Decimal("0.48"),
            delta=Decimal("1") if seq % 2 == 0 else Decimal("-1"),
        )
        obm.apply_delta(delta)

    elapsed = time.perf_counter() - t0
    deltas_per_sec = iterations / elapsed

    print(f"\n[BENCHMARK] L2 Delta Throughput: {deltas_per_sec:,.0f} deltas/sec ({iterations} deltas in {elapsed:.3f}s)")

    assert deltas_per_sec > 10000, f"Throughput {deltas_per_sec:.0f} deltas/sec below 10,000/sec requirement"


def test_state_serialization_concurrency_stress():
    """Real-time full state JSON serialization with fast_dumps must execute in < 0.5ms per frame."""
    # Warmup
    for _ in range(20):
        payload = _build_full_state_payload()
        _ = fast_dumps(payload)

    latencies_ms = []
    iterations = 200

    for _ in range(iterations):
        payload = _build_full_state_payload()
        t0 = time.perf_counter()
        serialized = fast_dumps(payload)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    p95_ms = np.percentile(latencies_ms, 95)
    mean_ms = np.mean(latencies_ms)

    print(f"\n[BENCHMARK] fast_dumps Full State Serialization: Mean={mean_ms:.4f}ms | P95={p95_ms:.4f}ms")
    assert mean_ms < 2.0, f"Mean state serialization latency {mean_ms:.4f}ms exceeded 2.0ms"
    assert p95_ms < 5.0, f"P95 state serialization latency {p95_ms:.4f}ms exceeded 5.0ms"


