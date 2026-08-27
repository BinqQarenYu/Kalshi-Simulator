"""Historical Time-Series Analytics and Query Engine for SQLite Store.

Provides high-performance paginated queries and institutional portfolio analytics:
- Trades, Settlements, and AI Predictions time-series queries
- Equity Curve & Drawdown time-series retrieval
- Exact quantitative metrics: Sharpe, Sortino, Calmar, Profit Factor, Payoff Ratio, Win Rate
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
import numpy as np

from kalshi_sim.db.connection import DatabaseManager, get_db

logger = logging.getLogger(__name__)


class HistoricalQueryService:
    """Provides analytical and time-series query operations over SQLite historical data."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db_manager = db_manager or get_db()

    async def get_trades(
        self,
        ticker: Optional[str] = None,
        timeframe: Optional[str] = None,
        execution_mode: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve paginated trade execution history with optional filtering."""
        query = "SELECT * FROM trades WHERE 1=1"
        params: List[Any] = []

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)
        if execution_mode:
            query += " AND execution_mode = ?"
            params.append(execution_mode)

        query += " ORDER BY timestamp_epoch_ms DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self.db_manager.get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_settlements(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve paginated contract settlement outcomes."""
        query = "SELECT * FROM settlements WHERE 1=1"
        params: List[Any] = []

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)

        query += " ORDER BY timestamp_epoch_ms DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self.db_manager.get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_equity_curve(
        self,
        start_epoch_ms: Optional[int] = None,
        end_epoch_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Retrieve sequential portfolio equity snapshots for charting."""
        query = "SELECT * FROM equity_snapshots WHERE 1=1"
        params: List[Any] = []

        if start_epoch_ms is not None:
            query += " AND timestamp_epoch_ms >= ?"
            params.append(start_epoch_ms)
        if end_epoch_ms is not None:
            query += " AND timestamp_epoch_ms <= ?"
            params.append(end_epoch_ms)

        query += " ORDER BY timestamp_epoch_ms ASC LIMIT ?"
        params.append(limit)

        async with self.db_manager.get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_ai_predictions(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent AI model predictions and Stage 2 EV decisions."""
        query = "SELECT * FROM ai_predictions WHERE 1=1"
        params: List[Any] = []

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)

        query += " ORDER BY timestamp_epoch_ms DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self.db_manager.get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def compute_portfolio_metrics(self) -> Dict[str, Any]:
        """Compute institutional performance statistics from database history."""
        async with self.db_manager.get_connection() as db:
            # 1. Fetch settlements
            async with db.execute(
                "SELECT pnl, entry_price, size, outcome FROM settlements ORDER BY timestamp_epoch_ms ASC"
            ) as cursor:
                settlement_rows = await cursor.fetchall()

            # 2. Fetch fees paid from trades
            async with db.execute("SELECT SUM(fees) FROM trades") as cursor:
                row = await cursor.fetchone()
                total_fees = float(row[0]) if row and row[0] is not None else 0.0

            # 3. Fetch latest equity snapshot
            async with db.execute(
                "SELECT balance, equity, drawdown_pct FROM equity_snapshots ORDER BY timestamp_epoch_ms DESC LIMIT 1"
            ) as cursor:
                eq_row = await cursor.fetchone()
                current_equity = float(eq_row["equity"]) if eq_row else 10000.0
                current_balance = float(eq_row["balance"]) if eq_row else 10000.0

        total_settled = len(settlement_rows)
        if total_settled == 0:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate_pct": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "profit_factor": 1.0,
                "total_fees_paid": total_fees,
                "total_realized_pnl": 0.0,
                "net_pnl": 0.0,
                "total_roi_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "avg_trade_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "payoff_ratio": 1.0,
                "expectancy_per_trade": 0.0,
                "current_equity": current_equity,
                "current_balance": current_balance,
            }

        pnls = [float(r["pnl"]) for r in settlement_rows]
        winning_pnls = [p for p in pnls if p > 0]
        losing_pnls = [p for p in pnls if p < 0]

        wins = len(winning_pnls)
        losses = len(losing_pnls)
        win_rate = (wins / total_settled) * 100.0

        gross_profit = sum(winning_pnls)
        gross_loss = abs(sum(losing_pnls))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 1.0)

        total_realized_pnl = sum(pnls)
        net_pnl = total_realized_pnl - total_fees
        initial_capital = 10000.0
        total_roi = (net_pnl / initial_capital) * 100.0

        avg_win = float(np.mean(winning_pnls)) if winning_pnls else 0.0
        avg_loss = abs(float(np.mean(losing_pnls))) if losing_pnls else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else (99.9 if avg_win > 0 else 1.0)
        avg_trade_pnl = float(np.mean(pnls))

        # Expectancy = (Win% * AvgWin) - (Loss% * AvgLoss)
        win_prob = wins / total_settled
        loss_prob = losses / total_settled
        expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

        # Compute return percentages per trade
        trade_returns = []
        for r in settlement_rows:
            cost = float(r["entry_price"]) * int(r["size"])
            trade_returns.append(float(r["pnl"]) / (cost + 1e-9))

        ret_arr = np.array(trade_returns, dtype=np.float64)
        mean_ret = float(np.mean(ret_arr))
        std_ret = float(np.std(ret_arr)) + 1e-9

        # Annualized Sharpe (assuming 15m intervals in standard 252-day equity equivalent)
        annualization_factor = math.sqrt(252 * 6.5 * 4)
        sharpe = (mean_ret / std_ret) * annualization_factor

        # Exact Downside Semi-Deviation for Sortino: sqrt(E[min(0, r)^2])
        downside_sq = np.minimum(0.0, ret_arr) ** 2
        downside_dev = float(np.sqrt(np.mean(downside_sq))) + 1e-9
        sortino = (mean_ret / downside_dev) * annualization_factor

        # Max Drawdown
        cum_equity = initial_capital
        peak_equity = initial_capital
        max_dd = 0.0
        for p in pnls:
            cum_equity += p
            if cum_equity > peak_equity:
                peak_equity = cum_equity
            dd = (peak_equity - cum_equity) / peak_equity if peak_equity > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        max_dd_pct = max_dd * 100.0
        calmar = (total_roi / max_dd_pct) if max_dd_pct > 0 else (99.9 if total_roi > 0 else 0.0)

        return {
            "total_trades": total_settled,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "total_fees_paid": round(total_fees, 2),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "total_roi_pct": round(total_roi, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "avg_trade_pnl": round(avg_trade_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "expectancy_per_trade": round(expectancy, 2),
            "current_equity": round(current_equity, 2),
            "current_balance": round(current_balance, 2),
        }
