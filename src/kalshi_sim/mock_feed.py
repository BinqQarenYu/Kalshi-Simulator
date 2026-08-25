"""Live Interactive Mock Feed for Kalshi Simulator.

Generates dynamic, realistic Bitcoin Level-2 order book updates, ticker quotes,
and public trade executions for testing the full quantitative simulation and
ONNX inference pipeline without requiring API credentials.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.schemas import (
    MarketInfo,
    MarketStatus,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
    TickerUpdate,
    Timeframe,
    TradeEvent,
)
from kalshi_sim.simulation_agent import SimulationAgent

logger = logging.getLogger("MockFeed")


class MockKalshiFeed:
    """Simulates real-time Kalshi BTC WebSocket feed and drives SimulationAgent."""

    def __init__(
        self,
        orderbook: OrderBookManager,
        sim_agent: SimulationAgent,
        ticker: str = "KXBTC15M-26AUG2518-T65000",
        tick_interval: float = 0.25,
    ) -> None:
        self.orderbook = orderbook
        self.sim_agent = sim_agent
        self.ticker = ticker
        self.tick_interval = tick_interval
        self.seq = 1
        self.base_btc_price = Decimal("65000")
        self.current_yes_prob = Decimal("0.50")
        self._running = False

    async def run(self) -> None:
        """Execute the mock streaming loop."""
        self._running = True
        logger.info("Initializing Live Mock Market Feed for %s ...", self.ticker)

        # 1. Register Mock Market in Simulation Agent
        now = datetime.now(timezone.utc)
        mock_market = MarketInfo(
            ticker=self.ticker,
            event_ticker="KXBTC15M-26AUG2518",
            series_ticker="KXBTC15M",
            title="Bitcoin above $65,000 at 18:00 UTC",
            status=MarketStatus.OPEN,
            floor_strike=Decimal("65000"),
            strike_type="greater",
            close_time=now,
        )
        self.sim_agent.update_market_cache({self.ticker: mock_market})
        self.sim_agent.set_ticker_timeframe(self.ticker, Timeframe.FIFTEEN_MIN)

        # 2. Emit Initial Order Book Snapshot (15 depth levels)
        yes_levels = []
        no_levels = []
        for i in range(15):
            p_yes = max(Decimal("0.01"), Decimal(str(round(0.48 - i * 0.02, 2))))
            p_no = max(Decimal("0.01"), Decimal(str(round(0.50 - i * 0.02, 2))))
            q_yes = Decimal(str(random.randint(50, 300)))
            q_no = Decimal(str(random.randint(50, 300)))
            yes_levels.append(OrderBookLevel(price=p_yes, quantity=q_yes))
            no_levels.append(OrderBookLevel(price=p_no, quantity=q_no))

        snap = OrderBookSnapshot(
            market_ticker=self.ticker,
            seq=self.seq,
            yes_levels=yes_levels,
            no_levels=no_levels,
            timestamp=now,
        )
        self.orderbook.apply_snapshot(snap)
        await self.sim_agent.on_orderbook_update(self.ticker)
        logger.info("Published initial L2 book snapshot for %s (seq=%d)", self.ticker, self.seq)

        # 3. Continuous Tick Generation Loop
        while self._running:
            await asyncio.sleep(self.tick_interval)
            self.seq += 1

            # Drift yes probability dynamically
            prob_drift = Decimal(str(round(random.gauss(0, 0.01), 3)))
            self.current_yes_prob = max(Decimal("0.10"), min(Decimal("0.90"), self.current_yes_prob + prob_drift))

            # Emit incremental delta
            side = "yes" if random.random() > 0.5 else "no"
            price = Decimal(str(round(float(self.current_yes_prob) + random.uniform(-0.05, 0.05), 2)))
            delta_qty = Decimal(str(random.choice([-20, -10, 15, 25, 50, 100])))

            delta = OrderBookDelta(
                market_ticker=self.ticker,
                seq=self.seq,
                side=side,
                price=max(Decimal("0.01"), min(Decimal("0.99"), price)),
                delta=delta_qty,
                timestamp=datetime.now(timezone.utc),
            )
            self.orderbook.apply_delta(delta)
            await self.sim_agent.on_orderbook_update(self.ticker)

            # Emit Ticker Update
            best_bid, best_ask, spread = self.orderbook.get_top_of_book(self.ticker)
            ticker_up = TickerUpdate(
                market_ticker=self.ticker,
                yes_bid=best_bid,
                yes_ask=best_ask,
                last_price=best_bid or Decimal("0.50"),
                volume=Decimal(str(random.randint(1000, 50000))),
                timestamp=datetime.now(timezone.utc),
            )
            await self.sim_agent.on_ticker_update(ticker_up)

            # Occasionally emit public trade execution
            if random.random() < 0.3:
                trade = TradeEvent(
                    trade_id=f"trade-{self.seq}",
                    market_ticker=self.ticker,
                    yes_price=best_bid or Decimal("0.50"),
                    no_price=Decimal("1.00") - (best_bid or Decimal("0.50")),
                    count=Decimal(str(random.choice([5, 10, 25, 50, 100]))),
                    taker_side="yes" if random.random() > 0.5 else "no",
                    timestamp=datetime.now(timezone.utc),
                )
                await self.sim_agent.on_trade_event(trade)

    def stop(self) -> None:
        self._running = False
