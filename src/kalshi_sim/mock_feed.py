"""Live Interactive Mock Feed for Kalshi Simulator.

Generates dynamic, realistic Bitcoin Level-2 order book updates, ticker quotes,
and public trade executions for testing the full quantitative simulation and
ONNX inference pipeline without requiring API credentials.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

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
from kalshi_sim.tick_writer import TickWriter

logger = logging.getLogger("MockFeed")


class MockKalshiFeed:
    """Simulates real-time Kalshi BTC WebSocket feed and drives SimulationAgent."""

    def __init__(
        self,
        orderbook: OrderBookManager,
        sim_agent: SimulationAgent,
        tick_writer: Optional[TickWriter] = None,
        tick_interval: float = 0.35,
    ) -> None:
        self.orderbook = orderbook
        self.sim_agent = sim_agent
        self.tick_writer = tick_writer
        self.tick_interval = tick_interval
        self._running = False
        self.market_seq: dict[str, int] = {}

        # Underlying BTC Spot Simulation
        self.btc_price = Decimal("65250.00")
        self.btc_drift = Decimal("0.0")

        # Active mock markets: ticker -> dict of metadata & state
        self.markets: dict[str, dict] = {}
        self._init_mock_markets()

    def _init_mock_markets(self) -> None:
        """Create a set of active BTC binary option contracts across strikes & timeframes."""
        now = datetime.now(timezone.utc)

        contract_configs = [
            ("KXBTC15M-T65000", "KXBTC15M", Timeframe.FIFTEEN_MIN, Decimal("65000"), "Bitcoin above $65,000 (15m)", 45),
            ("KXBTC15M-T65500", "KXBTC15M", Timeframe.FIFTEEN_MIN, Decimal("65500"), "Bitcoin above $65,500 (15m)", 60),
            ("KXBTC5M-T65250",  "KXBTC5M",  Timeframe.FIVE_MIN,    Decimal("65250"), "Bitcoin above $65,250 (5m)",  30),
            ("KXBTCH-T65000",   "KXBTCH",   Timeframe.ONE_HOUR,    Decimal("65000"), "Bitcoin above $65,000 (1h)",  120),
        ]

        market_cache = {}
        for ticker, series, tf, strike, title, expiry_sec in contract_configs:
            close_time = now + timedelta(seconds=expiry_sec)
            market_info = MarketInfo(
                ticker=ticker,
                event_ticker=f"{series}-{now.strftime('%d%b%y%H%M').upper()}",
                series_ticker=series,
                title=title,
                status=MarketStatus.OPEN,
                floor_strike=strike,
                strike_type="greater",
                close_time=close_time,
                latest_expiration_time=close_time,
            )
            self.markets[ticker] = {
                "info": market_info,
                "timeframe": tf,
                "strike": strike,
                "close_time": close_time,
                "expiry_sec": expiry_sec,
                "created_at": now,
            }
            market_cache[ticker] = market_info
            self.market_seq[ticker] = 1
            self.sim_agent.set_ticker_timeframe(ticker, tf)

        self.sim_agent.update_market_cache(market_cache)

    def _calc_implied_yes_prob(self, strike: Decimal) -> Decimal:
        """Calculate realistic binary Yes probability based on BTC price distance from strike."""
        diff = float(self.btc_price - strike)
        # Volatility scaling
        scaled = diff / 150.0
        # Sigmoid curve: 1 / (1 + exp(-scaled))
        try:
            prob = 1.0 / (1.0 + math.exp(-scaled))
        except OverflowError:
            prob = 1.0 if scaled > 0 else 0.0

        # Add minor noise
        prob += random.uniform(-0.02, 0.02)
        prob = max(0.03, min(0.97, prob))
        return Decimal(str(round(prob, 2)))

    async def _emit_snapshot_for_market(self, ticker: str) -> None:
        """Construct and emit a full 15-level uncrossed L2 book snapshot."""
        m = self.markets[ticker]
        strike = m["strike"]
        yes_prob = self._calc_implied_yes_prob(strike)

        # Build Yes bids (below yes_prob) and No bids (below 1 - yes_prob)
        yes_best = max(Decimal("0.01"), yes_prob - Decimal("0.01"))
        no_best = max(Decimal("0.01"), (Decimal("1.00") - yes_prob) - Decimal("0.01"))

        yes_levels = []
        no_levels = []
        for i in range(15):
            p_yes = max(Decimal("0.01"), yes_best - Decimal(str(i * 0.02)))
            p_no = max(Decimal("0.01"), no_best - Decimal(str(i * 0.02)))
            q_yes = Decimal(str(random.randint(40, 250)))
            q_no = Decimal(str(random.randint(40, 250)))
            yes_levels.append(OrderBookLevel(price=p_yes, quantity=q_yes))
            no_levels.append(OrderBookLevel(price=p_no, quantity=q_no))

        self.market_seq[ticker] = 1
        snap = OrderBookSnapshot(
            market_ticker=ticker,
            seq=1,
            yes_levels=yes_levels,
            no_levels=no_levels,
            timestamp=datetime.now(timezone.utc),
        )
        self.orderbook.apply_snapshot(snap)
        if self.tick_writer:
            await self.tick_writer.write(snap)

        best_bid, best_ask, spread = self.orderbook.get_top_of_book(ticker)
        logger.info(
            "[SNAPSHOT]  %-18s | seq=1    | YesBid=$%-4s YesAsk=$%-4s | Spread=$%-4s | Strike=$%s",
            ticker, best_bid, best_ask, spread, strike
        )

    async def run(self) -> None:
        """Execute the continuous mock streaming loop."""
        self._running = True
        logger.info("=" * 70)
        logger.info("  STARTING LIVE MOCK MARKET FEED ENGINE (MULTI-MARKET)")
        logger.info("  Simulated BTC Index Starting Price: $%s", self.btc_price)
        logger.info("=" * 70)

        # 1. Initialize Active Markets and emit initial snapshots
        if not self.markets:
            self._init_mock_markets()
        for ticker in self.markets:
            await self._emit_snapshot_for_market(ticker)

        # Initial ticker broadcast
        for ticker, m in self.markets.items():
            best_bid, best_ask, _ = self.orderbook.get_top_of_book(ticker)
            tick_up = TickerUpdate(
                market_ticker=ticker,
                yes_bid=best_bid,
                yes_ask=best_ask,
                last_price=self.btc_price,  # index price proxy
                volume=Decimal(str(random.randint(5000, 20000))),
                timestamp=datetime.now(timezone.utc),
            )
            await self.sim_agent.on_ticker_update(tick_up)
            await self.sim_agent.on_orderbook_update(ticker)

        # 2. Main Live Tick Generation Loop
        tick_counter = 0
        while self._running:
            await asyncio.sleep(self.tick_interval)
            tick_counter += 1

            # A. Dynamic BTC Spot Price Walk (Brownian Motion + Momentum Bursts)
            drift = Decimal(str(round(random.gauss(0, 12.5), 2)))
            # Occasional momentum trend
            if random.random() < 0.15:
                drift += Decimal(str(random.choice([-45.0, 45.0, 80.0, -80.0])))

            self.btc_price = max(Decimal("50000.00"), self.btc_price + drift)

            # B. Pick a market to stream updates for
            active_tickers = list(self.markets.keys())
            if not active_tickers:
                self._init_mock_markets()
                active_tickers = list(self.markets.keys())

            ticker = random.choice(active_tickers)
            m = self.markets[ticker]
            strike = m["strike"]
            timeframe = m["timeframe"]

            # Check for simulated market expiry and auto-rollover
            now = datetime.now(timezone.utc)
            if now >= m["close_time"]:
                logger.info(
                    "[EXPIRY]    Contract %s reached expiry close time. Settling against BTC Index $%s ...",
                    ticker, self.btc_price
                )
                # Send final ticker with BTC settlement price
                final_tick = TickerUpdate(
                    market_ticker=ticker,
                    yes_bid=Decimal("1.00") if self.btc_price >= strike else Decimal("0.00"),
                    yes_ask=Decimal("1.00") if self.btc_price >= strike else Decimal("0.00"),
                    last_price=self.btc_price,
                    volume=Decimal("50000"),
                    timestamp=now,
                )
                await self.sim_agent.on_ticker_update(final_tick)
                self.sim_agent.settle_expired_market(ticker, m["info"], final_tick)

                # Renew contract for next round
                new_close = now + timedelta(seconds=m["expiry_sec"])
                m["close_time"] = new_close
                m["info"].close_time = new_close
                m["info"].latest_expiration_time = new_close
                self.sim_agent.update_market_cache({ticker: m["info"]})
                await self._emit_snapshot_for_market(ticker)
                continue

            # C. Generate Realistic Order Book Delta
            yes_prob = self._calc_implied_yes_prob(strike)
            side = "yes" if random.random() > 0.5 else "no"

            if side == "yes":
                delta_price = max(Decimal("0.01"), min(Decimal("0.99"), yes_prob + Decimal(str(round(random.uniform(-0.04, 0.04), 2)))))
            else:
                no_prob = Decimal("1.00") - yes_prob
                delta_price = max(Decimal("0.01"), min(Decimal("0.99"), no_prob + Decimal(str(round(random.uniform(-0.04, 0.04), 2)))))

            delta_qty = Decimal(str(random.choice([-30, -15, 20, 50, 80, 150])))

            self.market_seq[ticker] = self.market_seq.get(ticker, 1) + 1
            curr_seq = self.market_seq[ticker]

            delta = OrderBookDelta(
                market_ticker=ticker,
                seq=curr_seq,
                side=side,
                price=delta_price,
                delta=delta_qty,
                timestamp=now,
            )
            self.orderbook.apply_delta(delta)
            if self.tick_writer:
                await self.tick_writer.write(delta)

            best_bid, best_ask, spread = self.orderbook.get_top_of_book(ticker)

            # Log delta activity
            if tick_counter % 2 == 0:
                logger.info(
                    "[DELTA]     %-18s | seq=%-4d | %-3s %-4s @ $%-4s | Bid=$%-4s Ask=$%-4s | BTC=$%s",
                    ticker, curr_seq, side.upper(), f"{delta_qty:+}", delta_price,
                    best_bid or "—", best_ask or "—", self.btc_price
                )

            # D. Emit Ticker Update
            ticker_up = TickerUpdate(
                market_ticker=ticker,
                yes_bid=best_bid,
                yes_ask=best_ask,
                last_price=self.btc_price,
                volume=Decimal(str(random.randint(10000, 95000))),
                timestamp=now,
            )
            await self.sim_agent.on_ticker_update(ticker_up)
            if self.tick_writer:
                await self.tick_writer.write(ticker_up)

            # E. Emit Public Trade Executions (simulates aggressive taker prints)
            if random.random() < 0.45:
                trade_price = best_bid if random.random() > 0.5 else (best_ask or Decimal("0.50"))
                trade_price = trade_price or Decimal("0.50")
                trade_count = Decimal(str(random.choice([5, 10, 20, 35, 50, 100])))
                taker_side = "yes" if random.random() > 0.48 else "no"

                trade = TradeEvent(
                    trade_id=f"trade-{curr_seq}",
                    market_ticker=ticker,
                    yes_price=trade_price,
                    no_price=Decimal("1.00") - trade_price,
                    count=trade_count,
                    taker_side=taker_side,
                    timestamp=now,
                )
                await self.sim_agent.on_trade_event(trade)
                if self.tick_writer:
                    await self.tick_writer.write(trade)

                logger.info(
                    "[TRADE]     %-18s | Taker=%-3s | %3d contracts @ YesPrice=$%-4s | Val=$%.2f",
                    ticker, taker_side.upper(), int(trade_count), trade_price,
                    float(trade_price * trade_count)
                )

            # F. Dispatch Orderbook Update to Simulation Agent (Runs ONNX & Heuristics)
            await self.sim_agent.on_orderbook_update(ticker)

    def stop(self) -> None:
        self._running = False
        logger.info("Live Mock Market Feed stopped.")

