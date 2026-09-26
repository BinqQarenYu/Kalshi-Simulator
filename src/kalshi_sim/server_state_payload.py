"""Full State Payload Builder for WebSocket Broadcast.

Extracted from server.py to reduce monolith size while maintaining
backward-compatible imports via re-exports in server.py.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from kalshi_sim.schemas import (
    CryptoAsset,
    get_asset_config,
)

logger = logging.getLogger("kalshi_sim.server_state_payload")


# ---------------------------------------------------------------------------
# Module-Level Init (Dependency Injection)
# ---------------------------------------------------------------------------
_state_getter: Callable[[], Any] | None = None
_resolve_active_market_fn: Callable[..., Any] | None = None
_resolve_bot_instance_fn: Callable[[str], Any] | None = None
_TIMEFRAME_CONFIGS: dict | None = None


def init_state_payload(
    state_getter: Callable[[], Any],
    resolve_active_market_fn: Callable[..., Any],
    resolve_bot_instance_fn: Callable[[str], Any],
    timeframe_configs: dict,
) -> None:
    """Inject runtime dependencies from the main server module."""
    global _state_getter, _resolve_active_market_fn, _resolve_bot_instance_fn, _TIMEFRAME_CONFIGS
    _state_getter = state_getter
    _resolve_active_market_fn = resolve_active_market_fn
    _resolve_bot_instance_fn = resolve_bot_instance_fn
    _TIMEFRAME_CONFIGS = timeframe_configs


def _get_state() -> Any:
    assert _state_getter is not None, "server_state_payload not initialized"
    return _state_getter()


def _build_full_state_payload() -> dict[str, Any]:
    """Serialize full real-time state for UI consumption."""
    state = _get_state()
    now_utc = datetime.now(timezone.utc)
    active_m, remaining_secs, strike_dec, target_time_str, time_window_str = _resolve_active_market_fn(now_utc)

    ticker = state.active_ticker
    book = state.orderbook.get_book(ticker)

    # Best bid / ask in dollars & cents
    if book and (book.best_yes_bid or book.best_no_bid):
        best_yes_bid = float(book.best_yes_bid) if book.best_yes_bid else (float(Decimal("1.0") - book.best_no_ask) if book.best_no_ask else 0.0)
        best_yes_ask = float(book.best_yes_ask) if book.best_yes_ask else (float(Decimal("1.0") - book.best_no_bid) if book.best_no_bid else 0.0)
        best_no_bid = float(book.best_no_bid) if book.best_no_bid else (float(Decimal("1.0") - book.best_yes_ask) if book.best_yes_ask else 0.0)
        best_no_ask = float(book.best_no_ask) if book.best_no_ask else (float(Decimal("1.0") - book.best_yes_bid) if book.best_yes_bid else 0.0)
    elif state.mode == "live":
        best_yes_bid = 0.0
        best_yes_ask = 0.0
        best_no_bid = 0.0
        best_no_ask = 0.0
    else:
        # Dynamic digital option fair probability with time-to-expiry decay (Strictly MOCK mode only)
        diff_val = float(state.current_btc_price - strike_dec)
        tf_val = state.active_timeframe.value if hasattr(state.active_timeframe, "value") else str(state.active_timeframe)
        cycle_duration = 300.0 if tf_val == "5m" else (3600.0 if tf_val == "1h" else 900.0)
        tau_fraction = min(1.0, max(5, remaining_secs) / cycle_duration)
        if state.active_asset == CryptoAsset.BTC:
            scale = max(25.0, 105.0 * math.sqrt(tau_fraction)) if tf_val == "5m" else max(35.0, 180.0 * math.sqrt(tau_fraction))
        else:
            active_cfg = get_asset_config(state.active_asset)
            base_diff = float(active_cfg.min_spot_diff)
            multiplier = (105.0 / 25.0) if tf_val == "5m" else (180.0 / 35.0)
            scale = max(base_diff, base_diff * multiplier * math.sqrt(tau_fraction))
        z = diff_val / scale
        try:
            p_yes = 1.0 / (1.0 + math.exp(-z))
        except OverflowError:
            p_yes = 1.0 if z > 0 else 0.0
        best_yes_bid = round(max(0.01, min(0.98, p_yes - 0.01)), 2)
        best_yes_ask = round(min(0.99, max(0.02, p_yes + 0.01)), 2)
        best_no_bid = round(max(0.01, min(0.98, (1.0 - p_yes) - 0.01)), 2)
        best_no_ask = round(min(0.99, max(0.02, (1.0 - p_yes) + 0.01)), 2)

    # Calculate mid-market probability (%)
    if best_yes_bid > 0 and best_yes_ask > 0:
        market_chance_pct = round(((best_yes_bid + best_yes_ask) / 2.0) * 100.0, 1)
    elif best_yes_ask > 0:
        market_chance_pct = round(best_yes_ask * 100.0, 1)
    elif state.mode == "live":
        market_chance_pct = 0.0
    else:
        market_chance_pct = 50.0

    # L2 Ladder (formatted in cents matching Kalshi UI: e.g. 52.0¢, 51.0¢, etc.)
    ladder: list[dict[str, Any]] = []
    if book and (book.yes_book or book.no_book):
        all_quantities = [float(q) for q in list(book.yes_book.values()) + list(book.no_book.values())]
        max_qty = max(all_quantities) if all_quantities else 1000.0

        for pr, qty in sorted(book.yes_book.items(), key=lambda x: x[0], reverse=True)[:8]:
            pr_cents = float(pr * 100)
            ladder.append({
                "side": "yes",
                "price_cents": f"{pr_cents:.1f}¢",
                "price_raw": float(pr),
                "contracts": int(qty),
                "total": f"${float(pr * qty):,.0f}",
                "depth_pct": min(100, max(8, int((float(qty) / max_qty) * 100))),
            })
        for pr, qty in sorted(book.no_book.items(), key=lambda x: x[0], reverse=True)[:8]:
            pr_cents = float(pr * 100)
            ladder.append({
                "side": "no",
                "price_cents": f"{pr_cents:.1f}¢",
                "price_raw": float(pr),
                "contracts": int(qty),
                "total": f"${float(pr * qty):,.0f}",
                "depth_pct": min(100, max(8, int((float(qty) / max_qty) * 100))),
            })

    # AI signals — decoupled background worker (<0.001ms instant memory fetch)
    ai_data = state.ai_worker.get_cached_signals()

    # Portfolio state
    portfolio_data: dict[str, Any] = {
        "balance": float(state.starting_capital),
        "equity": float(state.starting_capital),
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "win_rate": 0.0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "circuit_breaker_tripped": False,
        "current_drawdown_pct": 0.0,
        "positions": [],
        "settlements": [],
        "open_orders": [],
        "resting_orders": [],
    }

    if state.mode == "live" and state.live_portfolio:
        lp = state.live_portfolio
        live_cash = float(lp.get("balance_dollars", 28.21))
        live_equity = round(live_cash + float(lp.get("payout_pending", 0.0)), 2)
        live_reports = [r for r in state.win_loss_reports if r.get("execution_mode") == "live" or r.get("mode") == "live"]
        live_wins = sum(1 for r in live_reports if r.get("outcome") == "WIN")
        live_losses = sum(1 for r in live_reports if r.get("outcome") == "LOSS")
        live_trades = live_wins + live_losses
        live_wr = (live_wins / live_trades * 100.0) if live_trades > 0 else 0.0
        live_realized_pnl = sum(float(r.get("pnl", 0.0)) for r in live_reports)
        portfolio_data["realized_pnl"] = round(live_realized_pnl, 2)
        portfolio_data["win_rate"] = round(live_wr, 1)
        portfolio_data["total_trades"] = live_trades
        portfolio_data["wins"] = live_wins
        portfolio_data["losses"] = live_losses
        portfolio_data["circuit_breaker_tripped"] = False
        portfolio_data["current_drawdown_pct"] = 0.0
        portfolio_data["positions"] = [
            {
                "ticker": p.get("ticker", ""),
                "side": p.get("side", "yes"),
                "size": p.get("position", 0),
                "entry_price": float(p.get("entry_price", 0.50)),
                "current_price": float(p.get("current_price", best_yes_ask or 0.50)),
                "unrealized_pnl": float(p.get("unrealized_pnl", 0.0)),
            }
            for p in lp.get("positions", [])
        ]
    elif state.sim_agent and state.sim_agent.portfolio:
        p = state.sim_agent.portfolio
        snap = p.get_pnl_snapshot()
        portfolio_data["balance"] = float(p.balance)
        portfolio_data["equity"] = float(snap.total_equity)
        portfolio_data["realized_pnl"] = float(snap.total_realized_pnl)
        portfolio_data["unrealized_pnl"] = float(snap.total_unrealized_pnl)
        portfolio_data["win_rate"] = float(snap.win_rate * 100) if snap.win_rate is not None else 0.0
        portfolio_data["total_trades"] = snap.total_trades
        portfolio_data["wins"] = snap.wins
        portfolio_data["losses"] = snap.losses
        portfolio_data["circuit_breaker_tripped"] = p._circuit_breaker_tripped
        portfolio_data["current_drawdown_pct"] = 0.0
        portfolio_data["positions"] = [
            {
                "ticker": pos.ticker,
                "side": pos.side.value,
                "size": pos.size,
                "entry_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price or pos.avg_entry_price),
                "unrealized_pnl": float(pos.unrealized_pnl),
            }
            for pos in p.get_all_positions()
        ]
        portfolio_data["settlements"] = [
            {
                "ticker": s.ticker,
                "side": s.side.value,
                "size": s.size,
                "entry_price": float(s.entry_price),
                "settlement_price": float(s.settlement_price),
                "outcome": s.outcome,
                "pnl": float(s.pnl),
                "timestamp": s.timestamp.strftime("%H:%M:%S"),
            }
            for s in reversed(p.get_settlement_history()[-10:])
        ]

    # Resting orders
    if state.sim_agent and state.sim_agent._simulator:
        orders_list = [
            {
                "order_id": o.order_id,
                "ticker": o.ticker,
                "side": o.side.value,
                "size": o.size,
                "limit_price": float(o.limit_price) if o.limit_price else 0.0,
                "timeframe": o.timeframe.value,
                "status": o.status,
                "created_at": o.created_at.strftime("%H:%M:%S"),
            }
            for o in (state.sim_agent._simulator.get_all_resting_orders())
        ]
        portfolio_data["resting_orders"] = orders_list
        portfolio_data["open_orders"] = orders_list

    # Calculate BTC spot delta from strike (Prioritizing official CF Benchmarks)
    if state.cf_sync and state.cf_sync.is_connected:
        cf_p = state.cf_sync.get_price(state.active_asset)
        if cf_p > Decimal("0.00"):
            state.current_btc_price = cf_p
            cf_twap = state.cf_sync.get_twap(state.active_asset)
            if cf_twap:
                state.twap_60s_price = cf_twap

    # Use TWAP for settlement parity diff calculation if available
    btc_spot = float(state.twap_60s_price) if state.twap_60s_price is not None else float(state.current_btc_price)
    s_flt = float(strike_dec)
    diff = btc_spot - s_flt
    diff_pct = (diff / s_flt) * 100.0 if s_flt > 0.0 else 0.0

    cfg = _TIMEFRAME_CONFIGS.get(state.active_timeframe, {})
    asset_cfg = get_asset_config(state.active_asset)
    title = f"{asset_cfg.name} {state.active_timeframe.value}"
    series = asset_cfg.series_ticker_15m

    # -----------------------------------------------------------------------
    # Dual-ONNX Telemetry & 4-Pillar Pre-Flight Gates
    # -----------------------------------------------------------------------
    abs_diff = abs(diff)
    required_moat = 47.60  # 1.36x Sweet spot
    moat_floor = 40.25     # 1.15x Floor
    moat_ceiling = 75.25   # 2.15x Ceiling
    moat_pass = abs_diff >= moat_floor
    moat_status = "PASS" if moat_pass else "VETO"
    moat_reason = (
        f"Separation ${abs_diff:.2f} >= ${moat_floor:.2f} (Floor)"
        if moat_pass
        else f"Strike Noise Trap: |Diff| ${abs_diff:.2f} < Min Moat ${moat_floor:.2f}"
    )

    vpin_val = float(ai_data.get("vpin", 0.15))
    vpin_pass = vpin_val < 0.60
    vpin_status = "PASS" if vpin_pass else "VETO"
    vpin_reason = (
        f"Flow toxicity safe ({vpin_val:.2f} < 0.60)"
        if vpin_pass
        else f"High Toxicity Flow Veto ({vpin_val:.2f} >= 0.60)"
    )

    cycle_locked = False
    if state.sim_agent and hasattr(state.sim_agent, "_guardrails"):
        cycle_key = state.active_ticker
        cycle_locked = cycle_key in state.sim_agent._guardrails._cycle_locks
    cycle_status = "LOCKED" if cycle_locked else "READY"
    cycle_reason = "1 trade per cycle lock active" if cycle_locked else "Cycle ready for execution"

    ev_val = float(ai_data.get("expected_value", ai_data.get("ev_yes", 0.0)))
    edge_val = float(ai_data.get("statistical_edge", ai_data.get("edge_yes", 0.0)))
    rec_side = ai_data.get("recommended_side", "wait")
    edge_pass = (edge_val >= 0.05 or ev_val >= 0.04) and (rec_side in ("yes", "no"))
    edge_status = "PASS" if edge_pass else "WAIT"
    edge_reason = (
        f"EV +${ev_val:.2f} / Edge {edge_val * 100:.1f}%"
        if edge_pass
        else "Waiting for statistical edge > 5%"
    )

    preflight_gates = {
        "moat_gate": {
            "status": moat_status,
            "label": "Dynamic Moat",
            "current_diff": round(diff, 2),
            "abs_diff": round(abs_diff, 2),
            "required_moat": required_moat,
            "floor": moat_floor,
            "sweet_spot": required_moat,
            "ceiling": moat_ceiling,
            "reason": moat_reason,
        },
        "vpin_gate": {
            "status": vpin_status,
            "label": "VPIN Safety",
            "current_vpin": round(vpin_val, 3),
            "threshold": 0.60,
            "reason": vpin_reason,
        },
        "cycle_lock_gate": {
            "status": cycle_status,
            "label": "Cycle Lock",
            "locked": cycle_locked,
            "reason": cycle_reason,
        },
        "edge_gate": {
            "status": edge_status,
            "label": "Edge / EV",
            "edge_pct": round(edge_val * 100.0, 1),
            "ev": round(ev_val, 2),
            "reason": edge_reason,
        },
    }

    dual_bot = getattr(state, "dual_onnx_bot", None)
    dual_telemetry = {
        "regime": ai_data.get("regime", "CHOP_WAIT"),
        "action": ai_data.get("action", "HOLD"),
        "side": ai_data.get("recommended_side", "wait"),
        "quolas_signal": ai_data.get("quolas_signal", ai_data.get("onnx_signal", "WAIT")),
        "quolas_confidence": float(ai_data.get("quolas_confidence", ai_data.get("onnx_confidence", 0.50))),
        "kalshi_signal": ai_data.get("kalshi_signal", "WAIT"),
        "kalshi_confidence": float(ai_data.get("kalshi_confidence", 0.50)),
        "recommended_limit_price": float(ai_data.get("recommended_limit_price", 0.48)),
        "expected_value": float(ai_data.get("expected_value", 0.0)),
        "recommended_contracts": int(ai_data.get("recommended_contracts", 1)),
        "rationale": ai_data.get("rationale", ""),
        "active": state.active_strategy_bot in ("dual_onnx", "the_onnx_strategy"),
        # The 5 Strategy Execution Dials
        "brain_priority_mode": getattr(dual_bot, "brain_priority_mode", "TREND_ALIGNED_SCALP"),
        "contract_scaling_mode": getattr(dual_bot, "contract_scaling_mode", "TIER_0_STRICT_1"),
        "volatility_floor": float(getattr(dual_bot, "volatility_floor", 10.0)),
        "volatility_ceiling": float(getattr(dual_bot, "volatility_ceiling", 45.0)),
        "entry_discount_depth": float(getattr(dual_bot, "entry_discount_depth", 0.52)),
        "tape_confirmation_ticks": getattr(dual_bot, "tape_confirmation_ticks", 2),
        "taker_cross_ev_threshold": float(getattr(dual_bot, "taker_cross_ev_threshold", 0.08)),
        "dynamic_moat_multiplier": float(getattr(dual_bot, "dynamic_moat_multiplier", 1.15)),
        "current_atr": float(getattr(dual_bot, "current_atr", 14.0)),
        "tape_streak": getattr(dual_bot, "tape_streak", 0),
    }

    macro_bot = getattr(state.sim_agent, "_macro_trend_bot", None) if state.sim_agent else None
    if not macro_bot:
        macro_bot = _resolve_bot_instance_fn("macro_trend_dominion")

    macro_params = macro_bot.get_parameters() if macro_bot and hasattr(macro_bot, "get_parameters") else {}
    learning_diag = macro_bot.learning_engine.get_diagnostics() if macro_bot and hasattr(macro_bot, "learning_engine") else {}

    macro_telemetry = {
        "active": state.active_strategy_bot in ("macro_trend_dominion", "macro_onnx", "macro_trend", "macro_trend_dominion_bot"),
        "strategy_id": "macro_trend_dominion",
        "strategy_name": "Macro Trend Dominion",
        "call": ai_data.get("call", "YES" if ai_data.get("recommended_side") == "yes" else ("NO" if ai_data.get("recommended_side") == "no" else "DONT")),
        "side": ai_data.get("recommended_side", "wait"),
        "confidence_pct": round(float(ai_data.get("confidence_pct", ai_data.get("ai_prob", 0.50) * 100.0)), 1),
        "limit_price_cents": int(macro_params.get("limit_price_cents", 52)),
        "limit_price": float(macro_params.get("limit_price_cents", 52)) / 100.0,
        "expected_value": float(ai_data.get("expected_value", 0.0)),
        "net_edge_pct": float(ai_data.get("net_edge_pct", ai_data.get("statistical_edge", 0.0) * 100.0)),
        "recommended_contracts": int(ai_data.get("recommended_contracts", 1)),
        "macro_trend": "BULL" if diff > 0 else "BEAR",
        "hmm_regime": str(getattr(getattr(state, "hmm_brain", None), "current_regime", "UNKNOWN")),
        "spot_signal": ai_data.get("quolas_signal", ai_data.get("onnx_signal", "WAIT")),
        "spot_confidence": float(ai_data.get("quolas_confidence", ai_data.get("onnx_confidence", 0.50))),
        "kalshi_signal": ai_data.get("kalshi_signal", "WAIT"),
        "kalshi_confidence": float(ai_data.get("kalshi_confidence", 0.50)),
        "rationale": ai_data.get("rationale", ""),
        "brier_score": learning_diag.get("rolling_brier_score", 0.25),
        "brier_shrinkage_factor": learning_diag.get("brier_shrinkage_factor", 1.0),
        "active_price_cap": learning_diag.get("active_price_cap", 0.52),
        "pruned_deciles": learning_diag.get("pruned_deciles", []),
        "failure_counts": learning_diag.get("failure_counts", {}),
        "parameters": macro_params,
    }

    payload = {
        "timestamp": now_utc.isoformat(),
        "market": {
            "active_asset": state.active_asset.value,
            "active_asset_name": asset_cfg.name,
            "active_asset_decimals": asset_cfg.price_decimals,
            "cf_indices": state.cf_sync.get_all_state() if state.cf_sync else {},
            "title": title,
            "series": series,
            "ticker": state.active_ticker,
            "target_strike": float(strike_dec),
            "target_strike_str": asset_cfg.format_price(strike_dec),
            "target_time_str": target_time_str,
            "time_window_str": time_window_str,
            "current_btc_price": btc_spot,
            "current_btc_price_str": asset_cfg.format_price(btc_spot),
            "diff": round(diff, asset_cfg.price_decimals),
            "diff_pct": round(diff_pct, 3),
            "diff_str": asset_cfg.format_diff(diff, diff_pct),
            "expiry_countdown_seconds": remaining_secs,
            "expiry_countdown_str": f"{remaining_secs // 60:02d}:{remaining_secs % 60:02d}",
            "timeframe": state.active_timeframe.value,
            "market_chance_pct": market_chance_pct,
            "volume_24h_str": state.volume_24h_str,
            "best_yes_ask": round(best_yes_ask, 3),
            "best_yes_bid": round(best_yes_bid, 3),
            "best_no_ask": round(best_no_ask, 3),
            "best_no_bid": round(best_no_bid, 3),
            "yes_cents_str": f"{best_yes_ask * 100:.1f}¢",
            "no_cents_str": f"{best_no_ask * 100:.1f}¢",
            "twap_60s_price": float(state.twap_60s_price) if state.twap_60s_price is not None else None,
            "is_twap_active": bool(state.twap_60s_price is not None),
        },

        "chart": list(state.price_history)[-900:],
        "trade_tape": list(state.trade_tape)[-15:],
        "orderbook_ladder": ladder,
        "ai_signals": ai_data,
        "portfolio": portfolio_data,
        "live_portfolio": state.live_portfolio,
        "win_loss_reports": state.win_loss_reports[:15],
        "memory_profile": {
            "total_hot_ticks": state.memory_manager.get_memory_profile().total_hot_ticks,
            "total_offloaded_ticks": state.memory_manager.get_memory_profile().total_offloaded_ticks,
            "estimated_hot_memory_kb": round(state.memory_manager.get_memory_profile().estimated_hot_memory_kb, 1),
            "is_pressure_critical": state.memory_manager.get_memory_profile().is_pressure_critical,
        },
        "system_resources": state.system_governor.get_resource_metrics().to_dict(),
        "settings": {
            "ai_auto_trade": state.ai_auto_trade,
            "active_strategy_bot": state.active_strategy_bot,
            "bot_arm_states": getattr(state, "bot_arm_states", {}),
            "bot_certified": state.bot_auditor.is_certified(state.active_strategy_bot),
            "bot_sealed": state.bot_auditor.has_seal_of_excellence(state.active_strategy_bot),
            "mode": state.mode,
            "timeframe": state.active_timeframe.value,
            "domination_discount_price": float(state.domination_discount_price),
            "standalone_lock_active": False,
            "standalone_sync_active": False,
            "lock_holder": None,
        },
        "bot_audit_status": {
            "active_bot": state.active_strategy_bot,
            "is_certified": state.bot_auditor.is_certified(state.active_strategy_bot),
            "is_sealed": state.bot_auditor.has_seal_of_excellence(state.active_strategy_bot),
            "report": state.bot_auditor.get_certification(state.active_strategy_bot).to_dict() if state.bot_auditor.get_certification(state.active_strategy_bot) else None,
            "seal": state.bot_auditor.get_seal(state.active_strategy_bot).to_dict() if state.bot_auditor.get_seal(state.active_strategy_bot) else None,
        },
        "seal_of_excellence": state.bot_auditor.get_all_seals(),
        "integrity_status": state.integrity_agent.get_latest_status(),
        "compliance_status": state.law_order_agent.get_compliance_status(),
        "guardrails_status": state.guardrails_agent.get_status(),
        "token_credit_status": state.token_credit_agent.get_status(),
        "btc_orderflow": state.btc_orderflow_feed.get_orderflow_summary() if hasattr(state, "btc_orderflow_feed") and state.btc_orderflow_feed else None,
        "continuous_training": state.continuous_trainer.get_status() if hasattr(state, "continuous_trainer") and state.continuous_trainer else None,
        "hmm_macro_regime": state.hmm_brain.get_status() if hasattr(state, "hmm_brain") and state.hmm_brain else None,
        "dual_onnx_telemetry": dual_telemetry,
        "macro_trend_dominion_telemetry": macro_telemetry,
        "preflight_gates": preflight_gates,
    }

    # SECURITY: Audit state payload for private keys or sensitive credential leaks prior to WebSocket broadcast
    if hasattr(state, "law_order_agent") and state.law_order_agent:
        audit_res = state.law_order_agent.audit_credential_security(payload)
        if audit_res.status == "FAIL":
            logger.critical("[SECURITY ALERT] Blocked state broadcast payload due to credential leak!")
            raise ValueError(f"State payload security audit failed: {audit_res.message}")

    return payload
