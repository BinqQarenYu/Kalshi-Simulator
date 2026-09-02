"""Asynchronous AI Background Worker for Decoupled Microstructure Inference.

Runs 28-D feature extraction, ONNX neural net inference, and Statistical EV & Kelly
sizing on an isolated background interval (e.g. 250ms), caching results in memory.
This completely removes all mathematical and inference latency from the high-frequency
market data and WebSocket broadcast loops. Integrates AgentTokenManager for token/credit optimization.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from kalshi_sim.agent_token_manager import get_agent_token_manager
from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.schemas import OrderSide

logger = logging.getLogger("kalshi_sim.ai_worker")


class AIWorker:
    """Decoupled background worker executing quantitative microstructure AI pipelines."""

    def __init__(
        self,
        orderbook_manager: OrderBookManager,
        sim_agent: Any = None,
        refresh_interval_s: float = 0.25,
    ) -> None:
        self._orderbook = orderbook_manager
        self._sim_agent = sim_agent
        self._refresh_interval_s = refresh_interval_s
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._last_compute_duration_ms: float = 0.0
        self.active_strategy_bot: str = "3_step_domination_bot"  # Default to 3-step domination bot
        self._domination_bot = ThreeStepDominationBot()
        self._token_manager = get_agent_token_manager()

        # Thread-safe in-memory cached AI signals
        self._cached_signals: dict[str, Any] = {
            "strategy_id": "3_step_domination_bot",
            "strategy_name": "3-Step Domination Bot",
            "active_playbook": "Playbook 3: Late-Cycle Gamma Snub",
            "playbook_stage": "gamma_snub",
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
            "rationale": "3-Step Domination Bot initialized and scanning cycle windows.",
            "compute_latency_ms": 0.0,
        }

    def set_sim_agent(self, sim_agent: Any) -> None:
        """Update reference to the simulation execution agent."""
        self._sim_agent = sim_agent

    def set_active_strategy(self, strategy_id: str) -> None:
        """Switch active strategy bot ('3_step_domination_bot' or 'onnx_microstructure_bot')."""
        if strategy_id in ("3_step_domination_bot", "onnx_microstructure_bot"):
            self.active_strategy_bot = strategy_id
            logger.info("AIWorker active strategy bot switched to: %s", strategy_id)

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
        """Isolated async loop executing quantitative bot strategy evaluation with token/credit governance."""
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

                        # Check adaptive market delta gating to prevent redundant evaluations
                        should_eval, eval_reason = self._token_manager.should_evaluate_market_state(
                            ticker=ticker,
                            spot_price=spot_price,
                            target_strike=target_strike,
                            time_to_expiry_s=time_to_expiry_s,
                        )

                        # Context dictionary for SHA256 context deduplication
                        raw_context = {
                            "ticker": ticker,
                            "spot_price": round(spot_price, 1),
                            "target_strike": round(target_strike, 1),
                            "best_yes_ask": round(best_yes_ask, 2),
                            "best_no_ask": round(best_no_ask, 2),
                            "strategy": self.active_strategy_bot,
                        }
                        compressed_context = self._token_manager.compress_context(raw_context)

                        # 1. Check SHA256 context cache first
                        cached_hit = self._token_manager.get_cached_response(compressed_context)
                        if cached_hit:
                            # Re-use cached signals with zero token/credit cost
                            self._cached_signals = cached_hit["data"]
                            self._cached_signals["compute_latency_ms"] = round((asyncio.get_event_loop().time() - start_t) * 1000.0, 2)
                        elif should_eval:
                            trades = self._sim_agent._recent_trades.get(ticker, []) if hasattr(self._sim_agent, "_recent_trades") else []
                            equity = self._sim_agent._portfolio.equity if (hasattr(self._sim_agent, "_portfolio") and self._sim_agent._portfolio) else Decimal("100.00")

                            # Determine model routing strategy
                            model_id = (
                                "3_step_domination_local"
                                if self.active_strategy_bot == "3_step_domination_bot"
                                else "onnx_microstructure_local"
                            )

                            # 1. Strategy: 3-Step Domination Bot
                            if self.active_strategy_bot == "3_step_domination_bot":
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
                                    max_position_size=10,
                                    estimated_vpin=vpin_val,
                                )

                                compute_duration = (asyncio.get_event_loop().time() - start_t) * 1000.0
                                self._last_compute_duration_ms = compute_duration

                                new_signals = {
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
                                    "compute_latency_ms": round(compute_duration, 2),
                                }
                                self._cached_signals = new_signals

                            # 2. Strategy: ONNX Microstructure Bot
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

                                new_signals = {
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
                                self._cached_signals = new_signals

                            # Record token usage & cache response
                            self._token_manager.record_usage(
                                agent_id="ai_worker",
                                model_id=model_id,
                                prompt_tokens=120,
                                completion_tokens=30,
                                is_cached=False,
                            )
                            self._token_manager.cache_response(
                                context_or_prompt=compressed_context,
                                response_data=self._cached_signals,
                                estimated_tokens=150,
                                model_id=model_id,
                                ttl_seconds=15.0,
                            )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("AI Worker iteration error: %s", exc)

            elapsed = asyncio.get_event_loop().time() - start_t
            sleep_time = max(0.01, self._refresh_interval_s - elapsed)
            await asyncio.sleep(sleep_time)
