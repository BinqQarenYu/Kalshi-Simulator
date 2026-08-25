"""Unit tests for the Kalshi BTC Quantitative Trading Simulation Engine."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import (
    L2BookState,
    MarketInfo,
    MarketStatus,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderSide,
    OrderType,
    SimulatedFill,
    Timeframe,
)
from kalshi_sim.settlement import check_expirations, settle_position


class TestKalshiSimulation(unittest.TestCase):

    def test_orderbook_snapshot_and_delta(self):
        obm = OrderBookManager()
        snap = OrderBookSnapshot(
            market_ticker="KXBTC15M-TEST",
            seq=1,
            yes_levels=[
                OrderBookLevel(price=Decimal("0.48"), quantity=Decimal("100")),
                OrderBookLevel(price=Decimal("0.47"), quantity=Decimal("200")),
            ],
            no_levels=[
                OrderBookLevel(price=Decimal("0.51"), quantity=Decimal("150")),
                OrderBookLevel(price=Decimal("0.50"), quantity=Decimal("300")),
            ],
        )
        book = obm.apply_snapshot(snap)
        self.assertEqual(book.best_yes_bid, Decimal("0.48"))
        self.assertEqual(book.best_no_bid, Decimal("0.51"))
        self.assertEqual(book.best_yes_ask, Decimal("0.49"))  # 1 - 0.51
        self.assertEqual(book.spread, Decimal("0.01"))        # 0.49 - 0.48
        self.assertEqual(book.mid_price, Decimal("0.485"))

        # Apply delta
        delta = OrderBookDelta(
            market_ticker="KXBTC15M-TEST",
            seq=2,
            side="yes",
            price=Decimal("0.48"),
            delta=Decimal("-50"),
        )
        updated = obm.apply_delta(delta)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.yes_book[Decimal("0.48")], Decimal("50"))

        # Sequence gap test
        gap_delta = OrderBookDelta(
            market_ticker="KXBTC15M-TEST",
            seq=5,  # gap!
            side="yes",
            price=Decimal("0.48"),
            delta=Decimal("10"),
        )
        res = obm.apply_delta(gap_delta)
        self.assertIsNone(res)
        self.assertTrue(book.is_stale)

    def test_portfolio_ledger_and_settlement_yes_win(self):
        port = Portfolio(starting_balance=Decimal("10000"))
        fill = SimulatedFill(
            order_id="test-1",
            ticker="KXBTC15M-TEST",
            side=OrderSide.YES,
            size=100,
            fill_price=Decimal("0.48"),
            slippage=Decimal("0.001"),
            cost=Decimal("48.00"),
        )
        port.open_position(fill, Timeframe.FIFTEEN_MIN)
        self.assertEqual(port.balance, Decimal("9952.00"))
        self.assertEqual(len(port.open_positions), 1)

        # Settle Yes win (RTI 65500 >= strike 65000)
        res = port.settle_position(
            ticker="KXBTC15M-TEST",
            settlement_price=Decimal("65500"),
            floor_strike=Decimal("65000"),
            cap_strike=None,
            strike_type="greater",
        )
        self.assertIsNotNone(res)
        self.assertEqual(res.outcome, "win")
        self.assertEqual(res.pnl, Decimal("52.00"))  # 100 * 1.00 - 48.00
        self.assertEqual(port.balance, Decimal("10052.00"))
        self.assertEqual(len(port.open_positions), 0)

    def test_portfolio_settlement_yes_loss(self):
        port = Portfolio(starting_balance=Decimal("10000"))
        fill = SimulatedFill(
            order_id="test-2",
            ticker="KXBTC15M-TEST2",
            side=OrderSide.YES,
            size=50,
            fill_price=Decimal("0.55"),
            cost=Decimal("27.50"),
        )
        port.open_position(fill, Timeframe.FIFTEEN_MIN)
        self.assertEqual(port.balance, Decimal("9972.50"))

        # Settle Yes loss (RTI 64000 < strike 65000)
        res = port.settle_position(
            ticker="KXBTC15M-TEST2",
            settlement_price=Decimal("64000"),
            floor_strike=Decimal("65000"),
            cap_strike=None,
            strike_type="greater",
        )
        self.assertIsNotNone(res)
        self.assertEqual(res.outcome, "loss")
        self.assertEqual(res.pnl, Decimal("-27.50"))
        self.assertEqual(port.balance, Decimal("9972.50"))

    def test_order_simulator_market_order(self):
        sim = OrderSimulator()
        book = L2BookState("KXBTC15M-TEST")
        book.no_book = {
            Decimal("0.52"): Decimal("20"),  # yes ask = 0.48
            Decimal("0.50"): Decimal("50"),  # yes ask = 0.50
        }
        order_res = sim.simulate_market_order(
            book=book,
            side=OrderSide.YES,
            size=30,
            timeframe=Timeframe.FIFTEEN_MIN,
            reasoning="Test scalp",
        )
        self.assertIsNotNone(order_res)
        order, fill = order_res
        self.assertEqual(fill.size, 30)
        self.assertGreater(fill.fill_price, Decimal("0.48"))
        self.assertEqual(fill.cost, fill.fill_price * 30)


if __name__ == "__main__":
    unittest.main()
