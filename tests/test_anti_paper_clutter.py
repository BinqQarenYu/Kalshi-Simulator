"""Unit test verifying that paper/shadow trades NEVER persist to disk reports.

Rule 7 (Empirical Truth) & User Directive:
Only live executions are saved to data/win_loss_reports.json and data/eth_win_loss_reports.json.
Paper and shadow trades update the continuous experience buffer and ONNX calibration in-memory,
without polluting disk reports.
"""

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from kalshi_sim.ml.btc_bot1v4.btc_bot1v4_engine import BtcBot1V4Engine
from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine
from kalshi_sim.server_settlements import record_win_loss_event_report


class DummyState:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.win_loss_reports = []
        self.mode = "paper"
        self.starting_capital = Decimal("25.00")
        self.order_client = None
        self.sim_agent = None
        self.guardrails_agent = None
        self.experience_buffer = None
        self.cfbenchmarks_sync = None
        self.bot1_v4_engine = None

    def save_persisted_reports(self) -> None:
        out_file = self.data_dir / "win_loss_reports.json"
        out_file.write_text(json.dumps(self.win_loss_reports, indent=2), encoding="utf-8")


class TestAntiPaperClutter(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_btc_engine_does_not_save_paper_trade(self) -> None:
        hist_file = self.root / "btc_reports.json"
        engine = BtcBot1V4Engine(history_file=str(hist_file))

        # Paper settlement
        rep_paper = engine.record_cycle_settlement(
            won_or_pnl=True,
            ticker="KXBTC15M-TEST-PAPER",
            side="yes",
            entry_price=Decimal("0.45"),
            settlement_spot_price=Decimal("85050.00"),
            strike_price=Decimal("85000.00"),
            execution_mode="paper",
        )
        self.assertIsNotNone(rep_paper)
        self.assertFalse(hist_file.exists(), "Paper trade must NOT write report file to disk")

        # Shadow settlement
        rep_shadow = engine.record_cycle_settlement(
            won_or_pnl=True,
            ticker="KXBTC15M-TEST-SHADOW",
            side="yes",
            entry_price=Decimal("0.45"),
            settlement_spot_price=Decimal("85050.00"),
            strike_price=Decimal("85000.00"),
            execution_mode="shadow",
        )
        self.assertIsNotNone(rep_shadow)
        self.assertFalse(hist_file.exists(), "Shadow trade must NOT write report file to disk")

        # Live settlement MUST write to disk
        rep_live = engine.record_cycle_settlement(
            won_or_pnl=True,
            ticker="KXBTC15M-TEST-LIVE",
            side="yes",
            entry_price=Decimal("0.45"),
            settlement_spot_price=Decimal("85050.00"),
            strike_price=Decimal("85000.00"),
            execution_mode="live",
        )
        self.assertIsNotNone(rep_live)
        self.assertTrue(hist_file.exists(), "Live trade MUST write report file to disk")
        saved = json.loads(hist_file.read_text(encoding="utf-8"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["execution_mode"], "live")

    def test_eth_engine_does_not_save_paper_trade(self) -> None:
        hist_file = self.root / "eth_reports.json"
        engine = EthBot1V4Engine(history_file=str(hist_file))

        # Paper settlement
        rep_paper = engine.record_cycle_settlement(
            won_or_pnl=True,
            ticker="KXETH15M-TEST-PAPER",
            side="yes",
            entry_price=Decimal("0.42"),
            settlement_spot_price=Decimal("2605.00"),
            strike_price=Decimal("2600.00"),
            execution_mode="paper",
        )
        self.assertIsNotNone(rep_paper)
        self.assertFalse(hist_file.exists(), "ETH Paper trade must NOT write report file to disk")

        # Live settlement MUST write to disk
        rep_live = engine.record_cycle_settlement(
            won_or_pnl=True,
            ticker="KXETH15M-TEST-LIVE",
            side="yes",
            entry_price=Decimal("0.42"),
            settlement_spot_price=Decimal("2605.00"),
            strike_price=Decimal("2600.00"),
            execution_mode="live",
        )
        self.assertIsNotNone(rep_live)
        self.assertTrue(hist_file.exists(), "ETH Live trade MUST write report file to disk")
        saved = json.loads(hist_file.read_text(encoding="utf-8"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["execution_mode"], "live")

    def test_server_settlements_gating(self) -> None:
        from kalshi_sim.server_settlements import init_server_settlements
        state = DummyState(self.root)
        init_server_settlements(lambda: state, lambda bot_id: None)

        # Record shadow settlement
        record_win_loss_event_report(
            ticker="KXBTC15M-SHADOW",
            side="yes",
            contracts=1,
            entry_price=Decimal("0.45"),
            settlement_btc_price=Decimal("85020.00"),
            strike_price=Decimal("85000.00"),
            execution_mode="shadow",
            skip_guardrails=True,
        )
        self.assertEqual(len(state.win_loss_reports), 0, "Non-live report must not be inserted into state.win_loss_reports")
        self.assertFalse((self.root / "win_loss_reports.json").exists())

        # Record live settlement
        record_win_loss_event_report(
            ticker="KXBTC15M-LIVE",
            side="yes",
            contracts=1,
            entry_price=Decimal("0.45"),
            settlement_btc_price=Decimal("85020.00"),
            strike_price=Decimal("85000.00"),
            execution_mode="live",
            skip_guardrails=True,
        )
        self.assertEqual(len(state.win_loss_reports), 1)
        self.assertTrue((self.root / "win_loss_reports.json").exists())


if __name__ == "__main__":
    unittest.main()
