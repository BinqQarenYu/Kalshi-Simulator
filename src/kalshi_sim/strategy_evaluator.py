"""Strategy Evaluation Coordinator — handles market evaluation for trading bots.

Orchestrates multi-bot signal processing across:
- Macro ONNX & Macro Trend Dominion
- Dominion 2 Bot
- 3-Step Domination Bot
- Dual ONNX Arbitrage Bot
- ONNX Microstructure Neural Net Bot

Keeps SimulationAgent focused and lightweight while maintaining exact trading invariants.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.db import DatabaseWriter
from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.ml.dominion_2_bot import Dominion2Bot
from kalshi_sim.ml.dual_onnx_strategy import DualONNXArbitrageBot
try:
    from kalshi_sim.quant.market_maker_engine import MarketMakerEngine
except (ImportError, ModuleNotFoundError):
    MarketMakerEngine = None  # type: ignore
from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.ml.statistical_ev_engine import StatisticalEVEngine
from kalshi_sim.orderflow.btc_orderflow_feed import BtcOrderflowFeed
from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.process_lock import get_active_lock_holder
from kalshi_sim.schemas import L2BookState, MarketInfo, OrderSide, Timeframe, TradeEvent

logger = logging.getLogger(__name__)

MAX_CONCURRENT_POSITIONS = 5


class StrategyEvaluationCoordinator:
    """Evaluates quantitative trading models and generates order intents."""

    def __init__(
        self,
        guardrails: AgentGuardrails,
        simulator: OrderSimulator,
        db_writer: DatabaseWriter,
        onnx_engine: KalshiONNXEngine,
        ev_engine: StatisticalEVEngine,
        macro_trend_bot: MacroTrendDominionBot,
        dominion2_bot: Dominion2Bot,
        domination_bot: ThreeStepDominationBot,
        dual_onnx_bot: DualONNXArbitrageBot,
        btc_orderflow_feed: BtcOrderflowFeed,
        spot_price_getter: Optional[Callable[[], Decimal]] = None,
        bot1_v4_engine: Optional[Any] = None,
        market_maker_engine: Optional[MarketMakerEngine] = None,
    ) -> None:
        self._guardrails = guardrails
        self._simulator = simulator
        self._db_writer = db_writer
        self._onnx_engine = onnx_engine
        self._ev_engine = ev_engine
        self._macro_trend_bot = macro_trend_bot
        self._dominion2_bot = dominion2_bot
        self._domination_bot = domination_bot
        self._dual_onnx_bot = dual_onnx_bot
        self._btc_orderflow_feed = btc_orderflow_feed
        self._spot_price_getter = spot_price_getter
        self._bot1_v4_engine = bot1_v4_engine
        self._market_maker_engine = market_maker_engine or (MarketMakerEngine() if MarketMakerEngine is not None else None)

        # Cooldown and rate-limiting caches
        self._last_macro_eval_time: dict[str, float] = {}
        self._last_dom_eval_time: dict[str, float] = {}
        self._last_dom_exit_eval_time: dict[str, float] = {}
        self._last_dual_onnx_eval_time: dict[str, float] = {}
        self._last_onnx_ts: dict[str, float] = {}
        self._last_pred_log_time: dict[str, float] = {}
        self._spot_price_history: dict[str, list[tuple[float, float]]] = {}
        self._eval_count: int = 0

    async def evaluate_market(
        self,
        ticker: str,
        book: L2BookState,
        active_strategy_bot: str,
        execution_mode: str,
        market_cache: dict[str, MarketInfo],
        recent_trades: dict[str, list[TradeEvent]],
        ticker_timeframe_map: dict[str, Timeframe],
        portfolio_macro_trend: Portfolio,
        portfolio_dominion2: Portfolio,
        portfolio_domination: Portfolio,
        portfolio_onnx: Portfolio,
        portfolio_dual_onnx: Portfolio,
        portfolio_market_maker: Portfolio,
        place_order_fn: Callable[..., Any],
    ) -> None:
        """Evaluate trading decisions concurrently for active strategy bots."""
        timeframe = ticker_timeframe_map.get(ticker)
        if timeframe is None:
            timeframe = Timeframe.FIVE_MIN if ("5M" in ticker and "15M" not in ticker) else Timeframe.FIFTEEN_MIN
            ticker_timeframe_map[ticker] = timeframe

        trades = recent_trades.get(ticker, [])

        # Ensure active cycle contract (<= 930s to expiration)
        market_info = market_cache.get(ticker)
        if market_info and market_info.expiration_time:
            now_utc = datetime.now(timezone.utc)
            remaining_s = (market_info.expiration_time - now_utc).total_seconds()
            if remaining_s <= 0 or remaining_s > 930:
                return
            if remaining_s <= 45:
                self._simulator.cancel_resting_orders_for_ticker(ticker)

        # STRICT ISOLATION: In LIVE mode, execute only active bot on active 15M contract
        is_live = execution_mode == "live"
        is_mm = active_strategy_bot in ("market_maker", "bot6_market_maker", "dual_fleet", "both")
        if is_live:
            if is_mm:
                if not (ticker.startswith("KXBTC15M") or ticker.startswith("KXDOGE15M")):
                    return
            elif not ticker.startswith("KXBTC15M"):
                return

        # If another engine holds exclusive live lock, silence Mother evaluations
        if is_live:
            holder = get_active_lock_holder()
            if holder and holder[1] != os.getpid():
                return

        # Guardrails cycle lock check (exempt market maker to permit two-sided continuous liquidity)
        cycle_key = market_info.event_ticker if (market_info and market_info.event_ticker) else ticker
        if is_live and active_strategy_bot not in ("market_maker", "bot6_market_maker", "dual_fleet", "both") and (cycle_key in self._guardrails._cycle_locks or ticker in self._guardrails._cycle_locks):
            return

        # BOT 3: Macro ONNX & Macro Trend Dominion
        if active_strategy_bot in (
            "macro_onnx",
            "macro_onnx_bot",
            "macro_trend_onnx_fusion",
            "macro_trend_dominion",
            "macro_trend",
            "macro_trend_dominion_bot",
        ):
            await self._eval_macro_trend(
                ticker=ticker,
                book=book,
                market_info=market_info,
                trades=trades,
                timeframe=timeframe,
                portfolio=portfolio_macro_trend,
                active_strategy_bot=active_strategy_bot,
                is_live=is_live,
                place_order_fn=place_order_fn,
            )

        # BOT 0: Dominion 2 Bot
        if active_strategy_bot in ("dominion_2_bot", "dominion2", "dominion_v2"):
            await self._eval_dominion2(
                ticker=ticker,
                book=book,
                market_info=market_info,
                trades=trades,
                timeframe=timeframe,
                portfolio=portfolio_dominion2,
                is_live=is_live,
                place_order_fn=place_order_fn,
            )

        # BOT 1: 3-Step Domination Bot / Bot 1 V4 Engine / Dual Bot Fleet
        
        # BOT 6: Market Maker
        if active_strategy_bot in ("market_maker", "bot6_market_maker", "both", "dual_fleet", "all"):
            await self._eval_market_maker(
                ticker=ticker,
                book=book,
                market_info=market_info,
                timeframe=timeframe,
                portfolio=portfolio_market_maker,
                place_order_fn=place_order_fn,
            )

        if active_strategy_bot in ("3_step_domination_bot", "domination_bot", "domination", "bot1_v4_domination", "bot1_v4", "both", "dual", "all", "dual_domination", "dual_fleet"):
            await self._eval_domination(
                ticker=ticker,
                book=book,
                market_info=market_info,
                trades=trades,
                timeframe=timeframe,
                portfolio=portfolio_domination,
                is_live=is_live,
                place_order_fn=place_order_fn,
                active_bot_type=active_strategy_bot,
            )

        # BOT: The ONNX Strategy (Dual-Brain Spot Lead vs Kalshi Lag CLOB)
        if active_strategy_bot in (
            "dual_onnx",
            "the_onnx_strategy",
            "onnx_macro_v2",
            "dual_onnx_bot",
            "dual_onnx_arbitrage",
            "dual_onnx_arbitrage_bot",
        ):
            await self._eval_dual_onnx(
                ticker=ticker,
                book=book,
                market_info=market_info,
                trades=trades,
                timeframe=timeframe,
                portfolio=portfolio_dual_onnx,
                place_order_fn=place_order_fn,
            )

        # BOT 2: ONNX Microstructure Neural Net Bot
        if active_strategy_bot in ("onnx_microstructure_bot", "onnx_bot"):
            await self._eval_onnx_microstructure(
                ticker=ticker,
                book=book,
                trades=trades,
                timeframe=timeframe,
                portfolio=portfolio_onnx,
                place_order_fn=place_order_fn,
            )

    async def _eval_macro_trend(
        self,
        ticker: str,
        book: L2BookState,
        market_info: Optional[MarketInfo],
        trades: list[TradeEvent],
        timeframe: Timeframe,
        portfolio: Portfolio,
        active_strategy_bot: str,
        is_live: bool,
        place_order_fn: Callable[..., Any],
    ) -> None:
        if (
            not portfolio.circuit_breaker_tripped
            and len(portfolio.open_positions) < MAX_CONCURRENT_POSITIONS
            and portfolio.get_position(ticker) is None
        ):
            _m_now = time.monotonic()
            if _m_now - self._last_macro_eval_time.get(ticker, 0.0) >= 3.0:
                self._last_macro_eval_time[ticker] = _m_now
                try:
                    target_strike = float(market_info.target_strike if market_info else 78650.0)
                    if self._spot_price_getter:
                        try:
                            spot_price = float(self._spot_price_getter())
                        except Exception:
                            spot_price = target_strike
                    else:
                        spot_price = float(market_info.target_strike if market_info else 78650.0)
                    time_to_expiry_s = 600.0

                    if market_info and market_info.expiration_time:
                        now_utc = datetime.now(timezone.utc)
                        rem_secs = (market_info.expiration_time - now_utc).total_seconds()
                        if rem_secs <= 15.0:
                            return
                        time_to_expiry_s = rem_secs

                    vpin_score = 0.15
                    onnx_res = None
                    try:
                        btc_book, btc_trades = self._btc_orderflow_feed.get_btc_l2_state()
                        onnx_res = await asyncio.to_thread(
                            self._onnx_engine.process_orderbook_tick, btc_book, btc_trades
                        )
                        vpin_score = float(onnx_res.get("vpin_score", 0.15))
                    except Exception as exc:
                        logger.debug("[BTC ONNX] Inference fallback: %s", exc)
                        try:
                            vpin_score = float(self._onnx_engine.extractor.compute_vpin())
                        except Exception:
                            pass

                    macro_dec = self._macro_trend_bot.evaluate(
                        book=book,
                        spot_price=spot_price,
                        target_strike=target_strike,
                        time_to_expiry_s=time_to_expiry_s,
                        recent_trades=trades,
                        total_equity=portfolio.equity,
                        max_position_size=1,
                        estimated_vpin=vpin_score,
                        onnx_result=onnx_res,
                    )

                    if macro_dec.recommended_side in ("yes", "no") and macro_dec.recommended_contracts > 0:
                        m_side = OrderSide.YES if macro_dec.recommended_side == "yes" else OrderSide.NO
                        is_macro_onnx = active_strategy_bot in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion")
                        bot_label = "LIVE MACRO ONNX" if (is_live and is_macro_onnx) else ("LIVE MACRO TREND" if is_live else ("MACRO ONNX BOT" if is_macro_onnx else "MACRO TREND DOMINION"))
                        bot_tag = "macro_onnx" if is_macro_onnx else "macro_trend_dominion"
                        logger.info(
                            "[%s] %-18s | %-3s (%s) | ONNX BTC: %s(%.1f%%) [L:%.2f S:%.2f] | Regime: %s (1h: %+.2f%%) | Edge=%+.1f%% | EV=+%s/ct | Size=%d ct",
                            bot_label,
                            ticker,
                            macro_dec.recommended_side.upper(),
                            macro_dec.active_playbook,
                            macro_dec.onnx_signal,
                            macro_dec.onnx_confidence * 100.0,
                            macro_dec.onnx_prob_long,
                            macro_dec.onnx_prob_short,
                            macro_dec.macro_regime,
                            macro_dec.trend_1h_pct,
                            macro_dec.edge_pct,
                            f"${max(macro_dec.ev_yes, macro_dec.ev_no):.2f}",
                            1,
                        )
                        lim_p = Decimal(str(getattr(macro_dec, "limit_price", "0.52") or "0.52"))
                        await place_order_fn(
                            book=book,
                            ticker=ticker,
                            side=m_side,
                            max_size=1,
                            timeframe=timeframe,
                            reasoning=macro_dec.rationale,
                            portfolio=portfolio,
                            bot_type=bot_tag,
                            order_type="limit",
                            limit_price=lim_p,
                        )
                except Exception as exc:
                    logger.debug("Macro ONNX / Trend bot evaluation error: %s", exc)

    async def _eval_dominion2(
        self,
        ticker: str,
        book: L2BookState,
        market_info: Optional[MarketInfo],
        trades: list[TradeEvent],
        timeframe: Timeframe,
        portfolio: Portfolio,
        is_live: bool,
        place_order_fn: Callable[..., Any],
    ) -> None:
        if (
            not portfolio.circuit_breaker_tripped
            and len(portfolio.open_positions) < MAX_CONCURRENT_POSITIONS
            and portfolio.get_position(ticker) is None
        ):
            try:
                target_strike = float(market_info.target_strike if market_info else 78650.0)
                if self._spot_price_getter:
                    try:
                        spot_price = float(self._spot_price_getter())
                    except Exception:
                        spot_price = target_strike
                else:
                    spot_price = float(market_info.target_strike if market_info else 78650.0)
                time_to_expiry_s = 600.0

                if market_info and market_info.expiration_time:
                    now_utc = datetime.now(timezone.utc)
                    rem_secs = (market_info.expiration_time - now_utc).total_seconds()
                    if rem_secs <= 15.0:
                        return
                    time_to_expiry_s = rem_secs

                vpin_score = 0.15
                try:
                    vpin_score = float(self._onnx_engine.extractor.compute_vpin())
                except Exception:
                    pass

                decision2 = self._dominion2_bot.evaluate(
                    book=book,
                    spot_price=spot_price,
                    target_strike=target_strike,
                    time_to_expiry_s=time_to_expiry_s,
                    recent_trades=trades,
                    total_equity=portfolio.equity,
                    max_position_size=1,
                    estimated_vpin=vpin_score,
                )

                if decision2.recommended_side in ("yes", "no") and decision2.recommended_contracts > 0:
                    side_enum = OrderSide.YES if decision2.recommended_side == "yes" else OrderSide.NO
                    logger.info(
                        "[%s] %-18s | %-3s (%s) | Edge=%+.1f%% | EV=+%s/ct | Size=%d cts",
                        "LIVE DOMINION 2" if is_live else "DOMINION 2",
                        ticker,
                        decision2.recommended_side.upper(),
                        decision2.active_playbook,
                        decision2.edge_pct * 100.0,
                        f"${max(decision2.ev_yes, decision2.ev_no):.2f}",
                        decision2.recommended_contracts,
                    )
                    await place_order_fn(
                        book=book,
                        ticker=ticker,
                        side=side_enum,
                        max_size=decision2.recommended_contracts,
                        timeframe=timeframe,
                        reasoning=decision2.rationale,
                        portfolio=portfolio,
                        bot_type="dominion_2_bot",
                    )
            except Exception as exc:
                logger.debug("Dominion 2 bot evaluation error: %s", exc)

    async def _eval_domination(
        self,
        ticker: str,
        book: L2BookState,
        market_info: Optional[MarketInfo],
        trades: list[TradeEvent],
        timeframe: Timeframe,
        portfolio: Portfolio,
        is_live: bool,
        place_order_fn: Callable[..., Any],
        active_bot_type: str = "3_step_domination_bot",
    ) -> None:
        pos = portfolio.get_position(ticker)
        if pos is not None:
            await self._eval_domination_exit(
                ticker=ticker,
                pos=pos,
                book=book,
                market_info=market_info,
                trades=trades,
                timeframe=timeframe,
                portfolio=portfolio,
                is_live=is_live,
                place_order_fn=place_order_fn,
                active_bot_type=active_bot_type,
            )
            return

        if (
            not portfolio.circuit_breaker_tripped
            and len(portfolio.open_positions) < MAX_CONCURRENT_POSITIONS
        ):
            _eval_now = time.monotonic()
            if _eval_now - self._last_dom_eval_time.get(ticker, 0.0) < 3.0:
                return
            self._last_dom_eval_time[ticker] = _eval_now
            try:
                target_strike = float(market_info.target_strike if market_info else 78650.0)
                if self._spot_price_getter:
                    try:
                        spot_price = float(self._spot_price_getter())
                    except Exception:
                        spot_price = target_strike
                else:
                    spot_price = float(market_info.target_strike if market_info else 78650.0)
                time_to_expiry_s = 600.0

                if market_info and market_info.expiration_time:
                    now_utc = datetime.now(timezone.utc)
                    rem_secs = (market_info.expiration_time - now_utc).total_seconds()
                    if rem_secs <= 15.0:
                        return
                    time_to_expiry_s = rem_secs

                vpin_score = 0.15
                try:
                    vpin_score = float(self._onnx_engine.extractor.compute_vpin())
                except Exception:
                    pass

                is_dual = active_bot_type in ("both", "dual", "all", "dual_domination", "dual_fleet")
                engines_to_eval = []
                if is_dual:
                    engines_to_eval = [
                        (self._domination_bot, "3_step_domination_bot", False),
                        (self._bot1_v4_engine, "bot1_v4_domination", True),
                    ]
                elif active_bot_type in ("bot1_v4_domination", "bot1_v4") and self._bot1_v4_engine is not None:
                    engines_to_eval = [(self._bot1_v4_engine, "bot1_v4_domination", True)]
                else:
                    engines_to_eval = [(self._domination_bot, "3_step_domination_bot", False)]

                for bot_engine, bot_type_tag, is_v4 in engines_to_eval:
                    if bot_engine is None:
                        continue
                    decision = bot_engine.evaluate(
                        book=book,
                        spot_price=spot_price,
                        target_strike=target_strike,
                        time_to_expiry_s=time_to_expiry_s,
                        recent_trades=trades,
                        total_equity=portfolio.equity,
                        max_position_size=4,
                        estimated_vpin=vpin_score,
                        cycle_id=ticker,
                    )

                    now_mono = time.monotonic()
                    if now_mono - self._last_pred_log_time.get(f"{ticker}_{bot_type_tag}", 0.0) >= 3.0:
                        self._last_pred_log_time[f"{ticker}_{bot_type_tag}"] = now_mono
                        self._db_writer.enqueue_ai_prediction(
                            ticker=ticker,
                            p_up=decision.p_up,
                            p_down=decision.p_down,
                            p_wait=decision.p_wait,
                            vpin=decision.vpin,
                            ev_yes=decision.ev_yes,
                            ev_no=decision.ev_no,
                            recommended_side=decision.recommended_side,
                            rationale=f"[{bot_type_tag}] {decision.rationale}",
                        )

                    if decision.recommended_side in ("yes", "no") and decision.recommended_contracts > 0:
                        order_size = max(1, min(4, int(getattr(decision, "recommended_contracts", 1))))
                        side_enum = OrderSide.YES if decision.recommended_side == "yes" else OrderSide.NO
                        bot_label = ("LIVE BOT 1 V4" if is_v4 else "LIVE 3-STEP BOT") if is_live else ("BOT 1 V4" if is_v4 else "3-STEP BOT")
                        logger.info(
                            "[%s] %-18s | %-3s (%s) | Edge=%+.1f%% | EV=+%s/ct | Size=%d cts",
                            bot_label,
                            ticker,
                            decision.recommended_side.upper(),
                            decision.active_playbook,
                            decision.edge_pct,
                            f"${max(decision.ev_yes, decision.ev_no):.2f}",
                            order_size,
                        )
                        order_type_val = getattr(decision, "order_type", "limit")
                        base_discount = getattr(bot_engine, "discount_limit_price", Decimal("0.52"))
                        limit_price_val = Decimal(str(getattr(decision, "limit_price", base_discount)))
                        await place_order_fn(
                            book=book,
                            ticker=ticker,
                            side=side_enum,
                            max_size=order_size,
                            timeframe=timeframe,
                            reasoning=decision.rationale,
                            portfolio=portfolio,
                            bot_type=bot_type_tag,
                            order_type=order_type_val,
                            limit_price=limit_price_val,
                        )
                    else:
                        if not hasattr(self, "_last_eval_heartbeat_time"):
                            self._last_eval_heartbeat_time = {}
                        if now_mono - self._last_eval_heartbeat_time.get(f"{ticker}_{bot_type_tag}", 0.0) >= 15.0:
                            self._last_eval_heartbeat_time[f"{ticker}_{bot_type_tag}"] = now_mono
                            bot_label = ("LIVE BOT 1 V4" if is_v4 else "LIVE 3-STEP BOT") if is_live else ("BOT 1 V4" if is_v4 else "3-STEP BOT")
                            diff = spot_price - target_strike
                            logger.info(
                                "[%s EVAL] %-18s | Spot: $%.2f | Strike: $%.2f (Diff: %+.2f) | Signal: %s (%s) | Edge: %+.1f%%",
                                bot_label,
                                ticker,
                                spot_price,
                                target_strike,
                                diff,
                                decision.recommended_side.upper(),
                                getattr(decision, "active_playbook", "observation"),
                                getattr(decision, "edge_pct", 0.0),
                            )
            except Exception as exc:
                logger.debug("Domination bot evaluation error: %s", exc)

    async def _eval_domination_exit(
        self,
        ticker: str,
        pos: Any,
        book: L2BookState,
        market_info: Optional[MarketInfo],
        trades: list[TradeEvent],
        timeframe: Timeframe,
        portfolio: Portfolio,
        is_live: bool,
        place_order_fn: Callable[..., Any],
        active_bot_type: str = "3_step_domination_bot",
    ) -> None:
        """Evaluate open position against 50%-75% take-profit scalping and quantitative exit rules."""
        _eval_now = time.monotonic()
        if _eval_now - self._last_dom_exit_eval_time.get(ticker, 0.0) < 1.0:
            return
        self._last_dom_exit_eval_time[ticker] = _eval_now

        try:
            target_strike = float(market_info.target_strike if market_info else 78650.0)
            if self._spot_price_getter:
                try:
                    spot_price = float(self._spot_price_getter())
                except Exception:
                    spot_price = target_strike
            else:
                spot_price = float(market_info.target_strike if market_info else 78650.0)

            time_to_expiry_s = 600.0
            if market_info and market_info.expiration_time:
                now_utc = datetime.now(timezone.utc)
                rem_secs = (market_info.expiration_time - now_utc).total_seconds()
                time_to_expiry_s = max(0.0, rem_secs)

            vpin_score = 0.15
            try:
                vpin_score = float(self._onnx_engine.extractor.compute_vpin())
            except Exception:
                pass

            # Track rolling spot price history to compute spot velocity over 3s
            if ticker not in self._spot_price_history:
                self._spot_price_history[ticker] = []
            hist = self._spot_price_history[ticker]
            hist.append((_eval_now, spot_price))
            hist = [item for item in hist if _eval_now - item[0] <= 10.0]
            self._spot_price_history[ticker] = hist

            spot_velocity_3s = 0.0
            if len(hist) >= 2:
                oldest_in_window = hist[0]
                dt = _eval_now - oldest_in_window[0]
                if dt >= 0.5:
                    spot_velocity_3s = (spot_price - oldest_in_window[1]) / dt * 3.0

            # Retrieve active strategy engine for exit evaluation
            bot_engine = getattr(self, "_bot1_v4_engine", None) or self._domination_bot
            exit_eval = getattr(bot_engine, "exit_evaluator", None) or getattr(bot_engine, "_exit_evaluator", None)

            if exit_eval:
                exit_decision = exit_eval.evaluate_exit(
                    position=pos,
                    side=pos.side,
                    entry_price=pos.entry_price,
                    size=pos.size,
                    book=book,
                    spot_price=spot_price,
                    target_strike=target_strike,
                    time_to_expiry_s=time_to_expiry_s,
                    vpin=vpin_score,
                    spot_velocity_3s=spot_velocity_3s,
                )

                if exit_decision and exit_decision.should_exit:
                    exit_price = Decimal(str(exit_decision.exit_price or "0.75"))
                    logger.info(
                        "🎯 [%s SCALP EXIT TRIGGERED] %-18s | Action: SELL %s 1 ct @ $%s | Reason: %s | Profit: %+.1f%% (%s)",
                        "LIVE BOT 1 V4" if is_live else "BOT 1 V4",
                        ticker,
                        pos.side.value.upper() if hasattr(pos.side, "value") else str(pos.side).upper(),
                        exit_price,
                        exit_decision.exit_reason,
                        exit_decision.profit_pct,
                        exit_decision.rationale,
                    )

                    # In paper/simulated mode, execute immediate position close on portfolio
                    if not is_live:
                        res = portfolio.close_position(ticker, exit_price)
                        if res:
                            self._db_writer.enqueue_settlement_record(
                                settlement_id=f"SCALP_{ticker}_{int(time.time())}",
                                ticker=ticker,
                                side=res.side.value if hasattr(res.side, "value") else str(res.side),
                                count=res.size,
                                price=float(res.settlement_price),
                                final_pnl=float(res.pnl),
                                outcome=res.outcome,
                                ending_equity=float(portfolio.equity),
                                bot_type="bot1_v4_domination",
                                execution_mode="simulated",
                            )
                            if hasattr(bot_engine, "record_completed_turnover"):
                                bot_engine.record_completed_turnover(ticker)
                    else:
                        # In Live Mode: place sell order on Kalshi live REST API
                        await place_order_fn(
                            book=book,
                            ticker=ticker,
                            side=pos.side,
                            max_size=pos.size,
                            timeframe=timeframe,
                            reasoning=f"Scalp Take-Profit Exit: {exit_decision.exit_reason} ({exit_decision.rationale})",
                            portfolio=portfolio,
                            bot_type="bot1_v4_domination",
                            order_type="limit",
                            limit_price=exit_price,
                            action="sell",
                        )
                        if hasattr(bot_engine, "record_completed_turnover"):
                            bot_engine.record_completed_turnover(ticker)
        except Exception as exc:
            logger.debug("Domination bot exit evaluation error: %s", exc)

    async def _eval_dual_onnx(
        self,
        ticker: str,
        book: L2BookState,
        market_info: Optional[MarketInfo],
        trades: list[TradeEvent],
        timeframe: Timeframe,
        portfolio: Portfolio,
        place_order_fn: Callable[..., Any],
    ) -> None:
        if (
            not portfolio.circuit_breaker_tripped
            and len(portfolio.open_positions) < MAX_CONCURRENT_POSITIONS
            and portfolio.get_position(ticker) is None
            and not (hasattr(self._simulator, "_resting_orders") and self._simulator._resting_orders.get(ticker))
            and ticker not in self._guardrails._cycle_locks
        ):
            _d_now = time.monotonic()
            if _d_now - self._last_dual_onnx_eval_time.get(ticker, 0.0) >= 1.0:
                self._last_dual_onnx_eval_time[ticker] = _d_now
                try:
                    target_strike = float(market_info.target_strike if market_info else 78650.0)
                    if self._spot_price_getter:
                        try:
                            spot_price = float(self._spot_price_getter())
                        except Exception:
                            spot_price = target_strike
                    else:
                        spot_price = float(market_info.target_strike if market_info else 78650.0)
                    time_to_expiry_s = 600.0

                    if market_info and market_info.expiration_time:
                        now_utc = datetime.now(timezone.utc)
                        rem_secs = (market_info.expiration_time - now_utc).total_seconds()
                        if rem_secs <= 15.0:
                            return
                        time_to_expiry_s = rem_secs

                    btc_book, btc_trades = None, None
                    try:
                        if hasattr(self, "_btc_orderflow_feed") and self._btc_orderflow_feed:
                            btc_book, btc_trades = self._btc_orderflow_feed.get_btc_l2_state()
                            if not getattr(self._dual_onnx_bot, "candle_builder", None):
                                self._dual_onnx_bot.candle_builder = getattr(self._btc_orderflow_feed, "candle_builder_1m", None) or getattr(self._btc_orderflow_feed, "candle_builder_5m", None)
                    except Exception:
                        pass

                    spot_diff = float(spot_price - target_strike)
                    l2_book = book.get_state() if hasattr(book, "get_state") else book
                    dec_dual = self._dual_onnx_bot.evaluate(
                        spot_l2=btc_book if btc_book is not None else l2_book,
                        kalshi_l2=l2_book,
                        time_to_expiry_s=time_to_expiry_s,
                        spot_diff=spot_diff,
                        latest_spot_trades=btc_trades if btc_trades is not None else trades,
                        latest_kalshi_trades=trades,
                    )

                    if dec_dual.side in ("yes", "no") and dec_dual.recommended_contracts > 0:
                        side_enum = OrderSide.YES if dec_dual.side == "yes" else OrderSide.NO
                        order_size = 1
                        limit_price_val = Decimal(str(round(dec_dual.recommended_limit_price, 2)))
                        logger.info(
                            "[SHADOW PAPER ONNX STRATEGY] %-18s | %-3s (%s) | EV=+$%s | Size=%d ct @ $%s | Rationale=%s",
                            ticker,
                            dec_dual.side.upper(),
                            dec_dual.regime.value if hasattr(dec_dual.regime, "value") else str(dec_dual.regime),
                            f"{float(dec_dual.expected_value):.2f}",
                            order_size,
                            f"{float(limit_price_val):.2f}",
                            dec_dual.rationale,
                        )
                        await place_order_fn(
                            book=book,
                            ticker=ticker,
                            side=side_enum,
                            max_size=order_size,
                            timeframe=timeframe,
                            reasoning=dec_dual.rationale,
                            portfolio=portfolio,
                            bot_type="onnx_macro_v2",
                            order_type="limit",
                            limit_price=limit_price_val,
                        )
                except Exception as exc:
                    logger.warning("Dual ONNX bot evaluation error on %s: %s", ticker, exc)

    async def _eval_onnx_microstructure(
        self,
        ticker: str,
        book: L2BookState,
        trades: list[TradeEvent],
        timeframe: Timeframe,
        portfolio: Portfolio,
        place_order_fn: Callable[..., Any],
    ) -> None:
        now_ts = time.time()
        if (
            now_ts - self._last_onnx_ts.get(ticker, 0.0) >= 0.5
            and not portfolio.circuit_breaker_tripped
            and len(portfolio.open_positions) < MAX_CONCURRENT_POSITIONS
            and portfolio.get_position(ticker) is None
        ):
            self._last_onnx_ts[ticker] = now_ts
            try:
                t0 = time.perf_counter()
                onnx_res = await asyncio.to_thread(
                    self._onnx_engine.process_orderbook_tick, book, trades
                )
                latency_ms = (time.perf_counter() - t0) * 1000.0

                onnx_signal = onnx_res.get("signal", "WAIT")
                onnx_conf = onnx_res.get("confidence", 0.0)
                vpin_score = onnx_res.get("vpin_score", 0.0)

                self._eval_count += 1
                if onnx_signal in ("LONG", "SHORT") or self._eval_count % 10 == 0:
                    logger.info(
                        "[ONNX AI]   %-18s | Signal=%-5s (%4.1f%%) | VPIN=%.2f | OFI_L1=%+.2f | Latency=%.2fms",
                        ticker, onnx_signal, onnx_conf * 100.0, vpin_score, onnx_res.get("ofi_l1", 0.0), latency_ms
                    )

                if not onnx_res.get("vpin_veto"):
                    rel_long = onnx_res.get("rel_long", onnx_res.get("prob_long", 0.33))
                    rel_short = onnx_res.get("rel_short", onnx_res.get("prob_short", 0.33))
                    prob_wait = onnx_res.get("prob_wait", 0.34)

                    if onnx_signal == "LONG":
                        prob_long = max(0.55, rel_long)
                        prob_short = 1.0 - prob_long
                        prob_wait_in = 0.0
                    elif onnx_signal == "SHORT":
                        prob_short = max(0.55, rel_short)
                        prob_long = 1.0 - prob_short
                        prob_wait_in = 0.0
                    else:
                        prob_long = rel_long
                        prob_short = rel_short
                        prob_wait_in = prob_wait

                    best_yes_ask = book.best_yes_ask
                    best_yes_bid = book.best_yes_bid
                    best_no_ask = (Decimal("1.00") - best_yes_bid) if best_yes_bid is not None else None

                    ev_result = self._ev_engine.compute_optimal_execution(
                        prob_up=prob_long,
                        prob_down=prob_short,
                        best_yes_ask=best_yes_ask,
                        best_no_ask=best_no_ask,
                        total_equity=portfolio.equity,
                        max_position_size=1,
                        vpin=vpin_score,
                        prob_wait=prob_wait_in,
                    )

                    now_mono = time.monotonic()
                    if ev_result.recommended_side is not None or now_mono - self._last_pred_log_time.get(ticker, 0.0) >= 3.0:
                        self._last_pred_log_time[ticker] = now_mono
                        self._db_writer.enqueue_ai_prediction(
                            ticker=ticker,
                            p_up=prob_long,
                            p_down=prob_short,
                            p_wait=prob_wait,
                            vpin=vpin_score,
                            ev_yes=float(ev_result.expected_value if ev_result.recommended_side == OrderSide.YES else 0.0),
                            ev_no=float(ev_result.expected_value if ev_result.recommended_side == OrderSide.NO else 0.0),
                            recommended_side=ev_result.recommended_side.value if ev_result.recommended_side else "none",
                            rationale=ev_result.rationale,
                        )

                    if ev_result.has_positive_edge and ev_result.recommended_side is not None:
                        logger.info(
                            "[STAGE 2 EV] %-18s | %-3s @ $%-4s | AI_P=%.1f%% | EV=+%s/ct | Edge=%+.1f%% | Kelly=%.1f%% (%d cts)",
                            ticker,
                            ev_result.recommended_side.value.upper(),
                            ev_result.market_price,
                            ev_result.ai_prob * 100.0,
                            f"${ev_result.expected_value:.3f}",
                            ev_result.statistical_edge * 100.0,
                            ev_result.kelly_fraction * 100.0,
                            ev_result.recommended_contracts,
                        )
                        await place_order_fn(
                            book=book,
                            ticker=ticker,
                            side=ev_result.recommended_side,
                            max_size=ev_result.recommended_contracts,
                            timeframe=timeframe,
                            reasoning=ev_result.rationale,
                            portfolio=portfolio,
                            bot_type="onnx_microstructure_bot",
                        )
            except Exception as exc:
                logger.debug("ONNX bot evaluation error: %s", exc)


    async def _eval_market_maker(
        self,
        ticker: str,
        book: L2BookState,
        market_info: Optional[MarketInfo],
        timeframe: Timeframe,
        portfolio: Portfolio,
        place_order_fn: Callable[..., Any],
    ) -> None:
        if portfolio.circuit_breaker_tripped:
            return
            
        y_bid = float(book.best_yes_bid) if book.best_yes_bid is not None else None
        y_ask = float(book.best_yes_ask) if book.best_yes_ask is not None else None
        if y_bid is None or y_ask is None:
            return

        intents = self._market_maker_engine.evaluate(
            ticker=ticker,
            yes_bid=y_bid,
            yes_ask=y_ask,
            min_spread_cents=1,
            max_inventory=3,
        )
        
        for intent in intents:
            await place_order_fn(
                book=book,
                ticker=ticker,
                side=intent["side"],
                max_size=1,
                timeframe=timeframe,
                reasoning=intent["reasoning"],
                portfolio=portfolio,
                bot_type="market_maker",
                order_type="limit",
                limit_price=intent["price"],
            )
