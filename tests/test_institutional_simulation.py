"""Unit tests for Institutional Simulation Realism Upgrades.

Verifies:
1. FIFO Queue Priority & Trade Tape Depletion.
2. Marketable Crossing Fills.
3. Multi-Asset Spot Velocity Adverse Selection Drift.
4. Auto-Cancellation on Entry Window Cutoff.
5. 60-Second TWAP Settlement Parity vs Single Spot Tick.
6. Strict Decimal Kalshi Taker vs Maker Free Fee Math.
"""

from datetime import datetime, timezone
from decimal import Decimal
import unittest

from kalshi_sim.order_simulator import OrderSimulator
from shared.schemas import (
    L2BookState,
    OrderSide,
    OrderStatus,
    OrderType,
    Timeframe,
    TradeEvent,
)
from kalshi_sim.settlement import calculate_twap_pnl, evaluate_twap_settlement


class TestInstitutionalSimulation(unittest.TestCase):

    def setUp(self):
        self.sim = OrderSimulator()
        self.book = L2BookState(market_ticker="KXBTC15M-26SEP121200")
        # YES book: bids at 0.48 (50 contracts), 0.47 (100 contracts)
        self.book.yes_book = {
            Decimal("0.48"): Decimal("50"),
            Decimal("0.47"): Decimal("100"),
        }
        # NO book: bids at 0.49 (30 contracts) -> implies best YES ask = 1 - 0.49 = 0.51
        self.book.no_book = {
            Decimal("0.49"): Decimal("30"),
        }

    def test_fifo_queue_priority_depletion(self):
        """Resting limit order joins behind existing depth and only fills when queue is depleted."""
        # Place resting YES limit order at 0.48
        # Existing depth at 0.48 is 50 contracts -> queue_ahead must be 50
        order = self.sim.place_resting_limit_order(
            book=self.book,
            side=OrderSide.YES,
            size=1,
            limit_price=Decimal("0.48"),
            timeframe=Timeframe.FIFTEEN_MIN,
            reasoning="Test FIFO",
        )
        self.assertEqual(order.queue_ahead, 50)
        self.assertEqual(order.status, OrderStatus.RESTING)

        # 1. Trade of 20 contracts at 0.48 prints on tape
        trade_1 = TradeEvent(
            trade_id="tr-001",
            market_ticker="KXBTC15M-26SEP121200",
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.52"),
            count=Decimal("20"),
            taker_side="yes",
        )
        fills = self.sim.process_resting_orders(self.book, latest_trades=[trade_1])
        # Should NOT fill because 30 contracts still remain ahead in queue!
        self.assertEqual(len(fills), 0)
        self.assertEqual(order.queue_ahead, 30)
        self.assertEqual(order.status, OrderStatus.RESTING)

        # 2. Trade of 25 contracts at 0.48 prints
        trade_2 = TradeEvent(
            trade_id="tr-002",
            market_ticker="KXBTC15M-26SEP121200",
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.52"),
            count=Decimal("25"),
            taker_side="yes",
        )
        fills_2 = self.sim.process_resting_orders(self.book, latest_trades=[trade_2])
        self.assertEqual(len(fills_2), 0)
        self.assertEqual(order.queue_ahead, 5)

        # 3. Trade of 10 contracts prints at 0.48 (exhausts remaining 5 + fills our 1 contract!)
        trade_3 = TradeEvent(
            trade_id="tr-003",
            market_ticker="KXBTC15M-26SEP121200",
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.52"),
            count=Decimal("10"),
            taker_side="yes",
        )
        fills_3 = self.sim.process_resting_orders(self.book, latest_trades=[trade_3])
        self.assertEqual(len(fills_3), 1)
        ord_filled, fill = fills_3[0]
        self.assertEqual(ord_filled.status, OrderStatus.FILLED)
        self.assertEqual(fill.fill_price, Decimal("0.48"))
        self.assertEqual(fill.size, 1)
        # Resting maker order fee is $0.00
        self.assertEqual(fill.fee, Decimal("0.00"))

    def test_market_sweep_below_bid_instant_fill(self):
        """If a trade prints below our limit bid, the entire level was swept: instant fill."""
        order = self.sim.place_resting_limit_order(
            book=self.book,
            side=OrderSide.YES,
            size=1,
            limit_price=Decimal("0.48"),
            timeframe=Timeframe.FIFTEEN_MIN,
        )
        self.assertEqual(order.queue_ahead, 50)

        # Trade at 0.47 prints (swept through 0.48)
        sweep_trade = TradeEvent(
            trade_id="tr-sweep",
            market_ticker="KXBTC15M-26SEP121200",
            yes_price=Decimal("0.47"),
            no_price=Decimal("0.53"),
            count=Decimal("5"),
            taker_side="yes",
        )
        fills = self.sim.process_resting_orders(self.book, latest_trades=[sweep_trade])
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0][0].status, OrderStatus.FILLED)
        self.assertEqual(fills[0][1].fill_price, Decimal("0.48"))

    def test_aggressive_spread_crossing_fill(self):
        """Resting order fills immediately if market ask drops to or below limit price."""
        order = self.sim.place_resting_limit_order(
            book=self.book,
            side=OrderSide.YES,
            size=1,
            limit_price=Decimal("0.48"),
            timeframe=Timeframe.FIFTEEN_MIN,
        )

        # Market ask moves down: someone posts NO bid at 0.52 -> best YES ask = 1 - 0.52 = 0.48
        crossed_book = L2BookState(market_ticker="KXBTC15M-26SEP121200")
        crossed_book.yes_book = {Decimal("0.48"): Decimal("50")}
        crossed_book.no_book = {Decimal("0.52"): Decimal("10")}  # best YES ask = 0.48

        fills = self.sim.process_resting_orders(crossed_book)
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0][0].status, OrderStatus.FILLED)
        self.assertEqual(fills[0][1].fill_price, Decimal("0.48"))

    def test_multi_asset_adverse_selection_drift(self):
        """Fast market spot velocity applies +1 cent adverse selection penalty across assets."""
        # BTC: threshold is 15.0
        btc_book = L2BookState(market_ticker="KXBTC15M-ACTIVE")
        btc_book.no_book = {Decimal("0.48"): Decimal("100")}  # best YES ask = 0.52
        _, fill_btc = self.sim.simulate_market_order(
            book=btc_book,
            side=OrderSide.YES,
            size=1,
            timeframe=Timeframe.FIFTEEN_MIN,
            spot_velocity=20.0,  # > 15.0
            asset="BTC",
        )
        # Base ask was 0.52, with +0.01 adverse drift = 0.53
        self.assertEqual(fill_btc.fill_price, Decimal("0.5300"))

        # GOLD: threshold is 0.50
        gold_book = L2BookState(market_ticker="KXGOLD15M-ACTIVE")
        gold_book.no_book = {Decimal("0.48"): Decimal("100")}  # best YES ask = 0.52
        _, fill_gold = self.sim.simulate_market_order(
            book=gold_book,
            side=OrderSide.YES,
            size=1,
            timeframe=Timeframe.FIFTEEN_MIN,
            spot_velocity=0.80,  # > 0.50
            asset="GOLD",
        )
        self.assertEqual(fill_gold.fill_price, Decimal("0.5300"))

        # Calm market: spot velocity 0.10 for Gold -> no adverse drift
        _, fill_calm = self.sim.simulate_market_order(
            book=gold_book,
            side=OrderSide.YES,
            size=1,
            timeframe=Timeframe.FIFTEEN_MIN,
            spot_velocity=0.10,  # < 0.50
            asset="GOLD",
        )
        self.assertEqual(fill_calm.fill_price, Decimal("0.5200"))

    def test_cancel_expired_orders(self):
        """Unfulfilled resting orders expire when entry window closes (T_rem <= cutoff)."""
        order = self.sim.place_resting_limit_order(
            book=self.book,
            side=OrderSide.YES,
            size=1,
            limit_price=Decimal("0.48"),
            timeframe=Timeframe.FIFTEEN_MIN,
        )
        # While T_rem = 300s (> 270s), order remains resting
        expired_early = self.sim.cancel_expired_orders(time_remaining_s=300, cutoff_s=270)
        self.assertEqual(len(expired_early), 0)
        self.assertEqual(len(self.sim.get_all_resting_orders()), 1)

        # When T_rem = 240s (<= 270s), order is cancelled / expired
        expired = self.sim.cancel_expired_orders(time_remaining_s=240, cutoff_s=270)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].status, OrderStatus.EXPIRED)
        self.assertEqual(len(self.sim.get_all_resting_orders()), 0)

    def test_60s_twap_settlement_parity(self):
        """Settlement evaluated against 60s trailing TWAP rather than single instantaneous spot tick."""
        strike = Decimal("85000.00")
        # Case 1: Spot at final second is 85005.00 (above strike), but trailing 60s TWAP was 84995.00 (below strike)
        twap_below = Decimal("84995.00")
        yes_won = evaluate_twap_settlement(strike, twap_below)
        self.assertFalse(yes_won)  # NO won! Single spot tick would have falsely called YES win!

        outcome_yes, gross_yes, net_yes = calculate_twap_pnl(
            side=OrderSide.YES,
            entry_price=Decimal("0.50"),
            contracts=1,
            target_strike=strike,
            twap_60s=twap_below,
            fee=Decimal("0.01"),
        )
        self.assertEqual(outcome_yes, "LOSS")
        self.assertEqual(net_yes, Decimal("-0.50"))

        outcome_no, gross_no, net_no = calculate_twap_pnl(
            side=OrderSide.NO,
            entry_price=Decimal("0.50"),
            contracts=1,
            target_strike=strike,
            twap_60s=twap_below,
            fee=Decimal("0.01"),
        )
        self.assertEqual(outcome_no, "WIN")
        self.assertEqual(gross_no, Decimal("0.50"))
        self.assertEqual(net_no, Decimal("0.49"))  # 0.50 - 0.01 fee

    def test_strict_kalshi_fees(self):
        """Verify exact quadratic taker fee formula and $0.00 maker resting fee."""
        # 50c taker fee: ceil(0.07 * 1 * 0.50 * 0.50 * 100) = ceil(1.75) = 2 cents
        fee_50 = OrderSimulator.calculate_kalshi_taker_fee(Decimal("0.50"), 1)
        self.assertEqual(fee_50, Decimal("0.02"))

        # 95c taker fee: ceil(0.07 * 1 * 0.95 * 0.05 * 100) = ceil(0.3325) = 1 cent floor
        fee_95 = OrderSimulator.calculate_kalshi_taker_fee(Decimal("0.95"), 1)
        self.assertEqual(fee_95, Decimal("0.01"))


if __name__ == "__main__":
    unittest.main()
