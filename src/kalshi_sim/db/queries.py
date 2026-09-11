"""Historical Time-Series Analytics and Query Engine for SQLite Store.

Provides high-performance paginated queries and institutional portfolio analytics:
- Trades, Settlements, and AI Predictions time-series queries
- Equity Curve & Drawdown time-series retrieval with bot and execution mode isolation
- Exact quantitative metrics: Sharpe, Sortino, Calmar, Profit Factor, Payoff Ratio, Win Rate
- Selective manual history reset capabilities
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import aiosqlite
import numpy as np

from kalshi_sim.db.connection import DatabaseManager, get_db

logger = logging.getLogger(__name__)


def _expand_bot_aliases(bot_type: Optional[str]) -> Optional[List[str]]:
    """Expand bot_type into all historical and current database aliases."""
    if not bot_type or bot_type.lower() in ("all", "combined"):
        return None
    bt = bot_type.lower().strip()
    if bt in (
        "macro_trend_dominion",
        "macro_onnx",
        "macro_trend",
        "macro_trend_dominion_bot",
        "macro_onnx_bot",
        "macro_trend_onnx_fusion",
        "onnx_macro_v2",
    ):
        return [
            "macro_trend_dominion",
            "macro_onnx",
            "macro_trend",
            "macro_trend_dominion_bot",
            "macro_onnx_bot",
            "macro_trend_onnx_fusion",
            "onnx_macro_v2",
        ]
    if bt in (
        "dual_onnx",
        "the_onnx_strategy",
        "onnx_microstructure_bot",
        "onnx_microstructure",
        "dual_onnx_bot",
        "dual_onnx_arbitrage",
    ):
        return [
            "dual_onnx",
            "the_onnx_strategy",
            "onnx_microstructure_bot",
            "onnx_microstructure",
            "dual_onnx_bot",
            "dual_onnx_arbitrage",
        ]
    if bt in (
        "3_step_domination_bot",
        "dominion_2_bot",
        "three_step_domination_bot",
        "3_step_dominion",
    ):
        return [
            "3_step_domination_bot",
            "dominion_2_bot",
            "three_step_domination_bot",
            "3_step_dominion",
        ]
    return [bot_type]


class HistoricalQueryService:
    """Provides analytical and time-series query operations over SQLite historical data."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db_manager = db_manager or get_db()

    async def get_trades(
        self,
        ticker: Optional[str] = None,
        asset: Optional[str] = None,
        timeframe: Optional[str] = None,
        bot_type: Optional[str] = None,
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
        if asset and asset.lower() != "all":
            query += " AND ticker LIKE ?"
            params.append(f"KX{asset.upper()}%")
        if timeframe and timeframe.lower() != "all":
            query += " AND (timeframe = ? OR ticker LIKE ?)"
            params.extend([timeframe.lower(), f"%{timeframe.upper()}%"])
        bot_aliases = _expand_bot_aliases(bot_type)
        if bot_aliases:
            placeholders = ",".join("?" for _ in bot_aliases)
            query += f" AND bot_type IN ({placeholders})"
            params.extend(bot_aliases)
        if execution_mode and execution_mode.lower() != "all":
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
        asset: Optional[str] = None,
        timeframe: Optional[str] = None,
        bot_type: Optional[str] = None,
        execution_mode: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve paginated contract settlement outcomes."""
        query = "SELECT * FROM settlements WHERE 1=1"
        params: List[Any] = []

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        if asset and asset.lower() != "all":
            query += " AND ticker LIKE ?"
            params.append(f"KX{asset.upper()}%")
        if timeframe and timeframe.lower() != "all":
            query += " AND ticker LIKE ?"
            params.append(f"%{timeframe.upper()}%")
        bot_aliases = _expand_bot_aliases(bot_type)
        if bot_aliases:
            placeholders = ",".join("?" for _ in bot_aliases)
            query += f" AND bot_type IN ({placeholders})"
            params.extend(bot_aliases)
        if execution_mode and execution_mode.lower() != "all":
            query += " AND execution_mode = ?"
            params.append(execution_mode)

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
        bot_type: Optional[str] = None,
        execution_mode: Optional[str] = None,
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
        bot_aliases = _expand_bot_aliases(bot_type)
        if bot_aliases:
            placeholders = ",".join("?" for _ in bot_aliases)
            query += f" AND (bot_type IN ({placeholders}) OR bot_type = 'all')"
            params.extend(bot_aliases)
        if execution_mode and execution_mode.lower() != "all":
            query += " AND execution_mode = ?"
            params.append(execution_mode)
            if execution_mode.lower() == "live":
                query += " AND equity <= 50.0"

        query += " ORDER BY timestamp_epoch_ms ASC LIMIT ?"
        params.append(limit)

        async with self.db_manager.get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_ai_predictions(
        self,
        ticker: Optional[str] = None,
        bot_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent AI model predictions and Stage 2 EV decisions."""
        query = "SELECT * FROM ai_predictions WHERE 1=1"
        params: List[Any] = []

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        bot_aliases = _expand_bot_aliases(bot_type)
        if bot_aliases:
            placeholders = ",".join("?" for _ in bot_aliases)
            query += f" AND bot_type IN ({placeholders})"
            params.extend(bot_aliases)

        query += " ORDER BY timestamp_epoch_ms DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self.db_manager.get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def compute_portfolio_metrics(
        self,
        bot_type: Optional[str] = None,
        execution_mode: Optional[str] = None,
        asset: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compute institutional performance statistics filtered by bot, execution mode, asset, and timeframe."""
        st_where = " WHERE 1=1"
        st_params: List[Any] = []
        tr_where = " WHERE 1=1"
        tr_params: List[Any] = []
        eq_where = " WHERE 1=1"
        eq_params: List[Any] = []

        bot_aliases = _expand_bot_aliases(bot_type)
        if bot_aliases:
            placeholders = ",".join("?" for _ in bot_aliases)
            st_where += f" AND bot_type IN ({placeholders})"
            st_params.extend(bot_aliases)
            tr_where += f" AND bot_type IN ({placeholders})"
            tr_params.extend(bot_aliases)
            eq_where += f" AND (bot_type IN ({placeholders}) OR bot_type = 'all')"
            eq_params.extend(bot_aliases)

        if execution_mode and execution_mode.lower() != "all":
            st_where += " AND execution_mode = ?"
            st_params.append(execution_mode)
            tr_where += " AND execution_mode = ?"
            tr_params.append(execution_mode)
            eq_where += " AND execution_mode = ?"
            eq_params.append(execution_mode)

        if asset and asset.lower() != "all":
            asset_pat = f"KX{asset.upper()}%"
            st_where += " AND ticker LIKE ?"
            st_params.append(asset_pat)
            tr_where += " AND ticker LIKE ?"
            tr_params.append(asset_pat)

        if timeframe and timeframe.lower() != "all":
            tf_pat = f"%{timeframe.upper()}%"
            st_where += " AND ticker LIKE ?"
            st_params.append(tf_pat)
            tr_where += " AND (timeframe = ? OR ticker LIKE ?)"
            tr_params.extend([timeframe.lower(), tf_pat])

        async with self.db_manager.get_connection() as db:
            # 1. Fetch settlements
            async with db.execute(
                f"SELECT pnl, entry_price, size, outcome FROM settlements{st_where} ORDER BY timestamp_epoch_ms ASC",
                st_params,
            ) as cursor:
                settlement_rows = await cursor.fetchall()

            # 2. Fetch fees paid from trades
            async with db.execute(f"SELECT SUM(fees) FROM trades{tr_where}", tr_params) as cursor:
                row = await cursor.fetchone()
                total_fees = float(row[0]) if row and row[0] is not None else 0.0

            # 3. Fetch earliest and latest equity snapshots
            async with db.execute(
                f"SELECT balance, equity FROM equity_snapshots{eq_where} ORDER BY timestamp_epoch_ms ASC LIMIT 1",
                eq_params,
            ) as cursor:
                first_eq_row = await cursor.fetchone()
                if execution_mode == "live":
                    initial_capital = float(first_eq_row["balance"]) if (first_eq_row and float(first_eq_row["balance"]) < 50.0) else 25.0
                else:
                    initial_capital = float(first_eq_row["balance"]) if first_eq_row else 100.0

            async with db.execute(
                f"SELECT balance, equity, drawdown_pct FROM equity_snapshots{eq_where} ORDER BY timestamp_epoch_ms DESC LIMIT 1",
                eq_params,
            ) as cursor:
                eq_row = await cursor.fetchone()
                current_equity = float(eq_row["equity"]) if eq_row else initial_capital
                current_balance = float(eq_row["balance"]) if eq_row else initial_capital
                if execution_mode == "live":
                    # Derive live balance from latest settlement balance_after if available
                    if settlement_rows:
                        async with db.execute(
                            f"SELECT balance_after FROM settlements{st_where} ORDER BY timestamp_epoch_ms DESC LIMIT 1",
                            st_params,
                        ) as st_cur:
                            st_row = await st_cur.fetchone()
                            if st_row and st_row["balance_after"] is not None and float(st_row["balance_after"]) > 0:
                                current_balance = float(st_row["balance_after"])
                                current_equity = float(st_row["balance_after"])
                    elif current_equity > 50.0 or current_balance > 50.0:
                        realized_pnl_so_far = sum(float(r["pnl"]) for r in settlement_rows)
                        current_equity = round(initial_capital + realized_pnl_so_far, 2)
                        current_balance = round(initial_capital + realized_pnl_so_far, 2)

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
        active_trades = wins + losses
        win_rate = (wins / active_trades * 100.0) if active_trades > 0 else 0.0

        gross_profit = sum(winning_pnls)
        gross_loss = abs(sum(losing_pnls))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 1.0)

        total_realized_pnl = sum(pnls)
        net_pnl = total_realized_pnl - total_fees
        if execution_mode == "live":
            initial_capital = max(25.0, round(current_balance - net_pnl, 2))
        total_roi = (net_pnl / initial_capital) * 100.0 if initial_capital > 0 else 0.0

        avg_win = float(np.mean(winning_pnls)) if winning_pnls else 0.0
        avg_loss = abs(float(np.mean(losing_pnls))) if losing_pnls else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else (99.9 if avg_win > 0 else 1.0)
        avg_trade_pnl = float(np.mean(pnls))

        # Expectancy = (Win% * AvgWin) - (Loss% * AvgLoss)
        win_prob = wins / active_trades if active_trades > 0 else 0.0
        loss_prob = losses / active_trades if active_trades > 0 else 0.0
        expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

        # Compute return percentages per trade
        trade_returns = []
        for r in settlement_rows:
            cost = float(r["entry_price"]) * int(r["size"])
            trade_returns.append(float(r["pnl"]) / (cost + 1e-9))

        ret_arr = np.array(trade_returns, dtype=np.float64)
        mean_ret = float(np.mean(ret_arr))
        std_ret = float(np.std(ret_arr))

        # Annualized Sharpe & Sortino (365 days * 24h * 4 = 35,040 intervals/year for 15M continuous crypto contracts)
        annualization_factor = math.sqrt(365 * 24 * 4)
        if std_ret < 1e-6:
            sharpe = 0.0
        else:
            sharpe = max(-99.9, min(99.9, (mean_ret / std_ret) * annualization_factor))

        # Exact Downside Semi-Deviation for Sortino: sqrt(E[min(0, r)^2]) with zero-downside safeguard
        if len(losing_pnls) == 0:
            sortino = min(99.9, sharpe * 1.5) if sharpe > 0 else 0.0
        else:
            downside_sq = np.minimum(0.0, ret_arr) ** 2
            downside_dev = float(np.sqrt(np.mean(downside_sq)))
            if downside_dev < 1e-6:
                sortino = min(99.9, sharpe * 1.5) if sharpe > 0 else 0.0
            else:
                sortino = max(-99.9, min(99.9, (mean_ret / downside_dev) * annualization_factor))

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
        calmar = max(-99.9, min(99.9, calmar))

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

    async def reset_history(
        self,
        bot_type: Optional[str] = None,
        execution_mode: Optional[str] = None,
    ) -> Dict[str, int]:
        """Selectively delete history records from SQLite database."""
        bot_aliases = _expand_bot_aliases(bot_type)
        if bot_aliases:
            placeholders = ",".join("?" for _ in bot_aliases)
            where_clause += f" AND bot_type IN ({placeholders})"
            params.extend(bot_aliases)

        if execution_mode and execution_mode.lower() != "all":
            where_clause += " AND execution_mode = ?"
            params.append(execution_mode)

        counts = {"settlements": 0, "trades": 0, "ai_predictions": 0, "equity_snapshots": 0}

        async with self.db_manager.get_connection() as db:
            for table in ["settlements", "trades", "ai_predictions", "equity_snapshots"]:
                try:
                    # Check if table has bot_type column
                    cur = await db.execute(f"DELETE FROM {table}{where_clause}", params)
                    counts[table] = cur.rowcount
                except Exception as exc:
                    # Fallback for tables without bot_type
                    logger.debug("Selective reset error for table %s: %s", table, exc)
                    if bot_type is None or bot_type.lower() in ("all", "combined"):
                        cur = await db.execute(f"DELETE FROM {table}")
                        counts[table] = cur.rowcount
            await db.commit()

        logger.info("Reset historical database for bot=%s, mode=%s: %s", bot_type, execution_mode, counts)
        return counts

    async def delete_trade(self, trade_id_or_id: str | int) -> bool:
        """Delete a single trade by primary key ID or trade_id."""
        async with self.db_manager.get_connection() as db:
            if isinstance(trade_id_or_id, int) or (isinstance(trade_id_or_id, str) and trade_id_or_id.isdigit()):
                cur = await db.execute("DELETE FROM trades WHERE id = ? OR trade_id = ?", [int(trade_id_or_id), str(trade_id_or_id)])
            else:
                cur = await db.execute("DELETE FROM trades WHERE trade_id = ?", [str(trade_id_or_id)])
            await db.commit()
            return cur.rowcount > 0

    async def delete_settlement(self, settlement_id_or_id: str | int) -> bool:
        """Delete a single settlement by primary key ID or settlement_id."""
        async with self.db_manager.get_connection() as db:
            if isinstance(settlement_id_or_id, int) or (isinstance(settlement_id_or_id, str) and settlement_id_or_id.isdigit()):
                cur = await db.execute("DELETE FROM settlements WHERE id = ? OR settlement_id = ?", [int(settlement_id_or_id), str(settlement_id_or_id)])
            else:
                cur = await db.execute("DELETE FROM settlements WHERE settlement_id = ?", [str(settlement_id_or_id)])
            await db.commit()
            return cur.rowcount > 0

    async def delete_ai_prediction(self, prediction_id: int | str) -> bool:
        """Delete an AI prediction record by primary key ID."""
        async with self.db_manager.get_connection() as db:
            cur = await db.execute("DELETE FROM ai_predictions WHERE id = ?", [int(prediction_id)])
            await db.commit()
            return cur.rowcount > 0

    async def delete_batch(self, table: str, ids: List[Any]) -> int:
        """Batch delete records from a specified historical table given a list of IDs."""
        valid_tables = {"trades", "settlements", "ai_predictions", "equity_snapshots"}
        if table not in valid_tables:
            raise ValueError(f"Invalid table name for delete operation: {table}")
        if not ids:
            return 0

        placeholders = ",".join("?" for _ in ids)
        id_col = "trade_id" if table == "trades" and any(isinstance(x, str) and not x.isdigit() for x in ids) else "id"

        async with self.db_manager.get_connection() as db:
            # Handle mixed string trade_id or int id
            if table == "trades":
                cur = await db.execute(f"DELETE FROM trades WHERE id IN ({placeholders}) OR trade_id IN ({placeholders})", ids + ids)
            elif table == "settlements":
                cur = await db.execute(f"DELETE FROM settlements WHERE id IN ({placeholders}) OR settlement_id IN ({placeholders})", ids + ids)
            else:
                cur = await db.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
            await db.commit()
            return cur.rowcount

