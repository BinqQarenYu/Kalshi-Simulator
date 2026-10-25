"""Unit tests for LangGraph POE Evaluator."""

import unittest
from decimal import Decimal
from kalshi_sim.ml.poe_graph_evaluator import run_poe_audit


class TestPOEGraphEvaluator(unittest.TestCase):
    def test_empty_trades(self):
        res = run_poe_audit([])
        self.assertEqual(res["metrics"]["total_trades"], 0)
        self.assertEqual(res["metrics"]["net_pnl"], "0")
        self.assertIn("AGENT POE", res["audit_report_markdown"])

    def test_loss_attribution_and_recommendations(self):
        trades = [
            {"ticker": "KXETH15M-T1", "pnl": -0.50, "why": "ERR_DISPERSION_EXCURSION", "entry_price": 0.40},
            {"ticker": "KXBTC15M-T2", "pnl": 0.50, "why": "NONE", "entry_price": 0.50},
        ]
        res = run_poe_audit(trades)
        self.assertEqual(res["metrics"]["total_trades"], 2)
        self.assertEqual(res["metrics"]["wins"], 1)
        self.assertEqual(res["metrics"]["losses"], 1)
        
        # Recommendations should include moat and ask floor hardening
        recs = {r["parameter"]: r for r in res["recommendations"]}
        self.assertIn("min_spot_diff", recs)
        self.assertIn("min_viable_ask_floor", recs)
        self.assertEqual(recs["min_viable_ask_floor"]["recommended_value"], 0.48)


if __name__ == "__main__":
    unittest.main()
