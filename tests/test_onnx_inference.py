"""Unit tests for ONNX feature extraction, model inference, and GDrive sync."""

import unittest
from decimal import Decimal
from pathlib import Path
import numpy as np

from kalshi_sim.ml.feature_extractor import KalshiOrderflowFeatureExtractor
from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.schemas import (
    L2BookState,
    OrderBookLevel,
    TradeEvent,
)
from kalshi_sim.gdrive_sync import find_rclone_binary


class TestONNXTradingPipeline(unittest.TestCase):

    def setUp(self):
        self.book = L2BookState("KXBTC15M-TEST")
        # Populate 15 bid and ask levels
        for i in range(15):
            bid_p = Decimal(str(round(0.48 - i * 0.01, 2)))
            ask_no_p = Decimal(str(round(0.51 - i * 0.01, 2)))
            if bid_p > 0:
                self.book.yes_book[bid_p] = Decimal("100")
            if ask_no_p > 0:
                self.book.no_book[ask_no_p] = Decimal("120")

    def test_feature_extractor_shape_and_finite(self):
        extractor = KalshiOrderflowFeatureExtractor(target_depth=15, spatial_alpha=0.425)
        vec = extractor.extract_features_from_book(self.book)

        self.assertEqual(len(vec), 28)
        self.assertTrue(np.isfinite(vec).all())
        # First feature is spread_bps
        self.assertGreater(vec[0], 0.0)

    def test_onnx_engine_inference(self):
        engine = KalshiONNXEngine(model_path="models/nano_microscope_overhauled.onnx")
        self.assertIsNotNone(engine.session)

        res = engine.process_orderbook_tick(self.book)

        self.assertIn("signal", res)
        self.assertIn(res["signal"], ["LONG", "SHORT", "WAIT"])
        self.assertIn("confidence", res)
        self.assertIn("vpin_score", res)
        self.assertIn("vpin_veto", res)
        self.assertIn("prob_long", res)
        self.assertIn("prob_short", res)
        self.assertIn("prob_wait", res)

        # Probabilities should sum close to 1.0
        total_p = res["prob_long"] + res["prob_short"] + res["prob_wait"]
        self.assertAlmostEqual(total_p, 1.0, delta=0.05)

    def test_trade_event_processing(self):
        extractor = KalshiOrderflowFeatureExtractor()
        trade = TradeEvent(
            trade_id="t-123",
            market_ticker="KXBTC15M-TEST",
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.52"),
            count=Decimal("10.0"),
            taker_side="yes",
        )
        extractor.process_trade(trade)
        self.assertGreater(len(extractor.cvd_window), 0)

    def test_rclone_binary_discovery(self):
        rclone_path = find_rclone_binary()
        if rclone_path is None:
            self.skipTest("rclone binary not present on local machine")
        self.assertIsNotNone(rclone_path)


if __name__ == "__main__":
    unittest.main()
