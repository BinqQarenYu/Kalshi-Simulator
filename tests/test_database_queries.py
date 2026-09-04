"""Unit and integration tests for HistoricalQueryService and REST analytics endpoints."""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from kalshi_sim.db.connection import DatabaseManager
from kalshi_sim.db.queries import HistoricalQueryService
from kalshi_sim.db.writer import DatabaseWriter
from kalshi_sim.server import app


@pytest.mark.anyio
async def test_historical_query_service_crud_and_metrics(tmp_path: Path) -> None:
    """Test HistoricalQueryService retrieval and institutional math calculations."""
    db_path = tmp_path / "test_queries.db"
    db_mgr = DatabaseManager(db_path=db_path)
    writer = DatabaseWriter(db_manager=db_mgr, batch_size=5, flush_interval_seconds=0.01)
    await writer.start()

    # 1. Enqueue test trades
    writer.enqueue_trade(
        trade_id="tr_001",
        ticker="KXBTC15M-T78650",
        side="yes",
        size=10,
        price=0.45,
        gross_value=4.50,
        fees=0.10,
        timeframe="15m",
        execution_mode="simulated",
    )
    writer.enqueue_trade(
        trade_id="tr_002",
        ticker="KXBTC5M-T78600",
        side="no",
        size=20,
        price=0.55,
        gross_value=11.0,
        fees=0.20,
        timeframe="5m",
        execution_mode="live",
    )

    # 2. Enqueue settlements (1 win +$5.50, 1 loss -$4.50)
    writer.enqueue_settlement(
        settlement_id="st_001",
        ticker="KXBTC15M-T78650",
        side="yes",
        size=10,
        entry_price=0.45,
        settlement_price=1.0,
        outcome="win",
        pnl=5.50,
        balance_after=10005.50,
    )
    writer.enqueue_settlement(
        settlement_id="st_002",
        ticker="KXBTC5M-T78600",
        side="no",
        size=10,
        entry_price=0.45,
        settlement_price=0.0,
        outcome="loss",
        pnl=-4.50,
        balance_after=10001.00,
    )

    # 3. Enqueue equity snapshots
    writer.enqueue_equity_snapshot(
        balance=10005.50,
        equity=10005.50,
        realized_pnl=5.50,
        unrealized_pnl=0.0,
        drawdown_pct=0.0,
        win_rate=100.0,
        total_trades=1,
    )
    writer.enqueue_equity_snapshot(
        balance=10001.00,
        equity=10001.00,
        realized_pnl=1.00,
        unrealized_pnl=0.0,
        drawdown_pct=0.04,
        win_rate=50.0,
        total_trades=2,
    )

    # 4. Enqueue AI prediction
    writer.enqueue_ai_prediction(
        ticker="KXBTC15M-T78650",
        p_up=0.75,
        p_down=0.15,
        p_wait=0.10,
        vpin=0.15,
        ev_yes=0.25,
        ev_no=-0.35,
        recommended_side="yes",
        rationale="Strong positive edge",
    )

    await writer.stop()

    query_service = HistoricalQueryService(db_manager=db_mgr)

    # Test Trades query with filters
    all_trades = await query_service.get_trades()
    assert len(all_trades) == 2

    live_trades = await query_service.get_trades(execution_mode="live")
    assert len(live_trades) == 1
    assert live_trades[0]["trade_id"] == "tr_002"

    tf_trades = await query_service.get_trades(timeframe="15m")
    assert len(tf_trades) == 1
    assert tf_trades[0]["trade_id"] == "tr_001"

    # Test Settlements query
    settlements = await query_service.get_settlements()
    assert len(settlements) == 2

    # Test Equity Curve query
    equity_curve = await query_service.get_equity_curve()
    assert len(equity_curve) == 2

    # Test AI Predictions query
    ai_preds = await query_service.get_ai_predictions()
    assert len(ai_preds) == 1
    assert ai_preds[0]["recommended_side"] == "yes"

    # Test Metrics computation
    metrics = await query_service.compute_portfolio_metrics()
    assert metrics["total_trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["win_rate_pct"] == 50.0
    assert metrics["gross_profit"] == 5.50
    assert metrics["gross_loss"] == 4.50
    assert metrics["profit_factor"] == 1.22  # 5.50 / 4.50 = 1.222...
    assert metrics["total_fees_paid"] == 0.30
    assert metrics["total_realized_pnl"] == 1.00
    assert metrics["net_pnl"] == 0.70
    assert metrics["current_equity"] == 10001.00
    assert "sharpe_ratio" in metrics
    assert "sortino_ratio" in metrics
    assert "calmar_ratio" in metrics


def test_server_history_endpoints() -> None:
    """Test FastAPI REST /api/history/* endpoints."""
    with TestClient(app) as client:
        # 1. Trades endpoint
        res = client.get("/api/history/trades")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # 2. Settlements endpoint
        res = client.get("/api/history/settlements")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # 3. Equity curve endpoint
        res = client.get("/api/history/equity-curve")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # 4. AI predictions endpoint
        res = client.get("/api/history/ai-predictions")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # 5. Metrics endpoint
        res = client.get("/api/history/metrics")
        assert res.status_code == 200
        data = res.json()
        assert "win_rate_pct" in data
        assert "profit_factor" in data
        assert "sharpe_ratio" in data
        assert "sortino_ratio" in data

        # 6. Export endpoints
        res_trade_csv = client.get("/api/history/trades/export.csv")
        assert res_trade_csv.status_code == 200
        assert "text/csv" in res_trade_csv.headers["content-type"]

        res_exec_summary = client.get("/api/reports/executive-summary/export.json")
        assert res_exec_summary.status_code == 200
        assert "application/json" in res_exec_summary.headers["content-type"]
        assert "combined_portfolio_metrics" in res_exec_summary.json()

        # 7. Batch Delete endpoint test
        res_batch = client.post("/api/history/batch-delete", json={"table": "trades", "ids": [999999]})
        assert res_batch.status_code == 200
        assert res_batch.json()["success"] is True

