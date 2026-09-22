"""Unit tests for GoldONNXBot (32-D ONNX Spacetime Inference Engine)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app_1_machine_engine.ml.export_gold_onnx import export_gold_to_onnx
from app_1_machine_engine.ml.gold_onnx_bot import GoldONNXBot
from shared.schemas import L2BookState, MarketInfo, MarketStatus, OrderSide, OrderType


@pytest.fixture
def test_model_path(tmp_path: Path) -> Path:
    """Create a temporary valid 32-D gold ONNX model."""
    model_path = tmp_path / "gold.onnx"
    export_gold_to_onnx(output_path=model_path, verify_parity=True)
    return model_path


@pytest.fixture
def mock_gold_market() -> MarketInfo:
    """Mock Kalshi Gold MarketInfo."""
    return MarketInfo(
        ticker="KXGOLD15M-T2500",
        title="Will Gold be above $2500?",
        status=MarketStatus.OPEN,
        floor_strike=Decimal("2500.00"),
        target_strike=Decimal("2500.00"),
        yes_bid=Decimal("0.48"),
        yes_ask=Decimal("0.52"),
    )


@pytest.fixture
def mock_gold_orderbook() -> L2BookState:
    """Mock L2 Order Book for Gold."""
    book = L2BookState(market_ticker="KXGOLD15M-T2500")
    book.yes_book = {Decimal("0.48"): Decimal("100"), Decimal("0.47"): Decimal("200")}
    book.no_book = {Decimal("0.52"): Decimal("150"), Decimal("0.54"): Decimal("250")}
    return book


def test_gold_onnx_bot_initialization_and_inference(test_model_path: Path) -> None:
    """Verify session creation and raw inference."""
    bot = GoldONNXBot(model_path=test_model_path)
    assert bot.session is not None

    sample_features = np.zeros(32, dtype=np.float32)
    probs = bot.infer(sample_features)

    assert probs.shape == (3,)
    assert (probs >= 0.0).all()
    np.testing.assert_allclose(probs.sum(), 1.0, atol=1e-4)


def test_gold_onnx_bot_velocity_shield(test_model_path: Path, mock_gold_market: MarketInfo, mock_gold_orderbook: L2BookState) -> None:
    """Verify velocity shield blocks entry when spot changes rapidly."""
    from datetime import datetime, timezone
    bot = GoldONNXBot(model_path=test_model_path, spot_velocity_limit=Decimal("0.50"))

    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Feed rapid spot jumps within 2 seconds
    bot.update_spot(ts=now.timestamp() - 2.0, spot_price=Decimal("2500.00"))
    bot.update_spot(ts=now.timestamp(), spot_price=Decimal("2501.50"))  # $1.50 change in 2 seconds

    decision = bot.decide(
        market=mock_gold_market,
        orderbook=mock_gold_orderbook,
        spot_price=Decimal("2501.50"),
        time_remaining_s=300,
        now_utc=now,
    )

    assert decision.action == "WAIT"
    assert "[VELOCITY SHIELD]" in decision.rationale


def test_gold_onnx_bot_timing_window(test_model_path: Path, mock_gold_market: MarketInfo, mock_gold_orderbook: L2BookState) -> None:
    """Verify timing window gates."""
    bot = GoldONNXBot(model_path=test_model_path)

    # Too early (T = 500s > 480s)
    dec_early = bot.decide(
        market=mock_gold_market,
        orderbook=mock_gold_orderbook,
        spot_price=Decimal("2500.00"),
        time_remaining_s=500,
    )
    assert dec_early.action == "WAIT"
    assert "Awaiting late-cycle window" in dec_early.rationale

    # Too late / expiration quarantine (T = 60s < 120s)
    dec_late = bot.decide(
        market=mock_gold_market,
        orderbook=mock_gold_orderbook,
        spot_price=Decimal("2500.00"),
        time_remaining_s=60,
    )
    assert dec_late.action == "WAIT"
    assert "Expiration quarantine" in dec_late.rationale


def test_gold_onnx_bot_conviction_up_decision(
    test_model_path: Path,
    mock_gold_market: MarketInfo,
    mock_gold_orderbook: L2BookState,
) -> None:
    """Verify BUY YES generated when model has high P(UP) conviction."""
    bot = GoldONNXBot(model_path=test_model_path, min_confidence=0.70)

    # Mock inference to return 85% UP
    with patch.object(bot, "infer", return_value=np.array([0.85, 0.10, 0.05], dtype=np.float32)):
        decision = bot.decide(
            market=mock_gold_market,
            orderbook=mock_gold_orderbook,
            spot_price=Decimal("2502.00"),  # $2.00 above strike
            time_remaining_s=300,
        )

        assert decision.action == "BUY"
        assert decision.side == OrderSide.YES
        assert decision.contracts == 1  # Sizing armor
        assert decision.price <= Decimal("0.52")
        assert decision.confidence == pytest.approx(85.0)
        assert "[32-D ONNX YES]" in decision.rationale


def test_gold_onnx_bot_conviction_down_decision(
    test_model_path: Path,
    mock_gold_market: MarketInfo,
    mock_gold_orderbook: L2BookState,
) -> None:
    """Verify BUY NO generated when model has high P(DOWN) conviction."""
    bot = GoldONNXBot(model_path=test_model_path, min_confidence=0.70)

    # Mock inference to return 88% DOWN
    with patch.object(bot, "infer", return_value=np.array([0.05, 0.88, 0.07], dtype=np.float32)):
        decision = bot.decide(
            market=mock_gold_market,
            orderbook=mock_gold_orderbook,
            spot_price=Decimal("2498.00"),  # $2.00 below strike
            time_remaining_s=250,
        )

        assert decision.action == "BUY"
        assert decision.side == OrderSide.NO
        assert decision.contracts == 1
        assert decision.price <= Decimal("0.52")
        assert decision.confidence == pytest.approx(88.0)
        assert "[32-D ONNX NO]" in decision.rationale


def test_gold_onnx_bot_dead_zone_veto(
    test_model_path: Path,
    mock_gold_market: MarketInfo,
    mock_gold_orderbook: L2BookState,
) -> None:
    """Verify dead-zone veto blocks BUY YES if spot is significantly below strike."""
    bot = GoldONNXBot(model_path=test_model_path, min_confidence=0.70, dead_zone_gold_usd=Decimal("0.75"))

    # Model says 80% UP, but spot is $2497 vs Strike $2500 (diff -3.00 < -0.75)
    with patch.object(bot, "infer", return_value=np.array([0.80, 0.10, 0.10], dtype=np.float32)):
        decision = bot.decide(
            market=mock_gold_market,
            orderbook=mock_gold_orderbook,
            spot_price=Decimal("2497.00"),
            time_remaining_s=300,
        )

        assert decision.action == "WAIT"
        assert "[DEAD-ZONE VETO]" in decision.rationale
