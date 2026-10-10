"""Simulation Settlement Coordinator — handles settlement of expired markets across portfolios.

Extracts settlement logging, DB enqueuing, cycle tracking, and win/loss reporting
from SimulationAgent to keep the architecture clean, modular, and maintainable.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.db import DatabaseWriter
from kalshi_sim.execution_logger import ExecutionLogger
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import MarketInfo, MarketStatus, TickerUpdate
from kalshi_sim.settlement import check_expirations, settle_position

logger = logging.getLogger(__name__)


class SimulationSettlementCoordinator:
    """Coordinates expiration checks and multi-portfolio settlement recording."""

    def __init__(
        self,
        exec_logger: ExecutionLogger,
        db_writer: DatabaseWriter,
        guardrails: AgentGuardrails,
        spot_price_getter: Optional[Callable[[], Decimal]] = None,
    ) -> None:
        self._exec_logger = exec_logger
        self._db_writer = db_writer
        self._guardrails = guardrails
        self._spot_price_getter = spot_price_getter

    def settle_expired_market(
        self,
        ticker: str,
        market_info: MarketInfo,
        final_tick: Optional[TickerUpdate],
        portfolios_to_settle: list[tuple[Portfolio, str]],
        macro_trend_bot: Optional[Any] = None,
        execution_mode: str = "simulated",
        spot_price_getter: Optional[Callable[[], Decimal]] = None,
    ) -> None:
        """Immediately settle an expired position against the final BTC settlement price across portfolios."""
        getter = spot_price_getter or self._spot_price_getter
        spot_dec = None
        if getter:
            try:
                spot_dec = Decimal(str(getter()))
            except Exception:
                pass

        for p_inst, b_type in portfolios_to_settle:
            result = settle_position(
                portfolio=p_inst,
                ticker=ticker,
                market_info=market_info,
                last_ticker_update=final_tick,
                btc_settle_price=spot_dec,
            )
            if result:
                self._exec_logger.log_settlement(result)
                self._db_writer.enqueue_settlement(
                    settlement_id=f"st_{int(time.time()*1000)}_{result.ticker}_{random.randint(100, 999)}",
                    ticker=result.ticker,
                    side=result.side.value,
                    size=result.size,
                    entry_price=float(result.entry_price),
                    settlement_price=float(result.settlement_price),
                    outcome=result.outcome,
                    pnl=float(result.pnl),
                    balance_after=float(p_inst.balance),
                    bot_type=b_type,
                    execution_mode="simulated",
                )
                self._guardrails.record_cycle_settlement(
                    ticker=result.ticker,
                    outcome=result.outcome,
                    pnl=result.pnl,
                    balance_after=p_inst.balance,
                    cycle_id=result.ticker,
                    execution_mode="simulated",
                )
                if macro_trend_bot and hasattr(macro_trend_bot, "record_cycle_outcome"):
                    if b_type in ("macro_trend_dominion", "macro_onnx", "macro_trend", "macro_trend_dominion_bot"):
                        try:
                            macro_trend_bot.record_cycle_outcome(
                                cycle_id=result.ticker,
                                ticker=result.ticker,
                                call=result.side.value.upper(),
                                predicted_prob=0.65,
                                fill_price=result.entry_price,
                                outcome=result.outcome.upper(),
                                pnl=result.pnl,
                                execution_mode=execution_mode,
                            )
                        except Exception as exc:
                            logger.debug("Failed to record macro dominion cycle outcome: %s", exc)
                try:
                    from kalshi_sim.server import record_win_loss_event_report

                    strike_val = (
                        market_info.floor_strike
                        if market_info.floor_strike is not None
                        else (
                            market_info.target_strike
                            if market_info.target_strike is not None
                            else Decimal("0.0")
                        )
                    )
                    settle_spot = spot_dec if spot_dec is not None else strike_val
                    is_5m = (
                        "5M" in result.ticker and "15M" not in result.ticker
                    ) or getattr(market_info, "timeframe", None) == "5m"
                    tf_val = "5m" if is_5m else "15m"
                    record_win_loss_event_report(
                        ticker=result.ticker,
                        side=result.side.value,
                        contracts=result.size,
                        entry_price=result.entry_price,
                        settlement_btc_price=settle_spot,
                        strike_price=strike_val,
                        timeframe=tf_val,
                        ai_confidence=0.82,
                        ai_rationale=f"Natural {tf_val.upper()} Expiration Settlement for {b_type} | BTC: ${float(settle_spot):,.2f} vs Strike: ${float(strike_val):,.2f}",
                        vpin_score=0.15,
                        ev_edge=0.10,
                        bot_type=b_type,
                        execution_mode="simulated",
                        custom_outcome=result.outcome,
                        custom_pnl=result.pnl,
                        balance_after=p_inst.balance,
                    )
                except Exception as rep_err:
                    logger.debug("Failed to record win-loss report on settlement: %s", rep_err)

                logger.info(
                    "[SETTLED] [%-20s] %-18s | %-3s %s %d contracts | P&L=%+$7.2f | Balance=$%.2f",
                    b_type,
                    ticker,
                    result.side.value.upper(),
                    result.outcome.upper(),
                    result.size,
                    result.pnl,
                    p_inst.balance,
                )

    def check_and_settle_expirations(
        self,
        now: datetime,
        market_cache: dict[str, MarketInfo],
        ticker_cache: dict[str, TickerUpdate],
        portfolios_to_check: list[tuple[Portfolio, str]],
        macro_trend_bot: Optional[Any] = None,
        execution_mode: str = "simulated",
        settle_callback: Optional[Callable[[str, MarketInfo, Optional[TickerUpdate]], None]] = None,
    ) -> None:
        """Scan open positions in portfolios, identify expired markets, and trigger settlement."""
        for p_inst, b_type in portfolios_to_check:
            expired_tickers = check_expirations(
                positions=p_inst.open_positions,
                markets=market_cache,
                current_time=now,
            )
            for ticker in expired_tickers:
                market_info = market_cache.get(ticker)
                if market_info is None:
                    market_info = MarketInfo(
                        ticker=ticker,
                        series_ticker=ticker.split("-")[0] if "-" in ticker else "KXBTC15M",
                        title=ticker,
                        subtitle="",
                        status=MarketStatus.CLOSED,
                        close_time=now,
                        expiration_time=now,
                        floor_strike=None,
                        cap_strike=None,
                        strike_type="greater",
                    )
                last_update = ticker_cache.get(ticker)
                if settle_callback:
                    settle_callback(ticker, market_info, last_update)
                else:
                    self.settle_expired_market(
                        ticker=ticker,
                        market_info=market_info,
                        final_tick=last_update,
                        portfolios_to_settle=[(p_inst, b_type)],
                        macro_trend_bot=macro_trend_bot,
                        execution_mode=execution_mode,
                    )
