"""Asynchronous High-Throughput Database Storage Writer for Kalshi Simulator.

Uses an internal non-blocking asyncio.Queue with batch buffering and transaction-scoped
bulk inserts to persist streaming ticks, executed trades, contract settlements, equity snapshots,
AI predictions, and circuit breaker events without delaying real-time order matching loops.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import aiosqlite

from kalshi_sim.db.connection import DatabaseManager, get_db, get_eth_db

logger = logging.getLogger(__name__)


@dataclass
class QueuedRecord:
    """A database record awaiting batch persistence."""
    table: str
    data: Dict[str, Any]


class DatabaseWriter:
    """Non-blocking asynchronous database ingestion engine."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        batch_size: int = 50,
        flush_interval_seconds: float = 0.10,
        max_queue_size: int = 10000,
    ) -> None:
        self.db_manager = db_manager or get_db()
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds
        self.max_queue_size = max_queue_size
        self.queue: asyncio.Queue[QueuedRecord] = asyncio.Queue(maxsize=max_queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background queue consumption worker."""
        if self._running:
            return
        await self.db_manager.init_db()
        # Ensure queue is bound to currently running event loop
        try:
            self.queue = asyncio.Queue(maxsize=self.max_queue_size)
        except Exception:
            pass
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop(), name="db_writer_worker")
        logger.info("DatabaseWriter started background ingestion worker.")

    async def stop(self) -> None:
        """Gracefully stop the worker and flush all remaining queued records."""
        if not self._running:
            return
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        await self.flush()
        logger.info("DatabaseWriter stopped and flushed.")

    async def _worker_loop(self) -> None:
        """Continuous background loop consuming queue items and flushing in batches."""
        batch: List[QueuedRecord] = []
        last_flush = asyncio.get_running_loop().time()

        while self._running:
            try:
                # Wait for next record or timeout to trigger periodic flush
                timeout = max(0.01, self.flush_interval_seconds - (asyncio.get_running_loop().time() - last_flush))
                try:
                    record = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    batch.append(record)
                    self.queue.task_done()
                except asyncio.TimeoutError:
                    pass

                now = asyncio.get_running_loop().time()
                if len(batch) >= self.batch_size or (batch and (now - last_flush) >= self.flush_interval_seconds):
                    await self._persist_batch(batch)
                    batch.clear()
                    last_flush = now
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in DatabaseWriter worker loop: %s", exc, exc_info=True)
                await asyncio.sleep(0.05)

        # Final drain
        if batch:
            await self._persist_batch(batch)

    async def flush(self) -> None:
        """Drain and persist all currently queued records immediately."""
        batch: List[QueuedRecord] = []
        while not self.queue.empty():
            try:
                batch.append(self.queue.get_nowait())
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
        if batch:
            await self._persist_batch(batch)

    async def _persist_batch(self, batch: List[QueuedRecord]) -> None:
        """Execute grouped bulk inserts within a single database transaction."""
        if not batch:
            return

        # Group records by target table
        by_table: Dict[str, List[Dict[str, Any]]] = {}
        for item in batch:
            by_table.setdefault(item.table, []).append(item.data)

        async with self.db_manager.get_connection() as db:
            for table, records in by_table.items():
                if not records:
                    continue
                columns = list(records[0].keys())
                placeholders = ", ".join(["?"] * len(columns))
                sql = f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                param_rows = [[r[col] for col in columns] for r in records]
                await db.executemany(sql, param_rows)
            await db.commit()

    # -- Enqueue Helper Methods ----------------------------------------------

    def enqueue_tick(
        self,
        ticker: str,
        msg_type: str,
        best_bid: Optional[float] = None,
        best_ask: Optional[float] = None,
        mid_price: Optional[float] = None,
        spread: Optional[float] = None,
        volume: float = 0.0,
        payload_json: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Enqueue an L2 tick or trade event record."""
        ts = timestamp or datetime.now(timezone.utc)
        record = {
            "timestamp_utc": ts.isoformat(),
            "timestamp_epoch_ms": int(ts.timestamp() * 1000),
            "ticker": ticker,
            "msg_type": msg_type,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid_price": mid_price,
            "spread": spread,
            "volume": volume,
            "payload_json": payload_json,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="ticks", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped tick for %s", ticker)

    def enqueue_trade(
        self,
        trade_id: str,
        ticker: str,
        side: str,
        size: int,
        price: float,
        gross_value: float,
        fees: float = 0.0,
        vpin: Optional[float] = None,
        kelly_fraction: Optional[float] = None,
        bot_type: str = "3_step_domination_bot",
        execution_mode: str = "simulated",
        status: str = "filled",
        timeframe: str = "15m",
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Enqueue an executed order record."""
        ts = timestamp or datetime.now(timezone.utc)
        record = {
            "trade_id": trade_id,
            "timestamp_utc": ts.isoformat(),
            "timestamp_epoch_ms": int(ts.timestamp() * 1000),
            "ticker": ticker,
            "timeframe": timeframe,
            "side": side,
            "size": size,
            "price": price,
            "gross_value": gross_value,
            "fees": fees,
            "vpin": vpin,
            "kelly_fraction": kelly_fraction,
            "bot_type": bot_type,
            "execution_mode": execution_mode,
            "status": status,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="trades", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped trade %s", trade_id)

    def enqueue_settlement(
        self,
        settlement_id: str,
        ticker: str,
        side: str,
        size: int,
        entry_price: float,
        settlement_price: float,
        outcome: str,
        pnl: float,
        balance_after: float,
        bot_type: str = "3_step_domination_bot",
        execution_mode: str = "simulated",
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Enqueue a settled position outcome record."""
        ts = timestamp or datetime.now(timezone.utc)
        record = {
            "settlement_id": settlement_id,
            "timestamp_utc": ts.isoformat(),
            "timestamp_epoch_ms": int(ts.timestamp() * 1000),
            "ticker": ticker,
            "side": side,
            "size": size,
            "entry_price": entry_price,
            "settlement_price": settlement_price,
            "outcome": outcome,
            "pnl": pnl,
            "balance_after": balance_after,
            "bot_type": bot_type,
            "execution_mode": execution_mode,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="settlements", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped settlement %s", settlement_id)

    def enqueue_equity_snapshot(
        self,
        balance: float,
        equity: float,
        realized_pnl: float,
        unrealized_pnl: float,
        drawdown_pct: float = 0.0,
        win_rate: float = 0.0,
        total_trades: int = 0,
        open_positions_count: int = 0,
        bot_type: str = "all",
        execution_mode: str = "simulated",
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Enqueue a portfolio equity state snapshot."""
        ts = timestamp or datetime.now(timezone.utc)
        record = {
            "timestamp_utc": ts.isoformat(),
            "timestamp_epoch_ms": int(ts.timestamp() * 1000),
            "balance": balance,
            "equity": equity,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "drawdown_pct": drawdown_pct,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "open_positions_count": open_positions_count,
            "bot_type": bot_type,
            "execution_mode": execution_mode,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="equity_snapshots", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped equity snapshot")

    def enqueue_ai_prediction(
        self,
        ticker: str,
        p_up: float,
        p_down: float,
        p_wait: float,
        vpin: float,
        ev_yes: float,
        ev_no: float,
        recommended_side: str,
        rationale: Optional[str] = None,
        bot_type: str = "onnx_ml_bot",
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Enqueue an AI prediction and Stage 2 EV decision log."""
        ts = timestamp or datetime.now(timezone.utc)
        record = {
            "timestamp_utc": ts.isoformat(),
            "timestamp_epoch_ms": int(ts.timestamp() * 1000),
            "ticker": ticker,
            "p_up": p_up,
            "p_down": p_down,
            "p_wait": p_wait,
            "vpin": vpin,
            "ev_yes": ev_yes,
            "ev_no": ev_no,
            "recommended_side": recommended_side,
            "rationale": rationale,
            "bot_type": bot_type,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="ai_predictions", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped AI prediction for %s", ticker)

    def enqueue_circuit_breaker_event(
        self,
        event_type: str,
        peak_capital: float,
        current_equity: float,
        drawdown_pct: float,
        reason: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Enqueue a circuit breaker trip or reset event."""
        ts = timestamp or datetime.now(timezone.utc)
        record = {
            "timestamp_utc": ts.isoformat(),
            "timestamp_epoch_ms": int(ts.timestamp() * 1000),
            "event_type": event_type,
            "peak_capital": peak_capital,
            "current_equity": current_equity,
            "drawdown_pct": drawdown_pct,
            "reason": reason,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="circuit_breaker_events", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped circuit breaker event")

    def enqueue_batch_assessment(
        self,
        batch_number: int,
        evaluation_date: str,
        verdict: str,
        wins: int,
        losses: int,
        total_trades: int,
        win_rate: float,
        net_pnl: float,
        document_id: Optional[str] = None,
        time_window: Optional[str] = None,
        market_session: Optional[str] = None,
        target_asset: str = "KXBTC15M",
        vessel: Optional[str] = None,
        active_playbook: Optional[str] = None,
        pre_batch_balance: Optional[float] = None,
        post_batch_balance: Optional[float] = None,
        market_regime: Optional[str] = None,
        microstructure_context: Optional[str] = None,
        winning_autopsy: Optional[str] = None,
        losing_autopsy: Optional[str] = None,
        root_cause_why: Optional[str] = None,
        changes_triggered: Optional[str] = None,
        council_directives: Optional[str] = None,
        lessons_learned: Optional[str] = None,
        trades_json: Optional[str] = None,
        raw_markdown: Optional[str] = None,
    ) -> None:
        """Enqueue an audited 6-trade batch evaluation assessment."""
        record = {
            "batch_number": batch_number,
            "document_id": document_id,
            "evaluation_date": evaluation_date,
            "time_window": time_window,
            "market_session": market_session,
            "target_asset": target_asset,
            "vessel": vessel,
            "active_playbook": active_playbook,
            "verdict": verdict,
            "wins": wins,
            "losses": losses,
            "total_trades": total_trades,
            "win_rate": float(win_rate),
            "net_pnl": float(net_pnl),
            "pre_batch_balance": float(pre_batch_balance) if pre_batch_balance is not None else None,
            "post_batch_balance": float(post_batch_balance) if post_batch_balance is not None else None,
            "market_regime": market_regime,
            "microstructure_context": microstructure_context,
            "winning_autopsy": winning_autopsy,
            "losing_autopsy": losing_autopsy,
            "root_cause_why": root_cause_why,
            "changes_triggered": changes_triggered,
            "council_directives": council_directives,
            "lessons_learned": lessons_learned,
            "trades_json": trades_json,
            "raw_markdown": raw_markdown,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="batch_assessments", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped batch assessment #%d", batch_number)

    def enqueue_unfilled_order(
        self,
        order_id: str,
        ticker: str,
        side: str,
        limit_price: float,
        size: int,
        created_at_utc: str,
        terminated_at_utc: str,
        lifetime_seconds: float,
        cancellation_reason: str,
        time_remaining_at_cancel_s: Optional[float] = None,
        best_ask_at_placement: Optional[float] = None,
        closest_ask_approach: Optional[float] = None,
        price_gap_cents: Optional[float] = None,
        initial_queue_ahead: int = 0,
        volume_traded_at_price: int = 0,
        queue_deficit: int = 0,
        queue_exhaustion_pct: float = 0.0,
        t1_spot_price: Optional[float] = None,
        t1_strike_diff: Optional[float] = None,
        t1_macro_1h_slope: Optional[float] = None,
        t1_regime: Optional[str] = None,
        t1_vpin: Optional[float] = None,
        t4_spot_price: Optional[float] = None,
        t4_macro_1h_slope: Optional[float] = None,
        t4_regime: Optional[str] = None,
        settlement_outcome_if_filled: Optional[str] = None,
        counterfactual_pnl: Optional[float] = None,
        diagnostic_category: Optional[str] = None,
        bot_type: str = "bot1_v4_domination",
    ) -> None:
        """Enqueue an unfilled resting limit order telemetry record."""
        record = {
            "order_id": order_id,
            "ticker": ticker,
            "side": side,
            "limit_price": float(limit_price),
            "size": int(size),
            "created_at_utc": created_at_utc,
            "terminated_at_utc": terminated_at_utc,
            "lifetime_seconds": float(lifetime_seconds),
            "time_remaining_at_cancel_s": float(time_remaining_at_cancel_s) if time_remaining_at_cancel_s is not None else None,
            "cancellation_reason": cancellation_reason,
            "best_ask_at_placement": float(best_ask_at_placement) if best_ask_at_placement is not None else None,
            "closest_ask_approach": float(closest_ask_approach) if closest_ask_approach is not None else None,
            "price_gap_cents": float(price_gap_cents) if price_gap_cents is not None else None,
            "initial_queue_ahead": int(initial_queue_ahead),
            "volume_traded_at_price": int(volume_traded_at_price),
            "queue_deficit": int(queue_deficit),
            "queue_exhaustion_pct": float(queue_exhaustion_pct),
            "t1_spot_price": float(t1_spot_price) if t1_spot_price is not None else None,
            "t1_strike_diff": float(t1_strike_diff) if t1_strike_diff is not None else None,
            "t1_macro_1h_slope": float(t1_macro_1h_slope) if t1_macro_1h_slope is not None else None,
            "t1_regime": t1_regime,
            "t1_vpin": float(t1_vpin) if t1_vpin is not None else None,
            "t4_spot_price": float(t4_spot_price) if t4_spot_price is not None else None,
            "t4_macro_1h_slope": float(t4_macro_1h_slope) if t4_macro_1h_slope is not None else None,
            "t4_regime": t4_regime,
            "settlement_outcome_if_filled": settlement_outcome_if_filled,
            "counterfactual_pnl": float(counterfactual_pnl) if counterfactual_pnl is not None else None,
            "diagnostic_category": diagnostic_category,
            "bot_type": bot_type,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="unfilled_orders", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped unfilled order %s", order_id)

    def enqueue_lifecycle_forensics(
        self,
        trade_id: str,
        ticker: str,
        side: str,
        entry_price: float,
        outcome: str,
        realized_pnl: float,
        role: str = "MAKER",
        fee_paid: float = 0.0,
        t1_timestamp: Optional[str] = None,
        t1_spot: Optional[float] = None,
        t1_strike_diff: Optional[float] = None,
        t1_1h_slope: Optional[float] = None,
        t1_regime: Optional[str] = None,
        t1_vpin: Optional[float] = None,
        t2_timestamp: Optional[str] = None,
        t2_queue_wait_seconds: Optional[float] = None,
        t2_spot: Optional[float] = None,
        t2_1h_slope: Optional[float] = None,
        t2_regime: Optional[str] = None,
        t2_vpin: Optional[float] = None,
        t3_timestamp: Optional[str] = None,
        t3_spot: Optional[float] = None,
        t3_60s_twap: Optional[float] = None,
        twap_vs_spot_divergence: Optional[float] = None,
        t3_1h_slope: Optional[float] = None,
        t3_regime: Optional[str] = None,
        mfe_favorable_excursion: Optional[float] = None,
        mae_adverse_excursion: Optional[float] = None,
        regime_mutated: int = 0,
        trend_flipped: int = 0,
        adverse_selection_fill: int = 0,
        bot_type: str = "bot1_v4_domination",
    ) -> None:
        """Enqueue a 4-checkpoint executed trade lifecycle forensic record."""
        record = {
            "trade_id": trade_id,
            "ticker": ticker,
            "side": side,
            "entry_price": float(entry_price),
            "role": role,
            "fee_paid": float(fee_paid),
            "t1_timestamp": t1_timestamp,
            "t1_spot": float(t1_spot) if t1_spot is not None else None,
            "t1_strike_diff": float(t1_strike_diff) if t1_strike_diff is not None else None,
            "t1_1h_slope": float(t1_1h_slope) if t1_1h_slope is not None else None,
            "t1_regime": t1_regime,
            "t1_vpin": float(t1_vpin) if t1_vpin is not None else None,
            "t2_timestamp": t2_timestamp,
            "t2_queue_wait_seconds": float(t2_queue_wait_seconds) if t2_queue_wait_seconds is not None else None,
            "t2_spot": float(t2_spot) if t2_spot is not None else None,
            "t2_1h_slope": float(t2_1h_slope) if t2_1h_slope is not None else None,
            "t2_regime": t2_regime,
            "t2_vpin": float(t2_vpin) if t2_vpin is not None else None,
            "t3_timestamp": t3_timestamp,
            "t3_spot": float(t3_spot) if t3_spot is not None else None,
            "t3_60s_twap": float(t3_60s_twap) if t3_60s_twap is not None else None,
            "twap_vs_spot_divergence": float(twap_vs_spot_divergence) if twap_vs_spot_divergence is not None else None,
            "t3_1h_slope": float(t3_1h_slope) if t3_1h_slope is not None else None,
            "t3_regime": t3_regime,
            "mfe_favorable_excursion": float(mfe_favorable_excursion) if mfe_favorable_excursion is not None else None,
            "mae_adverse_excursion": float(mae_adverse_excursion) if mae_adverse_excursion is not None else None,
            "outcome": outcome,
            "realized_pnl": float(realized_pnl),
            "regime_mutated": int(regime_mutated),
            "trend_flipped": int(trend_flipped),
            "adverse_selection_fill": int(adverse_selection_fill),
            "bot_type": bot_type,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="trade_lifecycle_forensics", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped lifecycle forensics %s", trade_id)

    def enqueue_failure_autopsy(
        self,
        trade_id: str,
        ticker: str,
        outcome: str,
        realized_pnl: float,
        failure_code: str,
        is_counter_trend: int = 0,
        macro_1h_slope: Optional[float] = None,
        is_double_wick_trap: int = 0,
        wick_to_body_ratio: Optional[float] = None,
        moat_deficit_dollars: float = 0.0,
        was_salvageable: int = 0,
        salvageable_cents_lost: float = 0.0,
        mfe_price: Optional[float] = None,
        peak_profit_giveback_pct: float = 0.0,
        cents_left_on_table: float = 0.0,
        stinginess_gap_cents: float = 0.0,
        queue_deficit: int = 0,
        is_toxic_dump_fill: int = 0,
        vpin_spike_at_fill: float = 0.0,
        is_twap_pin_victim: int = 0,
        twap_vs_spot_divergence: float = 0.0,
        bot_type: str = "bot1_v4_domination",
    ) -> None:
        """Enqueue a standardized failure/mistake attribution autopsy record."""
        record = {
            "trade_id": trade_id,
            "ticker": ticker,
            "outcome": outcome,
            "realized_pnl": float(realized_pnl),
            "failure_code": failure_code,
            "is_counter_trend": int(is_counter_trend),
            "macro_1h_slope": float(macro_1h_slope) if macro_1h_slope is not None else None,
            "is_double_wick_trap": int(is_double_wick_trap),
            "wick_to_body_ratio": float(wick_to_body_ratio) if wick_to_body_ratio is not None else None,
            "moat_deficit_dollars": float(moat_deficit_dollars),
            "was_salvageable": int(was_salvageable),
            "salvageable_cents_lost": float(salvageable_cents_lost),
            "mfe_price": float(mfe_price) if mfe_price is not None else None,
            "peak_profit_giveback_pct": float(peak_profit_giveback_pct),
            "cents_left_on_table": float(cents_left_on_table),
            "stinginess_gap_cents": float(stinginess_gap_cents),
            "queue_deficit": int(queue_deficit),
            "is_toxic_dump_fill": int(is_toxic_dump_fill),
            "vpin_spike_at_fill": float(vpin_spike_at_fill),
            "is_twap_pin_victim": int(is_twap_pin_victim),
            "twap_vs_spot_divergence": float(twap_vs_spot_divergence),
            "bot_type": bot_type,
        }
        try:
            self.queue.put_nowait(QueuedRecord(table="trade_failure_autopsies", data=record))
        except asyncio.QueueFull:
            logger.warning("DatabaseWriter queue full; dropped failure autopsy %s", trade_id)



# Global default writer singleton
_global_db_writer: Optional[DatabaseWriter] = None


def get_db_writer() -> DatabaseWriter:
    """Retrieve or create the global DatabaseWriter singleton."""
    global _global_db_writer
    if _global_db_writer is None:
        _global_db_writer = DatabaseWriter()
    return _global_db_writer


# Global ETH writer singleton
_global_eth_db_writer: Optional[DatabaseWriter] = None


def get_eth_db_writer() -> DatabaseWriter:
    """Retrieve or create the global ETH DatabaseWriter singleton."""
    global _global_eth_db_writer
    if _global_eth_db_writer is None:
        _global_eth_db_writer = DatabaseWriter(db_manager=get_eth_db())
    return _global_eth_db_writer
