"""Structured execution logger for the simulation engine.

Logs simulated orders, fills, settlements, and portfolio P&L summaries
to both the console and a JSON Lines (.jsonl) file for backtesting analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import orjson

from kalshi_sim.schemas import (
    PnLSnapshot,
    Position,
    SettlementResult,
    SimulatedFill,
    SimulatedOrder,
    Timeframe,
)


def _orjson_default(obj: Any) -> Any:
    """Handle types that orjson cannot serialize natively."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    raise TypeError(f"Cannot serialize {type(obj)}")


def _format_currency(val: Decimal | None) -> str:
    """Format a Decimal as a currency string ($X,XXX.XX or -$X,XXX.XX)."""
    if val is None:
        return "$0.00"
    if val < 0:
        return f"-${abs(val):,.2f}"
    return f"${val:,.2f}"


class ExecutionLogger:
    """Structured logger for simulated trade executions, settlements, and P&L.

    Outputs human-readable text to the console and structured JSON Lines records
    to ``data/executions_{session_id or timestamp}.jsonl``.

    Usage::

        logger = ExecutionLogger(data_dir=Path("data"))
        logger.log_execution(order, fill)
        logger.log_settlement(settlement_result)
        logger.log_pnl_summary(pnl_snapshot)
        logger.close()
    """

    def __init__(self, data_dir: Path, session_id: str = "") -> None:
        """Initialize the execution logger and open the JSONL log file.

        Args:
            data_dir: Directory where execution log files will be stored.
            session_id: Optional session identifier. If omitted, the current UTC timestamp is used.
        """
        self._data_dir = data_dir
        self._session_id = session_id
        self._logger = logging.getLogger(__name__)

        self._data_dir.mkdir(parents=True, exist_ok=True)
        suffix = session_id if session_id else datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._file_path = self._data_dir / f"executions_{suffix}.jsonl"
        self._file = open(self._file_path, "ab")
        self._logger.info("Execution logger initialized: %s", self._file_path)

    def open(self) -> Path:
        """Ensure log file is open and return its path."""
        if self._file is None or self._file.closed:
            self._file = open(self._file_path, "ab")
        return self._file_path

    @property
    def file_path(self) -> Path:
        """Path to the active execution log file."""
        return self._file_path

    def _write_jsonl(self, data: dict[str, Any]) -> None:
        """Serialize a dictionary and append it as a line to the JSONL file."""
        if self._file is not None and not self._file.closed:
            line = orjson.dumps(data, default=_orjson_default)
            self._file.write(line + b"\n")
            self._file.flush()

    def log_execution(self, order: SimulatedOrder, fill: SimulatedFill) -> None:
        """Log a simulated order fill execution to console and JSONL.

        Console format:
            `[{timestamp}] | [{timeframe}] | [{ticker}] | [{side}] | [{size}] | [${fill_price}] | [{reasoning}]`

        Args:
            order: The virtual order submitted.
            fill: The execution fill report.
        """
        ts_str = (
            fill.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(fill.timestamp, datetime)
            else str(fill.timestamp)
        )
        tf_str = order.timeframe.value if hasattr(order.timeframe, "value") else str(order.timeframe)
        side_str = fill.side.value if hasattr(fill.side, "value") else str(fill.side)

        console_msg = (
            f"[{ts_str}] | [{tf_str}] | [{fill.ticker}] | [{side_str}] | "
            f"[{fill.size}] | [${fill.fill_price}] | [{order.reasoning}]"
        )
        print(console_msg)

        data = {
            "_type": "execution",
            **order.model_dump(),
            **fill.model_dump(),
        }
        self._write_jsonl(data)

    def log_settlement(self, result: SettlementResult) -> None:
        """Log a position settlement outcome to console and JSONL.

        Console format:
            `[{timestamp}] | SETTLEMENT | [{ticker}] | [{side}] | [{size}] | [{outcome}] | P&L: ${pnl}`

        Args:
            result: Outcome of the settled binary-option position.
        """
        ts_str = (
            result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(result.timestamp, datetime)
            else str(result.timestamp)
        )
        side_str = result.side.value if hasattr(result.side, "value") else str(result.side)

        console_msg = (
            f"[{ts_str}] | SETTLEMENT | [{result.ticker}] | [{side_str}] | "
            f"[{result.size}] | [{result.outcome}] | P&L: ${result.pnl}"
        )
        print(console_msg)

        data = {
            "_type": "settlement",
            **result.model_dump(),
        }
        self._write_jsonl(data)

    def log_pnl_summary(self, snapshot: PnLSnapshot) -> None:
        """Print a formatted P&L summary box to console and write to JSONL.

        Args:
            snapshot: Point-in-time portfolio performance snapshot.
        """
        balance_str = _format_currency(snapshot.current_balance)
        equity_str = _format_currency(snapshot.total_equity)
        realized_str = _format_currency(snapshot.total_realized_pnl)
        unrealized_str = _format_currency(snapshot.total_unrealized_pnl)
        positions_str = str(snapshot.open_positions)
        trades_str = str(snapshot.total_trades)
        win_rate_str = (
            f"{snapshot.win_rate * 100:.1f}%"
            if snapshot.win_rate is not None
            else "0.0%"
        )

        line1 = f"Balance:    {balance_str:<12} Equity:     {equity_str}"
        line2 = f"Realized:   {realized_str:<12} Unrealized: {unrealized_str}"
        line3 = f"Positions:  {positions_str:<12} Trades:     {trades_str:<8} Win Rate: {win_rate_str}"

        box = (
            "+-------------------------- P&L SUMMARY ---------------------------+\n"
            f"| {line1:<64} |\n"
            f"| {line2:<64} |\n"
            f"| {line3:<64} |\n"
            "+------------------------------------------------------------------+"
        )
        print(box)

        data = {
            "_type": "pnl_snapshot",
            **snapshot.model_dump(),
        }
        self._write_jsonl(data)

    def format_positions_table(self, positions: list[Position]) -> str:
        """Format a list of open positions as an ASCII table.

        Columns: Ticker | Side | Size | Entry | Current | Unrealized P&L

        Args:
            positions: List of open positions.

        Returns:
            Formatted ASCII table string.
        """
        ticker_w = max((len(p.ticker) for p in positions), default=6)
        ticker_w = max(ticker_w, len("Ticker"))
        side_w = max(len("Side"), 4)
        size_w = max(len("Size"), 4)
        entry_w = max(len("Entry"), 8)
        current_w = max(len("Current"), 8)
        pnl_w = max(len("Unrealized P&L"), 14)

        sep = (
            f"+-{'-' * ticker_w}-+-"
            f"{'-' * side_w}-+-"
            f"{'-' * size_w}-+-"
            f"{'-' * entry_w}-+-"
            f"{'-' * current_w}-+-"
            f"{'-' * pnl_w}-+"
        )
        header = (
            f"| {'Ticker':<{ticker_w}} "
            f"| {'Side':<{side_w}} "
            f"| {'Size':>{size_w}} "
            f"| {'Entry':>{entry_w}} "
            f"| {'Current':>{current_w}} "
            f"| {'Unrealized P&L':>{pnl_w}} |"
        )

        lines = [sep, header, sep]

        if not positions:
            total_inner_w = len(sep) - 4
            empty_msg = "No open positions"
            lines.append(f"| {empty_msg:<{total_inner_w}} |")
        else:
            for p in positions:
                side_str = p.side.value if hasattr(p.side, "value") else str(p.side)
                entry_str = f"${p.avg_entry_price:,.2f}"
                current_str = (
                    f"${p.current_price:,.2f}"
                    if p.current_price is not None
                    else "—"
                )
                if p.unrealized_pnl > 0:
                    pnl_str = f"+${p.unrealized_pnl:,.2f}"
                elif p.unrealized_pnl < 0:
                    pnl_str = f"-${abs(p.unrealized_pnl):,.2f}"
                else:
                    pnl_str = "$0.00"

                row = (
                    f"| {p.ticker:<{ticker_w}} "
                    f"| {side_str:<{side_w}} "
                    f"| {p.size:>{size_w}} "
                    f"| {entry_str:>{entry_w}} "
                    f"| {current_str:>{current_w}} "
                    f"| {pnl_str:>{pnl_w}} |"
                )
                lines.append(row)

        lines.append(sep)
        return "\n".join(lines)

    def close(self) -> None:
        """Flush and close the execution JSONL file."""
        if self._file is not None and not self._file.closed:
            self._file.flush()
            self._file.close()
            self._file = None
            self._logger.info("Execution logger closed: %s", self._file_path)

    def __enter__(self) -> ExecutionLogger:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
