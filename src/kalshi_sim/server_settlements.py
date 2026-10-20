"""Win/Loss Event Reporting & Live Settlement Synchronization.

Extracted from server.py to reduce monolith size while maintaining
backward-compatible imports via re-exports in server.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.db import get_db, get_db_writer, get_eth_db, get_eth_db_writer
from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import (
    CryptoAsset,
    OrderSide,
    SettlementResult,
    detect_asset_from_ticker,
)

logger = logging.getLogger("kalshi_sim.server_settlements")


# ---------------------------------------------------------------------------
# Module-Level Init (Dependency Injection)
# ---------------------------------------------------------------------------
_state_getter: Callable[[], Any] | None = None
_resolve_bot_instance_fn: Callable[[str], Any] | None = None


def init_server_settlements(
    state_getter: Callable[[], Any],
    resolve_bot_instance_fn: Callable[[str], Any],
) -> None:
    """Inject runtime dependencies from the main server module."""
    global _state_getter, _resolve_bot_instance_fn
    _state_getter = state_getter
    _resolve_bot_instance_fn = resolve_bot_instance_fn


def _get_state() -> Any:
    assert _state_getter is not None, "server_settlements not initialized"
    return _state_getter()


def _resolve_bot(bot_id: str) -> Any:
    if _resolve_bot_instance_fn:
        return _resolve_bot_instance_fn(bot_id)
    return None


def record_win_loss_event_report(
    ticker: str,
    side: str,
    contracts: int,
    entry_price: Decimal,
    settlement_btc_price: Decimal,
    strike_price: Decimal,
    timeframe: str = "15m",
    ai_confidence: float = 0.75,
    ai_rationale: Optional[str] = None,
    vpin_score: float = 0.15,
    ev_edge: float = 0.08,
    bot_type: Optional[str] = None,
    execution_mode: Optional[str] = None,
    report_id: Optional[str] = None,
    custom_pnl: Optional[Decimal] = None,
    custom_outcome: Optional[str] = None,
    timestamp_utc: Optional[str] = None,
    cycle_time: Optional[str] = None,
    balance_after: Optional[Decimal] = None,
    settlement_spot_price: Optional[Decimal] = None,
    asset: Optional[str] = None,
    bot_parameters: Optional[dict[str, Any]] = None,
    skip_guardrails: bool = False,
) -> dict[str, Any]:
    """Generate and persist a standardized event win/loss report (5m or 15m)."""
    state = _get_state()
    now_utc = datetime.now(timezone.utc)
    if settlement_spot_price is None:
        settlement_spot_price = settlement_btc_price
    if asset is None:
        asset = detect_asset_from_ticker(ticker).value
    if "5M" in ticker.upper() or "5MIN" in ticker.upper():
        timeframe = "5m"
    if not ai_rationale:
        ai_rationale = f"Automated {'5M' if '5m' in str(timeframe).lower() else '15M'} Cycle Execution"
    if not cycle_time:
        et_tz = ZoneInfo("America/New_York")
        et_now = now_utc.astimezone(et_tz)
        hr_now = et_now.hour % 12 or 12
        interval = 5 if "5m" in str(timeframe).lower() else 15
        m_now = (et_now.minute // interval) * interval
        m_next = (m_now + interval) % 60
        hr_next = hr_now if (m_now + interval) < 60 else ((et_now.hour + 1) % 12 or 12)
        ampm_now = "AM" if et_now.hour < 12 else "PM"
        cycle_time = f"{et_now.strftime('%B %d')}, {hr_now}:{m_now:02d} - {hr_next}:{m_next:02d} {ampm_now} ET"

    side_clean = side.lower()
    if custom_outcome is not None:
        outcome = custom_outcome.lower()
        won = (outcome == "win")
        settlement_price = Decimal("1.00") if won else Decimal("0.00")
        if custom_pnl is not None:
            pnl = custom_pnl
            cost = entry_price * Decimal(str(contracts))
            roi_pct = round((pnl / cost * Decimal("100")), 2) if cost > Decimal("0") else Decimal("0.0")
        else:
            pnl = (Decimal("1.00") - entry_price) * Decimal(str(contracts)) if won else - (entry_price * Decimal(str(contracts)))
            cost = entry_price * Decimal(str(contracts))
            roi_pct = round((pnl / cost * Decimal("100")), 2) if cost > Decimal("0") else Decimal("0.0")
    elif side_clean in ("flat", "skip", "veto") or contracts == 0:
        won = False
        outcome = "flat"
        settlement_price = Decimal("0.00")
        pnl = Decimal("0.00")
        roi_pct = Decimal("0.00")
    elif side_clean == "yes":
        won = (settlement_btc_price >= strike_price)
        settlement_price = Decimal("1.00") if won else Decimal("0.00")
        outcome = "win" if won else "loss"
        pnl = (Decimal("1.00") - entry_price) * Decimal(str(contracts)) if won else - (entry_price * Decimal(str(contracts)))
        cost = entry_price * Decimal(str(contracts))
        roi_pct = round((pnl / cost * Decimal("100")), 2) if cost > Decimal("0") else Decimal("0.0")
    else:
        won = (settlement_btc_price < strike_price)
        settlement_price = Decimal("1.00") if won else Decimal("0.00")
        outcome = "win" if won else "loss"
        pnl = (Decimal("1.00") - entry_price) * Decimal(str(contracts)) if won else - (entry_price * Decimal(str(contracts)))
        cost = entry_price * Decimal(str(contracts))
        roi_pct = round((pnl / cost * Decimal("100")), 2) if cost > Decimal("0") else Decimal("0.0")

    bot_type_resolved = bot_type or getattr(state, "active_strategy_bot", "3_step_domination_bot")
    exec_mode_resolved = execution_mode or state.mode

    # Apply PnL to portfolio if executed trade (MOCK/SIMULATED ONLY)
    if balance_after is not None:
        pass
    elif exec_mode_resolved != "live" and state.sim_agent:
        # Route to the matching bot portfolio
        target_p = state.sim_agent._portfolio
        if bot_type_resolved in ("3_step_domination_bot", "domination", "dominion"):
            target_p = getattr(state.sim_agent, "_portfolio_domination", target_p)
        elif bot_type_resolved in ("macro_onnx", "macro_trend_dominion", "macro_trend"):
            target_p = getattr(state.sim_agent, "_portfolio_macro_trend", target_p)
        elif bot_type_resolved in ("dominion_2_bot", "dominion2", "dominion_v2"):
            target_p = getattr(state.sim_agent, "_portfolio_dominion2", target_p)
        elif bot_type_resolved in ("onnx_ml_bot", "onnx_microstructure_bot", "onnx"):
            target_p = getattr(state.sim_agent, "_portfolio_onnx", target_p)
        elif bot_type_resolved in ("dual_onnx", "onnx_macro_v2", "the_onnx_strategy", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot"):
            target_p = getattr(state.sim_agent, "_portfolio_dual_onnx", target_p)

        if target_p and contracts > 0 and side_clean in ("yes", "no"):
            target_p._balance += pnl
            target_p._total_trades += 1
            if won:
                target_p._wins += 1
            else:
                target_p._losses += 1

            settle_res = SettlementResult(
                ticker=ticker,
                side=OrderSide(side_clean),
                size=contracts,
                entry_price=entry_price,
                settlement_price=settlement_btc_price,
                outcome=outcome,
                pnl=pnl,
            )
            target_p._settlement_history.append(settle_res)
            target_p._update_circuit_breaker()
            balance_after = target_p.balance
        else:
            balance_after = target_p.balance if target_p else state.starting_capital
    elif balance_after is None:
        if exec_mode_resolved == "live" and state.order_client:
            live_bal = Decimal("0.0")
            if hasattr(state.order_client, "shard_balances"):
                live_bal = state.order_client.shard_balances.get(2, Decimal("0.0"))
            if live_bal == Decimal("0.0"):
                live_bal = getattr(state.order_client, "last_balance", Decimal("25.00"))
            balance_after = live_bal
        else:
            balance_after = state.starting_capital

    # Resolve active market condition (choppy, stormy, bleed, heal)
    current_cond = "choppy"
    try:
        active_bot = _resolve_bot(bot_type_resolved)
        if active_bot is None and hasattr(state, "bot1_v4_engine"):
            active_bot = state.bot1_v4_engine
        if active_bot and hasattr(active_bot, "wave_classifier"):
            region = getattr(active_bot.wave_classifier, "current_region", "").lower()
            if region in ("chop", "choppy"):
                current_cond = "choppy"
            elif region in ("storm", "stormy"):
                current_cond = "stormy"
            elif region:
                current_cond = region
        elif hasattr(state, "guardrails_agent") and hasattr(state.guardrails_agent, "current_market_condition"):
            current_cond = state.guardrails_agent.current_market_condition
        elif hasattr(state, "hmm_brain") and state.hmm_brain:
            hmm_regime = state.hmm_brain.get_status().get("current_regime", "")
            if hmm_regime == "VOL_EXPANSION":
                current_cond = "stormy"
            elif hmm_regime == "RISK_OFF":
                current_cond = "bleed"
    except Exception:
        pass

    report = {
        "report_id": report_id or f"WLR-{now_utc.strftime('%y%m%d%H%M%S')}-{random.randint(100, 999)}",
        "cycle_time": cycle_time,
        "ticker": ticker,
        "timeframe": timeframe,
        "asset": asset,
        "strike_price": float(strike_price),
        "settlement_btc_price": float(settlement_spot_price),
        "settlement_spot_price": float(settlement_spot_price),
        "bot_side": side_clean,
        "contracts": contracts,
        "entry_price": float(entry_price),
        "settlement_price": float(settlement_price),
        "outcome": outcome,
        "pnl": float(pnl),
        "roi_pct": float(roi_pct),
        "ai_confidence": round(ai_confidence, 3),
        "ai_rationale": ai_rationale,
        "vpin_score": round(vpin_score, 3),
        "ev_edge": round(ev_edge, 3),
        "balance_after": float(balance_after),
        "market_condition": current_cond,
        "bot_type": bot_type_resolved,
        "bot_id": bot_type_resolved,
        "strategy_id": bot_type_resolved,
        "execution_mode": exec_mode_resolved,
        "lane": "LANE 1 (LIVE)" if exec_mode_resolved == "live" else "LANE 2 (SHADOW)",
        "timestamp_utc": timestamp_utc or now_utc.isoformat(),
    }

    # Attach live or resolved bot parameters snapshot for permanent review
    resolved_params = bot_parameters
    if resolved_params is None:
        try:
            bot_inst = _resolve_bot(bot_type_resolved)
            if bot_inst and hasattr(bot_inst, "get_parameters"):
                resolved_params = bot_inst.get_parameters()
        except Exception:
            resolved_params = None

    if resolved_params:
        report["bot_parameters"] = resolved_params

    if str(exec_mode_resolved).lower() == "live":
        state.win_loss_reports.insert(0, report)
        state.save_persisted_reports()
    else:
        logger.info(
            "🧪 [SHADOW/PAPER MODE] Settlement report %s processed in-memory (mode: %s); skipping disk persistence to win_loss_reports.json",
            report.get("report_id"),
            exec_mode_resolved,
        )

    # Determine if ETH asset
    is_eth_asset = (
        str(asset).upper() == "ETH"
        or ticker.upper().startswith("KXETH")
        or "eth" in str(bot_type_resolved).lower()
    )
    db_writer = get_eth_db_writer() if is_eth_asset else get_db_writer()

    # Route persistence to dedicated ETH report store if ETH asset AND live execution mode
    if is_eth_asset and str(exec_mode_resolved).lower() == "live":
        try:
            eth_file = Path("data/eth_win_loss_reports.json")
            eth_file.parent.mkdir(parents=True, exist_ok=True)
            eth_reports = []
            if eth_file.exists():
                try:
                    eth_reports = json.loads(eth_file.read_text(encoding="utf-8"))
                    if not isinstance(eth_reports, list):
                        eth_reports = []
                except Exception:
                    eth_reports = []
            eth_reports.insert(0, report)
            eth_file.write_text(json.dumps(eth_reports, indent=2), encoding="utf-8")
        except Exception as eth_w_exc:
            logger.warning("Could not persist to eth_win_loss_reports.json: %s", eth_w_exc)

    # 4-Region & Multi-Warrior Live Dynamic Feedback Loop
    active_bot = None
    try:
        active_bot = _resolve_bot(bot_type_resolved)
        if active_bot is None and hasattr(state, "bot1_v4_engine"):
            active_bot = state.bot1_v4_engine
        if active_bot and hasattr(active_bot, "record_cycle_settlement"):
            is_win = (str(outcome).strip().lower() == "win")
            active_bot.record_cycle_settlement(is_win)
            logger.info(
                "🌊 [WAVE REGIME SETTLEMENT FEEDBACK] Recorded cycle settlement for %s (Won: %s).",
                bot_type_resolved,
                is_win,
            )
    except Exception as bot_settle_exc:
        logger.debug("[WAVE REGIME SETTLEMENT FEEDBACK] Error recording settlement on bot instance: %s", bot_settle_exc)

    # Feed Continuous Experience Buffer for online sharpening & Platt calibration
    target_exp_buf = getattr(active_bot, "experience_buffer", None) if active_bot else None
    if target_exp_buf is None and hasattr(state, "experience_buffer"):
        target_exp_buf = state.experience_buffer

    if target_exp_buf:
        try:
            exp = target_exp_buf._dict_to_experience(report)
            if exp:
                target_exp_buf.record_settled_cycle(exp)
                logger.info(
                    "[EXPERIENCE_BUFFER] Recalibrated after cycle %s -> %s (PnL: $%s). Brier: %.4f, Platt Alpha: %.2f",
                    ticker, outcome.upper(), pnl, target_exp_buf.brier_score, target_exp_buf.platt_alpha
                )
        except Exception as eb_exc:
            logger.debug("[EXPERIENCE_BUFFER] Error recording cycle settlement: %s", eb_exc)

    if not skip_guardrails and hasattr(state, "guardrails_agent") and state.guardrails_agent:
        # Record settlement in Agent_Guardrails to unlock cycle and track streaks
        state.guardrails_agent.record_cycle_settlement(
            ticker=ticker,
            outcome=outcome,
            pnl=pnl,
            balance_after=balance_after,
            cycle_id=ticker,
            execution_mode=exec_mode_resolved,
        )

    try:
        db_writer.enqueue_settlement(
            settlement_id=report["report_id"],
            ticker=ticker,
            side=side_clean,
            size=contracts,
            entry_price=float(entry_price),
            settlement_price=float(settlement_price),
            outcome=outcome,
            pnl=float(pnl),
            balance_after=float(balance_after),
            bot_type=bot_type_resolved,
            execution_mode=exec_mode_resolved,
        )

        # Checkpoint & Lifecycle Forensics
        twap_val = float(settlement_spot_price)
        twap_div = 0.0
        if hasattr(state, "cfbenchmarks_sync") and state.cfbenchmarks_sync:
            latest_twap = getattr(state.cfbenchmarks_sync, "latest_60s_twap", None)
            if latest_twap is not None:
                twap_val = float(latest_twap)
                twap_div = float(settlement_spot_price) - twap_val

        macro_slope = 0.0
        if active_bot and hasattr(active_bot, "_last_1h_slope"):
            macro_slope = float(getattr(active_bot, "_last_1h_slope", 0.0) or 0.0)

        db_writer.enqueue_lifecycle_forensics(
            trade_id=report["report_id"],
            ticker=ticker,
            side=side_clean,
            entry_price=float(entry_price),
            outcome=outcome.upper(),
            realized_pnl=float(pnl),
            role="MAKER" if float(entry_price) <= 0.48 else "TAKER",
            fee_paid=0.0 if float(entry_price) <= 0.48 else 0.01,
            t1_timestamp=report.get("cycle_time"),
            t1_spot=float(strike_price),
            t1_strike_diff=float(settlement_spot_price - strike_price),
            t1_1h_slope=macro_slope,
            t1_regime=current_cond.upper(),
            t1_vpin=float(vpin_score),
            t2_timestamp=report.get("timestamp_utc"),
            t2_spot=float(settlement_spot_price),
            t2_1h_slope=macro_slope,
            t2_regime=current_cond.upper(),
            t2_vpin=float(vpin_score),
            t3_timestamp=report.get("timestamp_utc"),
            t3_spot=float(settlement_spot_price),
            t3_60s_twap=twap_val,
            twap_vs_spot_divergence=twap_div,
            t3_1h_slope=macro_slope,
            t3_regime=current_cond.upper(),
            bot_type=bot_type_resolved,
        )

        # Failure & Mistake Attribution Autopsy (If Loss)
        if outcome.lower() == "loss":
            twap_div_threshold = 1.50 if is_eth_asset else 15.0
            salv_diff_threshold = 8.50 if is_eth_asset else 85.0
            is_twap_pin = 1 if abs(twap_div) >= twap_div_threshold and ((side_clean == "yes" and float(settlement_spot_price) >= float(strike_price) and twap_val < float(strike_price)) or (side_clean == "no" and float(settlement_spot_price) < float(strike_price) and twap_val >= float(strike_price))) else 0
            is_ct = 1 if ((side_clean == "no" and macro_slope > 0.20) or (side_clean == "yes" and macro_slope < -0.20)) else 0
            
            wave_phys = getattr(active_bot, "_last_wave_physics", None) if active_bot else None
            is_dw = 1 if (wave_phys and getattr(wave_phys, "is_double_wick_meatgrinder", False)) else 0
            w_ratio = getattr(wave_phys, "upper_wick_dollars", 0.0) / max(1.0, getattr(wave_phys, "body_dollars", 1.0)) if wave_phys else 0.0
            
            # Salvage stop check (DEF-03)
            was_salv = 1 if float(entry_price) >= 0.40 and abs(float(settlement_spot_price - strike_price)) >= salv_diff_threshold else 0
            salv_lost = 0.12 * contracts if was_salv else 0.0

            is_whipsaw = 1 if report.get("exit_reason") == "salvage_derisk" and (
                (side_clean == "yes" and float(settlement_spot_price) >= float(strike_price)) or
                (side_clean == "no" and float(settlement_spot_price) < float(strike_price))
            ) else 0

            if is_twap_pin:
                f_code = "ERR_TWAP_PIN_VICTIM"
            elif is_whipsaw:
                f_code = "ERR_SALVAGE_WHIPSAW"
            elif is_ct:
                f_code = "ERR_COUNTER_TREND"
            elif is_dw or w_ratio >= 2.0:
                f_code = "ERR_MOMENTUM_EXHAUSTION"
            elif was_salv:
                f_code = "ERR_DOOMED_HOLD_TO_ZERO"
            else:
                f_code = "ERR_DISPERSION_EXCURSION"

            report["failure_code"] = f_code
            if str(exec_mode_resolved).lower() == "live":
                state.save_persisted_reports()

                if is_eth_asset:
                    try:
                        eth_file = Path("data/eth_win_loss_reports.json")
                        if eth_file.exists():
                            eth_reports = json.loads(eth_file.read_text(encoding="utf-8"))
                            if eth_reports and isinstance(eth_reports, list):
                                for r in eth_reports:
                                    if r.get("report_id") == report.get("report_id"):
                                        r["failure_code"] = f_code
                                        break
                                eth_file.write_text(json.dumps(eth_reports, indent=2), encoding="utf-8")
                    except Exception:
                        pass

            db_writer.enqueue_failure_autopsy(
                trade_id=report["report_id"],
                ticker=ticker,
                outcome="LOSS",
                realized_pnl=float(pnl),
                failure_code=f_code,
                is_counter_trend=is_ct,
                macro_1h_slope=macro_slope,
                is_double_wick_trap=is_dw,
                wick_to_body_ratio=w_ratio,
                was_salvageable=was_salv,
                salvageable_cents_lost=salv_lost,
                is_twap_pin_victim=is_twap_pin,
                twap_vs_spot_divergence=twap_div,
                bot_type=bot_type_resolved,
            )

        if exec_mode_resolved != "live" and state.sim_agent and state.sim_agent._portfolio:
            snap = state.sim_agent._portfolio.get_pnl_snapshot()
            db_writer.enqueue_equity_snapshot(
                balance=float(snap.current_balance),
                equity=float(snap.total_equity),
                realized_pnl=float(snap.total_realized_pnl),
                unrealized_pnl=float(snap.total_unrealized_pnl),
                drawdown_pct=float(state.sim_agent._portfolio.current_drawdown_pct * 100),
                win_rate=float((snap.win_rate or 0) * 100),
                total_trades=snap.total_trades,
                open_positions_count=snap.open_positions,
                bot_type=bot_type_resolved,
                execution_mode=exec_mode_resolved,
            )
    except Exception as exc:
        logger.debug("DB settlement & snapshot enqueue error: %s", exc)

    try:
        loop = asyncio.get_running_loop()
        coro = state.telemetry_alerts.send_settlement_alert(
            ticker=ticker,
            side=side_clean,
            contracts=contracts,
            pnl=pnl,
            roi_pct=float(roi_pct),
            outcome=outcome,
            balance_after=balance_after,
            strike_price=float(strike_price),
            settlement_btc_price=float(settlement_btc_price),
        )
        loop.create_task(coro)
    except RuntimeError:
        pass  # No running event loop (e.g. in synchronous test)
    except Exception as exc:
        logger.debug("Telemetry settlement alert dispatch error: %s", exc)

    state.is_dirty = True
    return report


def format_cycle_time_from_iso(iso_str: str, interval: int = 15) -> str:
    """Format an ISO timestamp to authentic Kalshi Eastern Time cycle interval."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        et_tz = ZoneInfo("America/New_York")
        et = dt.astimezone(et_tz)
        m_end = et.minute
        m_boundary = round(m_end / float(interval)) * interval
        if m_boundary >= 60:
            et_rounded = (et + timedelta(minutes=max(1, interval // 2))).replace(minute=0, second=0, microsecond=0)
            m_end = 0
            hr_end = et_rounded.hour
        else:
            hr_end = et.hour
            m_end = m_boundary
        
        m_start = (m_end - interval) % 60
        hr_start = hr_end if m_end >= interval else (hr_end - 1)
        ampm = "AM" if hr_end < 12 else "PM"
        hr_start_12 = hr_start % 12 or 12
        hr_end_12 = hr_end % 12 or 12
        date_str = et.strftime("%B %d")
        return f"{date_str}, {hr_start_12}:{m_start:02d} - {hr_end_12}:{m_end:02d} {ampm} ET"
    except Exception:
        return f"{interval}M Event Cycle ET"


_last_live_settlement_sync_time: float = 0.0
_has_done_initial_full_sync: bool = False


async def sync_live_settlements(full_sync: bool = False) -> list[dict[str, Any]]:
    """Synchronize live settlements directly from Kalshi API and reconcile with executed trades to generate live win/loss reports."""
    global _last_live_settlement_sync_time, _has_done_initial_full_sync
    state = _get_state()
    now = time.time()
    if not full_sync and (now - _last_live_settlement_sync_time < 30.0):
        return []

    client = state.order_client
    if client is None and state.sim_agent and hasattr(state.sim_agent, "_order_client"):
        client = state.sim_agent._order_client
        state.order_client = client

    if client is None:
        key_id = os.getenv("KALSHI_API_KEY_ID")
        key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "./kalshi_demo.pem")
        if not os.path.exists(key_path) and os.path.exists("./kalshi_demo.pem"):
            key_path = "./kalshi_demo.pem"
        if key_id and os.path.exists(key_path):
            client = KalshiLiveOrderClient(
                api_key_id=key_id,
                private_key_path=key_path,
                base_url=os.getenv("KALSHI_API_HOST", "https://api.elections.kalshi.com/trade-api/v2"),
            )
            state.order_client = client
            if hasattr(state, "sim_agent") and state.sim_agent:
                state.sim_agent._order_client = client
                if hasattr(state.sim_agent, "_order_router") and state.sim_agent._order_router:
                    state.sim_agent._order_router._order_client = client

    if client is None:
        return []

    try:
        # Full sync when explicitly requested or on startup when local live report history is incomplete
        need_full = full_sync or not _has_done_initial_full_sync
        settlements = await client.get_settlements(limit=100 if need_full else 50, all_pages=need_full, max_pages=10)
        _last_live_settlement_sync_time = now
        _has_done_initial_full_sync = True
        if not settlements:
            return []

        real_bal_dollars = Decimal("21.97")
        try:
            bal_data = await client.get_balance()
            if bal_data and "balance_dollars" in bal_data:
                b_val = Decimal(str(bal_data["balance_dollars"]))
                if b_val > Decimal("0"):
                    real_bal_dollars = b_val
            if state.live_portfolio is None:
                state.live_portfolio = {}
            state.live_portfolio["balance_dollars"] = float(real_bal_dollars)
        except Exception as bal_err:
            logger.debug("Failed fetching balance in sync_live_settlements: %s", bal_err)

        current_live_count = sum(1 for r in state.win_loss_reports if r.get("execution_mode") == "live")
        settlements_by_ticker = {s.get("ticker"): s for s in settlements if s.get("ticker")}
        if full_sync or current_live_count < len(settlements):
            state.win_loss_reports = [r for r in state.win_loss_reports if r.get("execution_mode") != "live" and r.get("bot_type") != "live"]
            existing_report_ids = {r.get("report_id") for r in state.win_loss_reports}
            existing_tickers = set()
        else:
            existing_report_ids = {r.get("report_id") for r in state.win_loss_reports}
            existing_tickers = {r.get("ticker") for r in state.win_loss_reports if r.get("execution_mode") == "live"}

        # Query local live trades from SQLite to reconcile attribution (both BTC and ETH stores)
        live_db_trades: dict[str, dict[str, Any]] = {}
        db_managers = [get_db(state.data_dir / "kalshi_history.db")]
        eth_path = state.data_dir / "kalshi_history_eth.db"
        if eth_path.exists():
            db_managers.append(get_eth_db(eth_path))

        for mgr in db_managers:
            try:
                if mgr.db_path.exists():
                    async with mgr.get_connection() as conn:
                        async with conn.execute(
                            "SELECT trade_id, ticker, side, size, price, gross_value, timestamp_utc, bot_type FROM trades WHERE execution_mode = 'live'"
                        ) as cursor:
                            rows = await cursor.fetchall()
                            for row in rows:
                                t_ticker = row[1]
                                live_db_trades[t_ticker] = {
                                    "trade_id": row[0],
                                    "ticker": t_ticker,
                                    "side": row[2],
                                    "size": row[3],
                                    "price": Decimal(str(row[4])),
                                    "gross_value": Decimal(str(row[5])),
                                    "timestamp_utc": row[6],
                                    "bot_type": row[7] or ("eth_bot1_v4" if "ETH" in str(t_ticker) else "3_step_domination_bot"),
                                }
            except Exception as db_exc:
                logger.debug("Failed reading trades table from %s in sync_live_settlements: %s", mgr.db_path, db_exc)

        new_reports: list[dict[str, Any]] = []

        # 1. Process known live trades that have settled
        for ticker, t_info in live_db_trades.items():
            report_id = f"WLR-LIVE-{ticker}"
            if report_id in existing_report_ids or ticker in existing_tickers:
                continue

            s = settlements_by_ticker.get(ticker)
            if not s:
                continue

            market_result = s.get("market_result", "").lower()
            if not market_result:
                continue

            trade_side = t_info["side"].lower()
            size = t_info["size"]
            cost = t_info["gross_value"]
            entry_price = t_info["price"]
            won = (trade_side == market_result)
            outcome = "win" if won else "loss"

            revenue = Decimal(str(size)) * Decimal("1.00") if won else Decimal("0.00")
            raw_rev = s.get("revenue")
            if raw_rev is not None:
                rev_dec = Decimal(str(raw_rev)) / Decimal("100") if isinstance(raw_rev, int) else Decimal(str(raw_rev))
                if rev_dec > Decimal("0") and won:
                    revenue = rev_dec

            pnl = revenue - cost
            settled_ts = s.get("settled_time") or t_info["timestamp_utc"]
            cycle_time = format_cycle_time_from_iso(settled_ts)

            # Resolve strike price
            strike_price = Decimal("0.0")
            if state.ingestion_agent and hasattr(state.ingestion_agent, "_market_cache"):
                m_info = state.ingestion_agent._market_cache.get(ticker)
                if m_info and m_info.floor_strike:
                    strike_price = m_info.floor_strike
            if strike_price == Decimal("0.0"):
                strike_price = state.target_strike

            is_eth = ticker.startswith("KXETH")
            diff_step = Decimal("2.50") if is_eth else Decimal("45.00")
            settlement_btc_price = strike_price + (diff_step if market_result == "yes" else -diff_step)
            live_bal = real_bal_dollars

            rep = record_win_loss_event_report(
                ticker=ticker,
                side=trade_side,
                contracts=size,
                entry_price=entry_price,
                settlement_btc_price=settlement_btc_price,
                settlement_spot_price=settlement_btc_price,
                strike_price=strike_price,
                timeframe="15m",
                ai_confidence=0.82,
                ai_rationale=f"Real Kalshi Production Settlement | Trade ID: {t_info['trade_id']} | Result: {market_result.upper()} | Revenue: ${float(revenue):.2f}",
                vpin_score=0.15,
                ev_edge=0.10,
                bot_type=t_info["bot_type"],
                execution_mode="live",
                report_id=report_id,
                custom_pnl=pnl,
                custom_outcome=outcome,
                timestamp_utc=settled_ts,
                cycle_time=cycle_time,
                balance_after=live_bal,
                asset="ETH" if is_eth else "BTC",
                skip_guardrails=True,
            )
            new_reports.append(rep)
            existing_report_ids.add(report_id)
            existing_tickers.add(ticker)
            logger.info("[LIVE REPORT GENERATED FROM TRADE] %s | %s | PnL: $%.4f", ticker, outcome.upper(), float(pnl))

        # 2. Reconcile ALL genuine Kalshi settlements directly from Kalshi API
        for s in settlements:
            ticker = s.get("ticker", "")
            if not ticker or not ticker.startswith("KX"):
                continue

            report_id = f"WLR-LIVE-{ticker}"
            if report_id in existing_report_ids or ticker in existing_tickers:
                continue

            try:
                yes_cnt = int(float(str(s.get("yes_count_fp", "0") or "0")))
                no_cnt = int(float(str(s.get("no_count_fp", "0") or "0")))
                yes_cost = Decimal(str(s.get("yes_total_cost_dollars", "0") or "0"))
                no_cost = Decimal(str(s.get("no_total_cost_dollars", "0") or "0"))
                revenue = Decimal(str(s.get("revenue", 0) or 0)) / Decimal("100")
                fee = Decimal(str(s.get("fee_cost", "0") or "0"))
            except Exception:
                continue

            total_cnt = yes_cnt + no_cnt
            total_cost = yes_cost + no_cost
            if total_cnt == 0 and total_cost == Decimal("0") and revenue == Decimal("0"):
                continue

            side = "yes" if yes_cnt > no_cnt else ("no" if no_cnt > yes_cnt else ("yes" if yes_cost >= no_cost else "no"))
            contracts = total_cnt if total_cnt > 0 else 1
            cost = total_cost
            entry_price = (cost / Decimal(str(contracts))) if contracts > 0 else Decimal("0.50")

            market_result = s.get("market_result", "").lower()
            pnl = revenue - cost - fee
            won = (pnl > Decimal("0")) or (side == market_result and revenue > Decimal("0"))
            outcome = "win" if won else ("loss" if pnl < Decimal("0") else "flat")

            settled_ts = s.get("settled_time") or datetime.now(timezone.utc).isoformat()
            cycle_time = format_cycle_time_from_iso(settled_ts)

            strike_price = Decimal("0.0")
            if state.ingestion_agent and hasattr(state.ingestion_agent, "_market_cache"):
                m_info = state.ingestion_agent._market_cache.get(ticker)
                if m_info and m_info.floor_strike:
                    strike_price = m_info.floor_strike
            if strike_price == Decimal("0.0"):
                strike_price = state.target_strike

            is_eth = ticker.startswith("KXETH")
            diff_step = Decimal("2.50") if is_eth else Decimal("50.00")
            settlement_btc_price = strike_price + (diff_step if market_result == "yes" else -diff_step)
            live_bal = real_bal_dollars

            rep = record_win_loss_event_report(
                ticker=ticker,
                side=side,
                contracts=contracts,
                entry_price=entry_price,
                settlement_btc_price=settlement_btc_price,
                settlement_spot_price=settlement_btc_price,
                strike_price=strike_price,
                timeframe="15m",
                ai_confidence=0.80,
                ai_rationale=f"Real Kalshi Production Settlement | Result: {market_result.upper()} | Revenue: ${float(revenue):.2f} | Fee: ${float(fee):.4f}",
                vpin_score=0.15,
                ev_edge=0.10,
                bot_type="eth_bot1_v4" if is_eth else "3_step_domination_bot",
                execution_mode="live",
                report_id=report_id,
                custom_pnl=pnl,
                custom_outcome=outcome,
                timestamp_utc=settled_ts,
                cycle_time=cycle_time,
                balance_after=live_bal,
                asset="ETH" if is_eth else "BTC",
                skip_guardrails=True,
            )
            rep["gross_pnl"] = float(revenue - cost)
            rep["fee"] = float(fee)
            new_reports.append(rep)
            existing_report_ids.add(report_id)
            existing_tickers.add(ticker)
            logger.info("[LIVE REPORT GENERATED FROM SETTLEMENT] %s | %s | PnL: $%.4f", ticker, outcome.upper(), float(pnl))

        if new_reports:
            # Sort all win_loss_reports by timestamp_utc descending so newest trades always show on top
            state.win_loss_reports.sort(key=lambda r: str(r.get("timestamp_utc", "")), reverse=True)
            state.save_persisted_reports()

            # Ensure SQLite store has all live records for historical query service (both BTC and ETH)
            try:
                for r in new_reports:
                    is_eth = r["ticker"].startswith("KXETH") or str(r.get("asset", "")).upper() == "ETH"
                    target_db = get_eth_db(state.data_dir / "kalshi_history_eth.db") if is_eth else get_db(state.data_dir / "kalshi_history.db")
                    async with target_db.get_connection() as conn:
                        ts_str = str(r.get("timestamp_utc", ""))
                        try:
                            dt_val = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            epoch_ms = int(dt_val.timestamp() * 1000)
                        except Exception:
                            epoch_ms = int(time.time() * 1000)

                        await conn.execute(
                            """
                            INSERT OR REPLACE INTO settlements (
                                settlement_id, timestamp_utc, timestamp_epoch_ms, ticker, side, size,
                                entry_price, settlement_price, outcome, pnl, balance_after, bot_type, execution_mode
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                r["report_id"],
                                ts_str,
                                epoch_ms,
                                r["ticker"],
                                r["bot_side"],
                                r["contracts"],
                                float(r["entry_price"]),
                                float(r["settlement_price"]),
                                r["outcome"],
                                float(r.get("gross_pnl", r["pnl"])),
                                float(r.get("balance_after", 21.97)),
                                r.get("bot_type", "eth_bot1_v4" if is_eth else "3_step_domination_bot"),
                                "live",
                            )
                        )
                        await conn.execute(
                            """
                            INSERT OR REPLACE INTO trades (
                                trade_id, timestamp_utc, timestamp_epoch_ms, ticker, timeframe, side,
                                size, price, gross_value, fees, bot_type, execution_mode, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                f"live_tr_{r['ticker']}",
                                ts_str,
                                epoch_ms,
                                r["ticker"],
                                "15m",
                                r["bot_side"],
                                r["contracts"],
                                float(r["entry_price"]),
                                float(r["entry_price"]) * r["contracts"],
                                float(r.get("fee", 0.0)),
                                r.get("bot_type", "eth_bot1_v4" if is_eth else "3_step_domination_bot"),
                                "live",
                                "filled",
                            )
                        )
                        await conn.commit()
            except Exception as db_sync_exc:
                logger.debug("Direct DB sync exception: %s", db_sync_exc)

        return new_reports
    except Exception as exc:
        logger.error("Failed to sync live settlements: %s", exc)
        return []
