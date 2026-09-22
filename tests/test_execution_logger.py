"""Unit tests for src/kalshi_sim/execution_logger.py."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import json

import orjson
import pytest

from kalshi_sim.execution_logger import ExecutionLogger, _format_currency, _orjson_default
from shared.schemas import (
    OrderSide,
    OrderStatus,
    OrderType,
    PnLSnapshot,
    Position,
    SettlementResult,
    SimulatedFill,
    SimulatedOrder,
    Timeframe,
)


def test_orjson_default():
    """Test custom serialization for orjson_default helper."""
    # Decimal
    assert _orjson_default(Decimal("123.45")) == "123.45"

    # datetime
    dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert _orjson_default(dt) == dt.isoformat()

    # Enum or object with .value
    assert _orjson_default(OrderSide.YES) == "yes"

    # Unsupported type
    with pytest.raises(TypeError, match="Cannot serialize"):
        _orjson_default(object())


def test_format_currency():
    """Test currency formatting logic."""
    assert _format_currency(None) == "$0.00"
    assert _format_currency(Decimal("0.00")) == "$0.00"
    assert _format_currency(Decimal("1234.56")) == "$1,234.56"
    assert _format_currency(Decimal("-500.25")) == "-$500.25"


def test_execution_logger_init_and_file_creation(tmp_path: Path):
    """Test ExecutionLogger initialization with custom and default session_id."""
    # Custom session ID
    logger_custom = ExecutionLogger(data_dir=tmp_path, session_id="test_session")
    expected_path = tmp_path / "executions_test_session.jsonl"
    assert logger_custom.file_path == expected_path
    assert expected_path.exists()
    logger_custom.close()

    # Default timestamp session ID
    logger_default = ExecutionLogger(data_dir=tmp_path)
    assert logger_default.file_path.exists()
    assert logger_default.file_path.name.startswith("executions_")
    assert logger_default.file_path.name.endswith(".jsonl")
    logger_default.close()


def test_execution_logger_open_and_close(tmp_path: Path):
    """Test opening, reopening, and closing file handles."""
    logger = ExecutionLogger(data_dir=tmp_path, session_id="open_close_test")
    path = logger.file_path
    assert not logger._file.closed

    logger.close()
    assert logger._file is None

    # Reopen
    reopened_path = logger.open()
    assert reopened_path == path
    assert logger._file is not None
    assert not logger._file.closed

    logger.close()


def test_execution_logger_context_manager(tmp_path: Path):
    """Test ExecutionLogger as a context manager."""
    with ExecutionLogger(data_dir=tmp_path, session_id="ctx_test") as logger:
        path = logger.file_path
        assert path.exists()
        assert not logger._file.closed

    assert logger._file is None


def test_log_execution(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Test log_execution output to console and JSONL file."""
    now = datetime(2025, 1, 1, 15, 30, 0, tzinfo=timezone.utc)
    order = SimulatedOrder(
        order_id="ord_100",
        ticker="KXBTC15M-T80000",
        side=OrderSide.YES,
        order_type=OrderType.LIMIT,
        size=2,
        limit_price=Decimal("0.55"),
        timeframe=Timeframe.FIFTEEN_MIN,
        reasoning="Bullish momentum",
        created_at=now,
        status=OrderStatus.PENDING,
    )
    fill = SimulatedFill(
        order_id="ord_100",
        ticker="KXBTC15M-T80000",
        side=OrderSide.YES,
        size=2,
        fill_price=Decimal("0.54"),
        slippage=Decimal("0.01"),
        fee=Decimal("0.02"),
        cost=Decimal("1.08"),
        timestamp=now,
    )

    with ExecutionLogger(data_dir=tmp_path, session_id="exec_log_test") as logger:
        logger.log_execution(order, fill)

    # Check console stdout
    captured = capsys.readouterr()
    expected_console = "[2025-01-01 15:30:00] | [15m] | [KXBTC15M-T80000] | [yes] | [2] | [$0.54] | [Bullish momentum]"
    assert expected_console in captured.out

    # Check JSONL file content
    log_file = tmp_path / "executions_exec_log_test.jsonl"
    lines = log_file.read_bytes().strip().split(b"\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["_type"] == "execution"
    assert record["order_id"] == "ord_100"
    assert record["fill_price"] == "0.54"
    assert record["side"] == "yes"


def test_log_settlement(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Test log_settlement output to console and JSONL file."""
    now = datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
    result = SettlementResult(
        ticker="KXBTC15M-T80000",
        side=OrderSide.YES,
        size=2,
        entry_price=Decimal("0.54"),
        settlement_price=Decimal("1.00"),
        outcome="win",
        pnl=Decimal("0.92"),
        timestamp=now,
    )

    with ExecutionLogger(data_dir=tmp_path, session_id="settle_test") as logger:
        logger.log_settlement(result)

    captured = capsys.readouterr()
    expected_console = "[2025-01-01 16:00:00] | SETTLEMENT | [KXBTC15M-T80000] | [yes] | [2] | [win] | P&L: $0.92"
    assert expected_console in captured.out

    log_file = tmp_path / "executions_settle_test.jsonl"
    lines = log_file.read_bytes().strip().split(b"\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["_type"] == "settlement"
    assert record["outcome"] == "win"
    assert record["pnl"] == "0.92"


def test_log_pnl_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Test log_pnl_summary formatting and JSONL logging."""
    snapshot = PnLSnapshot(
        starting_balance=Decimal("100.00"),
        current_balance=Decimal("125.50"),
        total_realized_pnl=Decimal("25.50"),
        total_unrealized_pnl=Decimal("-2.00"),
        total_equity=Decimal("123.50"),
        open_positions=1,
        total_trades=10,
        wins=7,
        losses=3,
        win_rate=Decimal("0.70"),
    )

    with ExecutionLogger(data_dir=tmp_path, session_id="pnl_test") as logger:
        logger.log_pnl_summary(snapshot)

    captured = capsys.readouterr()
    assert "P&L SUMMARY" in captured.out
    assert "Balance:    $125.50" in captured.out
    assert "Win Rate: 70.0%" in captured.out

    # Test win_rate None case
    snapshot_no_win_rate = snapshot.model_copy(update={"win_rate": None})
    with ExecutionLogger(data_dir=tmp_path, session_id="pnl_none_test") as logger:
        logger.log_pnl_summary(snapshot_no_win_rate)

    captured2 = capsys.readouterr()
    assert "Win Rate: 0.0%" in captured2.out

    log_file = tmp_path / "executions_pnl_test.jsonl"
    lines = log_file.read_bytes().strip().split(b"\n")
    record = json.loads(lines[0])
    assert record["_type"] == "pnl_snapshot"
    assert record["current_balance"] == "125.50"


def test_format_positions_table(tmp_path: Path):
    """Test format_positions_table for both empty and populated lists."""
    logger = ExecutionLogger(data_dir=tmp_path, session_id="table_test")

    # Empty positions
    empty_table = logger.format_positions_table([])
    assert "No open positions" in empty_table
    assert "Ticker" in empty_table

    # Populated positions
    pos1 = Position(
        ticker="KXBTC15M-T80000",
        side=OrderSide.YES,
        size=3,
        avg_entry_price=Decimal("0.50"),
        current_price=Decimal("0.65"),
        unrealized_pnl=Decimal("0.45"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )
    pos2 = Position(
        ticker="KXBTC15M-T80100",
        side=OrderSide.NO,
        size=2,
        avg_entry_price=Decimal("0.40"),
        current_price=None,
        unrealized_pnl=Decimal("-0.20"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )
    pos3 = Position(
        ticker="KXBTC15M-T80200",
        side=OrderSide.YES,
        size=1,
        avg_entry_price=Decimal("0.50"),
        current_price=Decimal("0.50"),
        unrealized_pnl=Decimal("0.00"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )

    table = logger.format_positions_table([pos1, pos2, pos3])
    assert "KXBTC15M-T80000" in table
    assert "+$0.45" in table
    assert "—" in table  # for current_price None
    assert "-$0.20" in table
    assert "$0.00" in table

    logger.close()


def test_write_jsonl_when_file_closed(tmp_path: Path):
    """Test that writing to closed file is safely handled without raising errors."""
    logger = ExecutionLogger(data_dir=tmp_path, session_id="closed_test")
    logger.close()

    # Attempting _write_jsonl after close should be a no-op
    logger._write_jsonl({"test": "data"})
    assert logger._file is None
