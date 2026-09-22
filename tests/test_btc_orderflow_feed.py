"""Unit Tests for Institutional Bitcoin Orderflow Feed and ONNX Microstructure Inference."""

from decimal import Decimal
import numpy as np
import pytest

from kalshi_sim.orderflow.btc_orderflow_feed import BtcOrderflowFeed
from app_2_execution_bot.ml.feature_extractor import KalshiOrderflowFeatureExtractor
from app_2_execution_bot.ml.onnx_engine import KalshiONNXEngine


def test_btc_orderflow_feed_initialization_and_seed():
    """Verify BtcOrderflowFeed seeds a valid 20-level continuous orderbook."""
    feed = BtcOrderflowFeed()
    feed.seed_orderflow(spot_price=87500.0)

    book, trades = feed.get_btc_l2_state()

    assert book.is_spot is True
    assert len(book.yes_book) == 20
    assert len(book.no_book) == 20
    assert book.best_yes_bid is not None
    assert book.best_yes_ask is not None
    assert book.best_yes_bid < book.best_yes_ask
    assert len(trades) >= 10

    # Depth should return 15 levels sorted properly
    bids, asks = book.get_depth(15)
    assert len(bids) == 15
    assert len(asks) == 15
    # Bids descending
    assert bids[0].price > bids[1].price
    # Asks ascending
    assert asks[0].price < asks[1].price


def test_btc_feature_extraction_continuous_asset():
    """Verify 28-dimensional feature extractor processes continuous Bitcoin spot book without NaNs."""
    feed = BtcOrderflowFeed()
    feed.seed_orderflow(spot_price=87500.0)
    book, trades = feed.get_btc_l2_state()

    extractor = KalshiOrderflowFeatureExtractor(target_depth=15)
    features = extractor.extract_features_from_book(book, latest_trades=trades)

    assert isinstance(features, np.ndarray)
    assert features.shape == (28,)
    assert np.isfinite(features).all()
    # Spread should be positive and bounded
    assert features[0] > 0.0
    # VPIN should be bounded [0, 1]
    assert 0.0 <= features[6] <= 1.0


def test_onnx_inference_on_bitcoin_orderflow():
    """Verify QuoLas Nano Microscope ONNX runs on genuine Bitcoin orderflow."""
    feed = BtcOrderflowFeed()
    feed.seed_orderflow(spot_price=87500.0)
    book, trades = feed.get_btc_l2_state()

    engine = KalshiONNXEngine()
    result = engine.process_orderbook_tick(book, latest_trades=trades)

    assert "signal" in result
    assert result["signal"] in ("LONG", "SHORT", "WAIT")
    assert 0.0 <= result["confidence"] <= 1.0
    assert 0.0 <= result["prob_long"] <= 1.0
    assert 0.0 <= result["prob_short"] <= 1.0
    assert 0.0 <= result["prob_wait"] <= 1.0
    assert "vpin_score" in result


def test_binance_trade_aggressor_mapping():
    """Verify Binance m (isBuyerMaker) maps to exact buy/sell sides and signed CVD."""
    feed = BtcOrderflowFeed()
    feed.seed_orderflow(spot_price=87500.0)

    # 1. Taker Buy (m=False)
    feed._handle_binance_trade({
        "p": "87505.00",
        "q": "1.5000",
        "m": False,
        "T": 1725450000000,
        "a": 1001,
    })
    last_trade = feed.trades[-1]
    assert last_trade.taker_side == "buy"
    assert last_trade.count == Decimal("1.5000")
    assert last_trade.price == Decimal("87505.00")

    # 2. Taker Sell (m=True)
    feed._handle_binance_trade({
        "p": "87500.00",
        "q": "2.0000",
        "m": True,
        "T": 1725450001000,
        "a": 1002,
    })
    last_sell = feed.trades[-1]
    assert last_sell.taker_side == "sell"
    assert last_sell.count == Decimal("2.0000")


def test_btc_orderflow_feed_callback_error_handling(caplog):
    """Verify callbacks that raise exceptions are logged and do not prevent other callbacks from executing."""
    feed = BtcOrderflowFeed()
    received_prices = []

    def failing_callback(p: Decimal) -> None:
        raise ValueError("Simulated callback error")

    def working_callback(p: Decimal) -> None:
        received_prices.append(p)

    feed.register_on_tick(failing_callback)
    feed.register_on_tick(working_callback)

    target_price = Decimal("88000.50")
    with caplog.at_level("ERROR"):
        feed._dispatch_on_tick(target_price)

    assert len(received_prices) == 1
    assert received_prices[0] == target_price
    assert "Simulated callback error" in caplog.text
