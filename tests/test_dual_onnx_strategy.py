"""Comprehensive Test Battery for Dual-ONNX Contradiction Arbitrage System.

Validates:
1. Momentum Scalp regime (Dual UP -> BUY_YES, Dual DOWN -> BUY_NO).
2. Contradiction Arbitrage regime (Spot UP / Kalshi DOWN -> BUY_YES <= discount_ceiling, Spot DOWN / Kalshi UP -> BUY_NO <= discount_ceiling).
3. Microstructural toxicity veto (VPIN breach -> TOXIC_VETO, HOLD).
4. Neutral / Chop gating (Spot WAIT -> CHOP_WAIT, HOLD).
5. Strict Decimal financial rigor for limit prices and Expected Value (EV).
6. Hard 1-contract sizing cap across all market scenarios.
7. Gateway initialization, fallback, and fault tolerance.
8. Dynamic parameter introspection and live updates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kalshi_sim.ml.dual_onnx_gateway import DualONNXGateway, _make_neutral_result
from kalshi_sim.ml.dual_onnx_schemas import DualONNXDecision, DualONNXRegime
from kalshi_sim.ml.dual_onnx_strategy import DualONNXArbitrageBot, _classify_signal
from kalshi_sim.schemas import CryptoAsset, L2BookState, OrderBookLevel, OrderSide


@pytest.fixture
def spot_l2_book() -> L2BookState:
    """Fixture providing simulated Spot BTC L2 order book."""
    book = L2BookState(market_ticker="BTC_SPOT", is_spot=True)
    book.yes_book[Decimal("0.50")] = Decimal("50")
    book.yes_book[Decimal("0.49")] = Decimal("100")
    book.no_book[Decimal("0.51")] = Decimal("50")
    book.no_book[Decimal("0.52")] = Decimal("100")
    return book


@pytest.fixture
def kalshi_l2_book() -> L2BookState:
    """Fixture providing simulated Kalshi binary CLOB L2 order book."""
    book = L2BookState(market_ticker="KXBTC15M-T78650", is_spot=False)
    book.yes_book[Decimal("0.45")] = Decimal("20")
    book.yes_book[Decimal("0.44")] = Decimal("30")
    # For binary book, best_yes_ask = 1.00 - best_no_bid.
    # Setting no_bid to 0.55 makes best_yes_ask = 0.45
    book.no_book[Decimal("0.55")] = Decimal("20")
    book.no_book[Decimal("0.56")] = Decimal("30")
    return book


def test_classify_signal_normalization() -> None:
    """Verify signal string normalization handles all aliases."""
    assert _classify_signal("LONG") == "UP"
    assert _classify_signal("up") == "UP"
    assert _classify_signal("BUY") == "UP"
    assert _classify_signal("YES") == "UP"

    assert _classify_signal("SHORT") == "DOWN"
    assert _classify_signal("down") == "DOWN"
    assert _classify_signal("SELL") == "DOWN"
    assert _classify_signal("NO") == "DOWN"

    assert _classify_signal("WAIT") == "WAIT"
    assert _classify_signal("hold") == "WAIT"
    assert _classify_signal("unknown") == "WAIT"


def test_dual_onnx_decision_immutability_and_dict() -> None:
    """Verify DualONNXDecision is frozen and serializes cleanly."""
    decision = DualONNXDecision(
        action="BUY_YES",
        regime=DualONNXRegime.CONTRADICTION_ARBITRAGE,
        side="yes",
        quolas_signal="UP",
        quolas_confidence=0.82,
        kalshi_signal="DOWN",
        kalshi_confidence=0.71,
        recommended_limit_price=Decimal("0.45"),
        expected_value=Decimal("0.2500"),
        recommended_contracts=1,
        rationale="Contradiction discount buy",
    )

    assert decision.is_trade is True
    assert decision.action == "BUY_YES"
    assert decision.recommended_contracts == 1

    # Verify immutability
    with pytest.raises(Exception):
        decision.action = "HOLD"  # type: ignore[misc]

    # Verify dictionary serialization
    d = decision.to_dict()
    assert d["action"] == "BUY_YES"
    assert d["regime"] == "CONTRADICTION_ARBITRAGE"
    assert d["recommended_limit_price"] == "0.45"
    assert d["expected_value"] == "0.2500"
    assert d["is_trade"] is True


def test_momentum_scalp_both_up(spot_l2_book: L2BookState, kalshi_l2_book: L2BookState) -> None:
    """Verify Agreement Regime: Both UP triggers MOMENTUM_SCALP BUY_YES with 1 contract."""
    bot = DualONNXArbitrageBot(
        discount_ceiling=Decimal("0.48"),
        momentum_max_price=Decimal("0.62"),
        min_ev_dollars=Decimal("0.02"),
    )

    q_infer = {
        "signal": "LONG",
        "confidence": 0.78,
        "vpin_score": 0.25,
        "vpin_veto": False,
    }
    k_infer = {
        "signal": "LONG",
        "confidence": 0.72,
        "vpin_score": 0.30,
        "vpin_veto": False,
    }

    decision = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=450.0,
        spot_diff=35.0,
        quolas_inference=q_infer,
        kalshi_inference=k_infer,
    )

    assert decision.action == "BUY_YES"
    assert decision.regime == DualONNXRegime.MOMENTUM_SCALP
    assert decision.side == "yes"
    assert decision.recommended_contracts == 1
    assert isinstance(decision.recommended_limit_price, Decimal)
    assert isinstance(decision.expected_value, Decimal)
    assert decision.recommended_limit_price <= bot.momentum_max_price
    assert decision.expected_value >= bot.min_ev_dollars


def test_momentum_scalp_both_down(spot_l2_book: L2BookState, kalshi_l2_book: L2BookState) -> None:
    """Verify Agreement Regime: Both DOWN triggers MOMENTUM_SCALP BUY_NO with 1 contract."""
    bot = DualONNXArbitrageBot(
        discount_ceiling=Decimal("0.48"),
        momentum_max_price=Decimal("0.62"),
        min_ev_dollars=Decimal("0.02"),
    )

    q_infer = {
        "signal": "SHORT",
        "confidence": 0.80,
        "vpin_score": 0.22,
        "vpin_veto": False,
    }
    k_infer = {
        "signal": "SHORT",
        "confidence": 0.75,
        "vpin_score": 0.28,
        "vpin_veto": False,
    }

    decision = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=300.0,
        spot_diff=-45.0,
        quolas_inference=q_infer,
        kalshi_inference=k_infer,
    )

    assert decision.action == "BUY_NO"
    assert decision.regime == DualONNXRegime.MOMENTUM_SCALP
    assert decision.side == "no"
    assert decision.recommended_contracts == 1
    assert isinstance(decision.recommended_limit_price, Decimal)
    assert isinstance(decision.expected_value, Decimal)
    assert decision.recommended_limit_price <= bot.momentum_max_price
    assert decision.expected_value >= bot.min_ev_dollars


def test_contradiction_arbitrage_spot_up_kalshi_down(spot_l2_book: L2BookState, kalshi_l2_book: L2BookState) -> None:
    """Verify Contradiction Regime: Spot UP and Kalshi DOWN snipes BUY_YES at discount ceiling."""
    bot = DualONNXArbitrageBot(
        discount_ceiling=Decimal("0.48"),
        min_ev_dollars=Decimal("0.02"),
    )

    q_infer = {
        "signal": "LONG",
        "confidence": 0.85,
        "vpin_score": 0.20,
        "vpin_veto": False,
    }
    k_infer = {
        "signal": "SHORT",
        "confidence": 0.70,
        "vpin_score": 0.35,
        "vpin_veto": False,
    }

    decision = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=250.0,
        spot_diff=15.0,
        quolas_inference=q_infer,
        kalshi_inference=k_infer,
    )

    assert decision.action == "BUY_YES"
    assert decision.regime == DualONNXRegime.CONTRADICTION_ARBITRAGE
    assert decision.side == "yes"
    assert decision.recommended_contracts == 1
    assert isinstance(decision.recommended_limit_price, Decimal)
    assert isinstance(decision.expected_value, Decimal)
    # Price must strictly respect discount ceiling
    assert decision.recommended_limit_price <= Decimal("0.48")
    assert decision.expected_value >= Decimal("0.02")


def test_contradiction_arbitrage_spot_down_kalshi_up(spot_l2_book: L2BookState, kalshi_l2_book: L2BookState) -> None:
    """Verify Contradiction Regime: Spot DOWN and Kalshi UP snipes BUY_NO at discount ceiling."""
    bot = DualONNXArbitrageBot(
        discount_ceiling=Decimal("0.46"),
        min_ev_dollars=Decimal("0.02"),
    )

    q_infer = {
        "signal": "SHORT",
        "confidence": 0.88,
        "vpin_score": 0.20,
        "vpin_veto": False,
    }
    k_infer = {
        "signal": "LONG",
        "confidence": 0.72,
        "vpin_score": 0.25,
        "vpin_veto": False,
    }

    decision = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=200.0,
        spot_diff=-20.0,
        quolas_inference=q_infer,
        kalshi_inference=k_infer,
    )

    assert decision.action == "BUY_NO"
    assert decision.regime == DualONNXRegime.CONTRADICTION_ARBITRAGE
    assert decision.side == "no"
    assert decision.recommended_contracts == 1
    assert decision.recommended_limit_price <= Decimal("0.46")
    assert decision.expected_value >= Decimal("0.02")


def test_toxic_vpin_veto(spot_l2_book: L2BookState, kalshi_l2_book: L2BookState) -> None:
    """Verify Microstructural Veto: High VPIN score triggers TOXIC_VETO and HOLD."""
    bot = DualONNXArbitrageBot(vpin_toxic_threshold=0.70)

    # Spot VPIN is toxic (0.78 > 0.70)
    q_infer = {
        "signal": "LONG",
        "confidence": 0.90,
        "vpin_score": 0.78,
        "vpin_veto": True,
    }
    k_infer = {
        "signal": "LONG",
        "confidence": 0.80,
        "vpin_score": 0.30,
        "vpin_veto": False,
    }

    decision = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=300.0,
        spot_diff=50.0,
        quolas_inference=q_infer,
        kalshi_inference=k_infer,
    )

    assert decision.action == "HOLD"
    assert decision.regime == DualONNXRegime.TOXIC_VETO
    assert decision.recommended_contracts == 0
    assert "Toxic" in decision.rationale


def test_chop_wait_neutral_spot(spot_l2_book: L2BookState, kalshi_l2_book: L2BookState) -> None:
    """Verify Neutral Gating: When Spot Brain is WAIT or low confidence, bot enters CHOP_WAIT."""
    bot = DualONNXArbitrageBot(min_confidence=0.55)

    # Spot brain is neutral WAIT
    q_infer = {
        "signal": "WAIT",
        "confidence": 0.40,
        "vpin_score": 0.20,
        "vpin_veto": False,
    }
    k_infer = {
        "signal": "LONG",
        "confidence": 0.85,
        "vpin_score": 0.25,
        "vpin_veto": False,
    }

    decision = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=300.0,
        spot_diff=10.0,
        quolas_inference=q_infer,
        kalshi_inference=k_infer,
    )

    assert decision.action == "HOLD"
    assert decision.regime == DualONNXRegime.CHOP_WAIT
    assert decision.recommended_contracts == 0


def test_expired_market_hold(spot_l2_book: L2BookState, kalshi_l2_book: L2BookState) -> None:
    """Verify bot refuses to trade on expired cycle (time_to_expiry_s <= 0)."""
    bot = DualONNXArbitrageBot()
    decision = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=0.0,
    )
    assert decision.action == "HOLD"
    assert decision.recommended_contracts == 0


def test_missing_order_books() -> None:
    """Verify bot safely handles missing books with HOLD and 0 contracts."""
    bot = DualONNXArbitrageBot()

    # None books
    decision = bot.evaluate(spot_l2=None, kalshi_l2=None)
    assert decision.action == "HOLD"
    assert decision.recommended_contracts == 0
    assert decision.regime == DualONNXRegime.CHOP_WAIT


def test_hard_one_contract_cap(spot_l2_book: L2BookState, kalshi_l2_book: L2BookState) -> None:
    """Verify institutional hard cap: contracts is strictly 1 for actionable trades, 0 for holds."""
    bot = DualONNXArbitrageBot()

    # Strong BUY_YES setup
    decision_trade = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=300.0,
        quolas_inference={"signal": "LONG", "confidence": 0.85, "vpin_score": 0.20, "vpin_veto": False},
        kalshi_inference={"signal": "LONG", "confidence": 0.75, "vpin_score": 0.20, "vpin_veto": False},
    )
    assert decision_trade.recommended_contracts == 1

    # HOLD setup
    decision_hold = bot.evaluate(
        spot_l2=spot_l2_book,
        kalshi_l2=kalshi_l2_book,
        time_to_expiry_s=300.0,
        quolas_inference={"signal": "WAIT", "confidence": 0.35, "vpin_score": 0.20, "vpin_veto": False},
        kalshi_inference={"signal": "WAIT", "confidence": 0.35, "vpin_score": 0.20, "vpin_veto": False},
    )
    assert decision_hold.recommended_contracts == 0


def test_get_and_update_parameters() -> None:
    """Verify runtime parameter querying and dynamic parameter updates."""
    bot = DualONNXArbitrageBot(
        discount_ceiling=Decimal("0.48"),
        momentum_max_price=Decimal("0.62"),
        min_ev_dollars=Decimal("0.02"),
    )

    params = bot.get_parameters()
    assert params["discount_ceiling"] == 0.48
    assert params["momentum_max_price"] == 0.62
    assert params["min_ev_dollars"] == 0.02
    assert params["asset"] == "BTC"

    # Dynamic update
    updated = bot.update_parameters(
        discount_ceiling=0.45,
        momentum_max_price=0.65,
        min_ev_dollars=0.03,
        vpin_toxic_threshold=0.65,
        asset="ETH",
    )

    assert updated["discount_ceiling"] == 0.45
    assert updated["momentum_max_price"] == 0.65
    assert updated["min_ev_dollars"] == 0.03
    assert updated["vpin_toxic_threshold"] == 0.65
    assert updated["asset"] == "ETH"
    assert bot.discount_ceiling == Decimal("0.45")
    assert bot.asset == CryptoAsset.ETH


def test_gateway_fallback_and_inference(tmp_path: Path) -> None:
    """Verify DualONNXGateway initialization, QuoLas fallback, and infer_both interface."""
    dummy_quolas = tmp_path / "nano_microscope_overhauled.onnx"
    dummy_kalshi = tmp_path / "kalshi_onnx.onnx"

    # Both non-existent -> gateway runs in stub mode without throwing exception
    gateway = DualONNXGateway(
        quolas_model_path=dummy_quolas,
        kalshi_model_path=dummy_kalshi,
        fallback_to_quolas=True,
    )

    status = gateway.get_status()
    assert "quolas_ready" in status
    assert "kalshi_ready" in status

    # Inference with None books
    q_res, k_res = gateway.infer_both(spot_book=None, kalshi_book=None)
    assert q_res["signal"] == "WAIT"
    assert k_res["signal"] == "WAIT"
    assert q_res["confidence"] == 1.0
