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

from kalshi_sim.db.connection import DatabaseManager, get_db

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
        self.queue: asyncio.Queue[QueuedRecord] = asyncio.Queue(maxsize=max_queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background queue consumption worker."""
        if self._running:
            return
        await self.db_manager.init_db()
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


# Global default writer singleton
_global_db_writer: Optional[DatabaseWriter] = None


def get_db_writer() -> DatabaseWriter:
    """Retrieve or create the global DatabaseWriter singleton."""
    global _global_db_writer
    if _global_db_writer is None:
        _global_db_writer = DatabaseWriter()
    return _global_db_writer
