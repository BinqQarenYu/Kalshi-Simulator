import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from kalshi_sim.schemas import OrderSide, SimulatedFill, Timeframe, MarketInfo, MarketStatus, TickerUpdate
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.settlement import check_expirations, settle_position
from kalshi_sim.simulation_agent import SimulationAgent
from kalshi_sim.server import record_win_loss_event_report, _matches_bot_id


def test_dual_onnx_expiration_and_settlement():
    """Verify that _portfolio_dual_onnx positions are recognized by check_expirations and settle correctly."""
    mgr = OrderBookManager()
    agent = SimulationAgent(orderbook_manager=mgr, timeframes=[Timeframe.FIFTEEN_MIN])
    agent.set_active_strategy("dual_onnx")
    assert agent.active_strategy_bot == "dual_onnx"
    assert agent.portfolio is agent._portfolio_dual_onnx

    # Open a simulated position in _portfolio_dual_onnx
    ticker = "KXBTC15M-26SEP091815-15"
    fill = SimulatedFill(
        order_id="test_dual_1",
        ticker=ticker,
        side=OrderSide.YES,
        size=1,
        fill_price=Decimal("0.48"),
        cost=Decimal("0.48"),
        fee=Decimal("0.00"),
        slippage=Decimal("0.00"),
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    agent._portfolio_dual_onnx.open_position(fill, Timeframe.FIFTEEN_MIN)
    assert len(agent._portfolio_dual_onnx.open_positions) == 1

    # Populate market cache with an expired market
    close_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    minfo = MarketInfo(
        ticker=ticker,
        series_ticker="KXBTC15M",
        title="Bitcoin Up by 15M",
        subtitle="",
        status=MarketStatus.CLOSED,
        close_time=close_time,
        expiration_time=close_time,
        floor_strike=Decimal("78000.00"),
        cap_strike=None,
        strike_type="greater",
    )
    agent.update_market_cache({ticker: minfo})

    # Test check_expirations finds the position
    expired = check_expirations(
        positions=agent._portfolio_dual_onnx.open_positions,
        markets=agent._market_cache,
        current_time=datetime.now(timezone.utc),
    )
    assert ticker in expired

    # Set spot price getter returning above strike ($79,000 > $78,000) -> YES wins
    agent._spot_price_getter = lambda: Decimal("79000.00")
    dummy_tick = TickerUpdate(market_ticker=ticker, yes_bid=Decimal("0.99"), no_bid=Decimal("0.01"))

    # Settle
    agent.settle_expired_market(ticker, minfo, dummy_tick)

    # Position must be popped and open positions cleared (unchoked)
    assert len(agent._portfolio_dual_onnx.open_positions) == 0
    assert agent._portfolio_dual_onnx.get_position(ticker) is None

    # Settlement history must record the win
    settlements = agent._portfolio_dual_onnx.get_settlement_history()
    assert len(settlements) == 1
    assert settlements[0].outcome == "win"
    assert settlements[0].pnl == Decimal("0.52")


def test_dual_onnx_report_bot_matching():
    """Verify that _matches_bot_id accurately correlates onnx_macro_v2 to dual_onnx."""
    rep = {
        "report_id": "WLR-TEST-001",
        "bot_type": "onnx_macro_v2",
        "bot_id": "onnx_macro_v2",
        "strategy_id": "onnx_macro_v2",
        "ai_rationale": "Dual-Brain Cross-Market Arbitrage",
        "execution_mode": "simulated",
    }
    assert _matches_bot_id(rep, "dual_onnx") is True
    assert _matches_bot_id(rep, "onnx_macro_v2") is True
    assert _matches_bot_id(rep, "the_onnx_strategy") is True
    assert _matches_bot_id(rep, "3_step_domination_bot") is False
