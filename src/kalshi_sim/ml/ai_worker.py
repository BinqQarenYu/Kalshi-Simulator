"""Asynchronous AI Background Worker for Decoupled Microstructure Inference.

Runs 28-D feature extraction, ONNX neural net inference, and Statistical EV & Kelly
sizing on an isolated background interval (e.g. 250ms), caching results in memory.
This completely removes all mathematical and inference latency from the high-frequency
market data and WebSocket broadcast loops.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.ml.dominion_2_bot import Dominion2Bot
from kalshi_sim.ml.dual_onnx_schemas import DualONNXRegime
from kalshi_sim.ml.dual_onnx_strategy import DualONNXArbitrageBot
from kalshi_sim.ml.macro_trend_dominion import MacroTrendDominionBot
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.schemas import OrderSide

logger = logging.getLogger("kalshi_sim.ai_worker")


class AIWorker:
    """Decoupled background worker executing quantitative microstructure AI pipelines."""

    def __init__(
        self,
        orderbook_manager: OrderBookManager,
        sim_agent: Optional[Any] = None,
        compute_interval_seconds: float = 0.05,  # 20 Hz calculation loop
        hmm_brain: Optional[Any] = None,
        refresh_interval_s: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        self.orderbook_manager = orderbook_manager
        self._sim_agent = sim_agent
        self.compute_interval_seconds = refresh_interval_s if refresh_interval_s is not None else compute_interval_seconds
        self.hmm_brain = hmm_brain
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._last_compute_duration_ms: float = 0.0
        self.active_strategy_bot: str = "3_step_domination_bot"  # Default: 3-Step Domination Bot
        self._macro_trend_bot = MacroTrendDominionBot(
            strategy_id="macro_trend_dominion",
            strategy_name="Macro Trend Dominion",
            hmm_brain=self.hmm_brain,
        )
        self._domination_bot = ThreeStepDominationBot()
        self._dominion2_bot = Dominion2Bot()
        self._dual_onnx_bot = DualONNXArbitrageBot(hmm_brain=self.hmm_brain)

        # Thread-safe in-memory cached AI signals
        self._cached_signals: dict[str, Any] = {
            "strategy_id": "3_step_domination_bot",
            "strategy_name": "3-Step Domination Bot",
            "active_playbook": "Playbook 1: Early Momentum",
            "playbook_stage": "early_momentum",
            "p_up": 0.50,
            "p_down": 0.50,
            "p_wait": 0.00,
            "vpin": 0.15,
            "vpin_is_safe": True,
            "ev_yes": 0.00,
            "ev_no": 0.00,
            "edge_yes": 0.00,
            "edge_no": 0.00,
            "kelly_f_yes": 0.00,
            "kelly_f_no": 0.00,
            "recommended_side": "wait",
            "rationale": "3-Step Domination Bot (Playbook 1: Early Momentum, Playbook 2: Mid OFI Drift, Playbook 3: Gamma Snub) initialized.",
            "compute_latency_ms": 0.0,
        }

    def set_sim_agent(self, sim_agent: Any) -> None:
        """Update reference to the simulation execution agent."""
        self._sim_agent = sim_agent

    def set_active_strategy(self, strategy_id: str) -> None:
        """Switch active strategy bot ('dual_onnx', 'macro_onnx', 'macro_trend_dominion', '3_step_domination_bot', 'dominion_2_bot', or 'onnx_microstructure_bot')."""
        if strategy_id in ("dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot", "the_onnx_strategy", "onnx_macro_v2"):
            self.active_strategy_bot = "dual_onnx"
            logger.info("AIWorker active strategy bot switched to: %s", self.active_strategy_bot)
        elif strategy_id in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
            self.active_strategy_bot = "macro_onnx"
            logger.info("AIWorker active strategy bot switched to: %s", self.active_strategy_bot)
        elif strategy_id in ("macro_trend_dominion", "macro_trend", "macro_trend_dominion_bot"):
            self.active_strategy_bot = "macro_trend_dominion"
            logger.info("AIWorker active strategy bot switched to: %s", self.active_strategy_bot)
        elif strategy_id in ("dominion_2_bot", "3_step_domination_bot", "onnx_microstructure_bot", "dominion2", "dominion_v2"):
            # Normalize alias
            if strategy_id in ("dominion2", "dominion_v2"):
                strategy_id = "dominion_2_bot"
            self.active_strategy_bot = strategy_id
            logger.info("AIWorker active strategy bot switched to: %s", strategy_id)

    def set_domination_discount_price(self, price: Decimal | float | str) -> None:
        """Dynamically update the maker discount limit price ceiling on the domination bot."""
        if hasattr(self, "_domination_bot") and hasattr(self._domination_bot, "set_discount_limit_price"):
            self._domination_bot.set_discount_limit_price(price)

    def set_asset(self, asset: Any) -> None:
        """Update active asset on the domination bot."""
        if hasattr(self, "_domination_bot") and hasattr(self._domination_bot, "set_asset"):
            self._domination_bot.set_asset(asset)
        logger.info("AIWorker underlying asset updated to: %s", asset)

    def get_cached_signals(self) -> dict[str, Any]:
        """Return the latest cached AI state instantly with <0.001ms latency."""
        return self._cached_signals.copy()

    def start(
        self,
        active_ticker_supplier: Optional[Callable[[], str]] = None,
        market_context_supplier: Optional[Callable[[], dict[str, Any]]] = None,
    ) -> asyncio.Task[None]:
        """Start the background AI worker loop."""
        if self._running and self._task and not self._task.done():
            return self._task
        self._running = True
        self._task = asyncio.create_task(self._worker_loop(active_ticker_supplier, market_context_supplier))
        return self._task

    def stop(self) -> None:
        """Stop the background AI worker loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _worker_loop(
        self,
        active_ticker_supplier: Optional[Callable[[], str]] = None,
        market_context_supplier: Optional[Callable[[], dict[str, Any]]] = None,
    ) -> None:
        """Isolated async loop executing quantitative bot strategy evaluation."""
        logger.info("AI Worker loop started (refresh interval: %.2fs)", self._refresh_interval_s)
        while self._running:
            start_t = asyncio.get_event_loop().time()
            try:
                ticker = active_ticker_supplier() if active_ticker_supplier else "KXBTC15M"
                ctx = market_context_supplier() if market_context_supplier else {}
                spot_price = ctx.get("spot_price", 0.0)
                target_strike = ctx.get("target_strike", 0.0)
                time_to_expiry_s = ctx.get("time_to_expiry_s", 600.0)

                if self._sim_agent and self._orderbook and ticker:
                    book = self._orderbook.get_book(ticker)
                    if book and (book.yes_book or book.no_book):
                        best_yes_ask = float(book.best_yes_ask) if book.best_yes_ask else 0.51
                        best_no_ask = float(Decimal("1.0") - book.best_yes_bid) if book.best_yes_bid else 0.50
                        trades = self._sim_agent._recent_trades.get(ticker, []) if hasattr(self._sim_agent, "_recent_trades") else []
                        equity = self._sim_agent._portfolio.equity if (hasattr(self._sim_agent, "_portfolio") and self._sim_agent._portfolio) else Decimal("100.00")

                        # 0. Strategy: Dual-ONNX Contradiction Arbitrage
                        if self.active_strategy_bot in ("dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot", "the_onnx_strategy", "onnx_macro_v2"):
                            btc_book, btc_trades = None, None
                            try:
                                if hasattr(self._sim_agent, "_btc_orderflow_feed") and self._sim_agent._btc_orderflow_feed:
                                    btc_book, btc_trades = self._sim_agent._btc_orderflow_feed.get_btc_l2_state()
                            except Exception:
                                pass

                            spot_diff = float(spot_price - target_strike)
                            dec_dual = self._dual_onnx_bot.evaluate(
                                spot_l2=btc_book if btc_book is not None else book,
                                kalshi_l2=book,
                                time_to_expiry_s=time_to_expiry_s,
                                spot_diff=spot_diff,
                                latest_spot_trades=btc_trades if btc_trades is not None else trades,
                                latest_kalshi_trades=trades,
                            )
                            compute_duration = (asyncio.get_event_loop().time() - start_t) * 1000.0
                            self._last_compute_duration_ms = compute_duration

                            p_up_val = dec_dual.quolas_confidence if dec_dual.quolas_signal == "UP" else (1.0 - dec_dual.quolas_confidence if dec_dual.quolas_signal == "DOWN" else 0.50)
                            p_down_val = dec_dual.quolas_confidence if dec_dual.quolas_signal == "DOWN" else (1.0 - dec_dual.quolas_confidence if dec_dual.quolas_signal == "UP" else 0.50)

                            self._cached_signals = {
                                "strategy_id": "dual_onnx",
                                "strategy_name": "Dual-ONNX Contradiction Arbitrage",
                                "active_playbook": dec_dual.regime.value if hasattr(dec_dual.regime, "value") else str(dec_dual.regime),
                                "playbook_stage": "dual_onnx",
                                "regime": dec_dual.regime.value if hasattr(dec_dual.regime, "value") else str(dec_dual.regime),
                                "action": dec_dual.action,
                                "quolas_signal": dec_dual.quolas_signal,
                                "quolas_confidence": dec_dual.quolas_confidence,
                                "kalshi_signal": dec_dual.kalshi_signal,
                                "kalshi_confidence": dec_dual.kalshi_confidence,
                                "p_up": p_up_val,
                                "p_down": p_down_val,
                                "p_wait": 0.00 if dec_dual.quolas_signal != "WAIT" else 1.00,
                                "vpin": 0.15,
                                "vpin_is_safe": dec_dual.regime != DualONNXRegime.TOXIC_VETO,
                                "ev_yes": float(dec_dual.expected_value) if dec_dual.side == "yes" else 0.0,
                                "ev_no": float(dec_dual.expected_value) if dec_dual.side == "no" else 0.0,
                                "edge_yes": float(dec_dual.expected_value) if dec_dual.side == "yes" else 0.0,
                                "edge_no": float(dec_dual.expected_value) if dec_dual.side == "no" else 0.0,
                                "expected_value": float(dec_dual.expected_value),
                                "statistical_edge": float(dec_dual.expected_value),
                                "kelly_f_yes": 0.10 if dec_dual.side == "yes" else 0.0,
                                "kelly_f_no": 0.10 if dec_dual.side == "no" else 0.0,
                                "recommended_side": dec_dual.side or "wait",
                                "recommended_contracts": dec_dual.recommended_contracts,
                                "recommended_limit_price": float(dec_dual.recommended_limit_price),
                                "rationale": dec_dual.rationale,
                                "compute_latency_ms": round(compute_duration, 2),
                                "cross_brain_skew_ms": round(getattr(self._dual_onnx_bot, "last_temporal_skew_ms", 0.0), 2),
                                "is_temporally_synced": getattr(self._dual_onnx_bot, "is_temporally_synced", True),
                                "slower_brain": getattr(self._dual_onnx_bot, "slower_brain", "IN_SYNC"),
                            }

                        # 1. Strategy: Macro ONNX & Macro Trend Dominion
                        elif self.active_strategy_bot in (
                            "macro_onnx",
                            "macro_onnx_bot",
                            "macro_trend_onnx_fusion",
                            "macro_trend_dominion",
                            "macro_trend",
                            "macro_trend_dominion_bot",
                        ):
                            vpin_val = 0.15
                            onnx_res = None
                            try:
                                if hasattr(self._sim_agent, "_btc_orderflow_feed"):
                                    btc_book, btc_trades = self._sim_agent._btc_orderflow_feed.get_btc_l2_state()
                                    onnx_res = self._sim_agent._onnx_engine.process_orderbook_tick(btc_book, latest_trades=btc_trades)
                                else:
                                    onnx_res = self._sim_agent._onnx_engine.process_orderbook_tick(book, latest_trades=trades)
                                vpin_val = float(onnx_res.get("vpin_score", 0.15))
                            except Exception:
                                try:
                                    vpin_val = float(self._sim_agent._onnx_engine.extractor.compute_vpin())
                                except Exception:
                                    pass

                            m_dec = self._macro_trend_bot.evaluate(
                                book=book,
                                spot_price=spot_price,
                                target_strike=target_strike,
                                time_to_expiry_s=time_to_expiry_s,
                                recent_trades=trades,
                                total_equity=equity,
                                max_position_size=1,
                                estimated_vpin=vpin_val,
                                onnx_result=onnx_res,
                            )

                            compute_duration = (asyncio.get_event_loop().time() - start_t) * 1000.0
                            self._last_compute_duration_ms = compute_duration

                            self._cached_signals = {
                                "strategy_id": m_dec.strategy_id,
                                "strategy_name": m_dec.strategy_name,
                                "active_playbook": m_dec.active_playbook,
                                "playbook_stage": m_dec.playbook_stage,
                                "macro_regime": m_dec.macro_regime,
                                "trend_1h_pct": m_dec.trend_1h_pct,
                                "trend_15m_pct": m_dec.trend_15m_pct,
                                "p_up": m_dec.p_up,
                                "p_down": m_dec.p_down,
                                "p_wait": m_dec.p_wait,
                                "onnx_signal": m_dec.onnx_signal,
                                "onnx_confidence": m_dec.onnx_confidence,
                                "onnx_prob_long": m_dec.onnx_prob_long,
                                "onnx_prob_short": m_dec.onnx_prob_short,
                                "onnx_prob_wait": m_dec.onnx_prob_wait,
                                "vpin": m_dec.vpin,
                                "vpin_is_safe": m_dec.vpin_is_safe,
                                "ev_yes": m_dec.ev_yes,
                                "ev_no": m_dec.ev_no,
                                "edge_yes": m_dec.edge_yes,
                                "edge_no": m_dec.edge_no,
                                "kelly_f_yes": m_dec.kelly_f_yes,
                                "kelly_f_no": m_dec.kelly_f_no,
                                "recommended_side": m_dec.recommended_side,
                                "rationale": m_dec.rationale,
                                "compute_latency_ms": round(compute_duration, 2),
                            }

                        # 1. Strategy: Dominion 2 Bot (Anti-Pin Scalper)
                        elif self.active_strategy_bot == "dominion_2_bot":
                            vpin_val = 0.15
                            try:
                                vpin_val = float(self._sim_agent._onnx_engine.extractor.compute_vpin())
                            except Exception:
                                pass

                            dec2 = self._dominion2_bot.evaluate(
                                book=book,
                                spot_price=spot_price,
                                target_strike=target_strike,
                                time_to_expiry_s=time_to_expiry_s,
                                recent_trades=trades,
                                total_equity=equity,
                                max_position_size=4,
                                estimated_vpin=vpin_val,
                            )

                            compute_duration = (asyncio.get_event_loop().time() - start_t) * 1000.0
                            self._last_compute_duration_ms = compute_duration

                            self._cached_signals = {
                                "strategy_id": dec2.strategy_id,
                                "strategy_name": dec2.strategy_name,
                                "active_playbook": dec2.active_playbook,
                                "playbook_stage": dec2.playbook_stage,
                                "p_up": dec2.p_up,
                                "p_down": dec2.p_down,
                                "p_wait": dec2.p_wait,
                                "vpin": dec2.vpin,
                                "vpin_is_safe": dec2.vpin_is_safe,
                                "ev_yes": dec2.ev_yes,
                                "ev_no": dec2.ev_no,
                                "edge_yes": dec2.edge_yes,
                                "edge_no": dec2.edge_no,
                                "kelly_f_yes": dec2.kelly_f_yes,
                                "kelly_f_no": dec2.kelly_f_no,
                                "recommended_side": dec2.recommended_side,
                                "rationale": dec2.rationale,
                                "compute_latency_ms": round(compute_duration, 2),
                            }

                        # 2. Strategy: 3-Step Domination Bot
                        elif self.active_strategy_bot == "3_step_domination_bot":
                            # Extract VPIN from onnx_engine feature extractor if available
                            vpin_val = 0.15
                            try:
                                vpin_val = float(self._sim_agent._onnx_engine.extractor.compute_vpin())
                            except Exception:
                                pass

                            dec = self._domination_bot.evaluate(
                                book=book,
                                spot_price=spot_price,
                                target_strike=target_strike,
                                time_to_expiry_s=time_to_expiry_s,
                                recent_trades=trades,
                                total_equity=equity,
                                max_position_size=1,
                                estimated_vpin=vpin_val,
                            )

                            compute_duration = (asyncio.get_event_loop().time() - start_t) * 1000.0
                            self._last_compute_duration_ms = compute_duration

                            self._cached_signals = {
                                "strategy_id": dec.strategy_id,
                                "strategy_name": dec.strategy_name,
                                "active_playbook": dec.active_playbook,
                                "playbook_stage": dec.playbook_stage,
                                "p_up": dec.p_up,
                                "p_down": dec.p_down,
                                "p_wait": dec.p_wait,
                                "vpin": dec.vpin,
                                "vpin_is_safe": dec.vpin_is_safe,
                                "ev_yes": dec.ev_yes,
                                "ev_no": dec.ev_no,
                                "edge_yes": dec.edge_yes,
                                "edge_no": dec.edge_no,
                                "kelly_f_yes": dec.kelly_f_yes,
                                "kelly_f_no": dec.kelly_f_no,
                                "recommended_side": dec.recommended_side,
                                "rationale": dec.rationale,
                                "order_type": getattr(dec, "order_type", "limit"),
                                "limit_price": getattr(dec, "limit_price", 0.48),
                                "discount_limit_price": float(self._domination_bot.discount_limit_price),
                                "compute_latency_ms": round(compute_duration, 2),
                            }

                        # 3. Strategy: ONNX Microstructure Bot
                        else:
                            onnx_res = self._sim_agent._onnx_engine.process_orderbook_tick(book, latest_trades=trades)
                            prob_long = onnx_res.get("prob_long", 0.33)
                            prob_short = onnx_res.get("prob_short", 0.33)
                            prob_wait = onnx_res.get("prob_wait", 0.34)
                            vpin_score = onnx_res.get("vpin_score", 0.0)

                            ev_result = self._sim_agent._ev_engine.compute_optimal_execution(
                                prob_up=prob_long,
                                prob_down=prob_short,
                                best_yes_ask=Decimal(str(best_yes_ask)),
                                best_no_ask=Decimal(str(best_no_ask)),
                                total_equity=equity,
                                max_position_size=10,
                                vpin=vpin_score,
                                prob_wait=prob_wait,
                            )

                            compute_duration = (asyncio.get_event_loop().time() - start_t) * 1000.0
                            self._last_compute_duration_ms = compute_duration

                            self._cached_signals = {
                                "strategy_id": "onnx_microstructure_bot",
                                "strategy_name": "ONNX Microstructure Bot",
                                "active_playbook": "28-D Microstructure Neural Net",
                                "playbook_stage": "onnx",
                                "p_up": prob_long,
                                "p_down": prob_short,
                                "p_wait": prob_wait,
                                "vpin": vpin_score,
                                "vpin_is_safe": not onnx_res.get("vpin_veto", False),
                                "ev_yes": float(ev_result.expected_value if ev_result.recommended_side == OrderSide.YES else Decimal("0.0")),
                                "ev_no": float(ev_result.expected_value if ev_result.recommended_side == OrderSide.NO else Decimal("0.0")),
                                "edge_yes": float(ev_result.statistical_edge if ev_result.recommended_side == OrderSide.YES else 0.0),
                                "edge_no": float(ev_result.statistical_edge if ev_result.recommended_side == OrderSide.NO else 0.0),
                                "kelly_f_yes": float(ev_result.kelly_fraction if ev_result.recommended_side == OrderSide.YES else 0.0),
                                "kelly_f_no": float(ev_result.kelly_fraction if ev_result.recommended_side == OrderSide.NO else 0.0),
                                "recommended_side": ev_result.recommended_side.value if ev_result.recommended_side else "wait",
                                "rationale": ev_result.rationale,
                                "compute_latency_ms": round(compute_duration, 2),
                            }
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("AI Worker iteration error: %s", exc)

            elapsed = asyncio.get_event_loop().time() - start_t
            sleep_time = max(0.01, self._refresh_interval_s - elapsed)
            await asyncio.sleep(sleep_time)
