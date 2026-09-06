"""Macro Trend Dominion Bot (Macro Trend Following & Asymmetric Capital Preservation Engine).

Formulated specifically for Kalshi 15-Minute Bitcoin Binary Contracts to eliminate the #1
historical failure mode: fighting the macro trend during Bitcoin bull/bear expansions.

Core Principles:
1. Multi-Scale Macro Trend Engine: Continuously evaluates rolling 1-hour and 15-minute BTC spot returns.
2. Strict Trend Alignment:
   - MACRO_BULL: Exclusively trades YES. Counter-trend NO bets are 100% vetoed.
   - MACRO_BEAR: Exclusively trades NO. Counter-trend YES bets are 100% vetoed.
   - MACRO_CHOP: Enforces strict $50 spot separation barrier.
3. Strict Micro-Bankroll Sizing: Exactly 1 contract while total equity < $50.00.
4. Entry Price Sweet Spot: $0.30 floor (no lottery traps) to $0.62 ceiling (hard kill > $0.72).
5. Dynamic Late-Cycle Harvest & Cut-Loss Salvage:
   - Takes profit at >= $0.85 - $0.95.
   - Salvages 10c-20c on hopeless out-of-the-money positions (T <= 90s, Diff > $50 adverse).
"""

from __future__ import annotations

import collections
import logging
import math
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Deque, Dict, List, Optional, Tuple, Union

from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
from kalshi_sim.schemas import L2BookState, OrderSide, TradeEvent

logger = logging.getLogger("kalshi_sim.macro_trend_dominion")


def _standard_normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function Phi(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class MacroTrendDecision:
    """Structured decision output from Macro Trend Dominion Bot."""
    strategy_id: str
    strategy_name: str
    active_playbook: str
    playbook_stage: str
    macro_regime: str  # 'MACRO_BULL' | 'MACRO_BEAR' | 'MACRO_CHOP'
    trend_1h_pct: float
    trend_15m_pct: float
    p_up: float
    p_down: float
    p_wait: float
    vpin: float
    vpin_is_safe: bool
    ev_yes: float
    ev_no: float
    edge_yes: float
    edge_no: float
    kelly_f_yes: float
    kelly_f_no: float
    recommended_side: str  # 'yes' | 'no' | 'wait'
    recommended_contracts: int
    rationale: str
    edge_pct: float
    time_to_expiry_s: float
    spot_diff: float
    onnx_signal: str = "WAIT"
    onnx_confidence: float = 0.0
    onnx_prob_long: float = 0.0
    onnx_prob_short: float = 0.0
    onnx_prob_wait: float = 0.0


@dataclass(frozen=True)
class MacroTrendExitDecision:
    """Structured exit evaluation from Macro Trend Dominion Bot."""
    should_exit: bool
    exit_reason: str  # 'TAKE_PROFIT_CEILING' | 'LATE_CYCLE_HARVEST' | 'TAKE_PROFIT_ROI' | 'CUT_LOSS_SALVAGE' | 'HOLD' | 'NONE'
    exit_price: Decimal
    profit_pct: float
    unrealized_pnl: Decimal
    rationale: str


class MacroTrendDominionBot:
    """Macro Trend Dominion Quantitative Strategy Bot."""

    STRATEGY_ID = "macro_onnx"
    STRATEGY_NAME = "Macro ONNX Bot"

    def __init__(
        self,
        strategy_id: str = "macro_onnx",
        strategy_name: str = "Macro ONNX Bot",
        min_edge_pct: float = 0.06,  # 6.0% minimum statistical edge
        min_ev_dollars: Decimal = Decimal("0.02"),
        vpin_toxic_threshold: float = 0.60,
        vpin_safe_threshold: float = 0.35,
        default_btc_1m_volatility: float = 14.0,
        take_profit_price_threshold: Decimal = Decimal("0.95"),
        min_take_profit_roi: float = 0.20,
        late_cycle_roi: float = 0.15,
        fee_per_contract: Decimal = Decimal("0.01"),
        min_spot_diff: float = 35.0,
        chop_spot_diff: float = 50.0,
        max_entry_price: Decimal = Decimal("0.62"),
        hard_kill_price: Decimal = Decimal("0.68"),
        min_entry_price: Decimal = Decimal("0.30"),
        macro_bull_threshold_pct: float = 0.15,  # +0.15% 1-hour return classifies as BULL
        macro_bear_threshold_pct: float = -0.15,  # -0.15% 1-hour return classifies as BEAR
        max_spot_history_seconds: float = 7200.0,  # 2 hours rolling buffer
        onnx_orderflow_weight: float = 0.35,  # 35% weight for ONNX Bitcoin microstructure orderflow
    ) -> None:
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.min_edge_pct = min_edge_pct
        self.min_ev_dollars = min_ev_dollars
        self.vpin_toxic_threshold = vpin_toxic_threshold
        self.vpin_safe_threshold = vpin_safe_threshold
        self.default_btc_1m_volatility = default_btc_1m_volatility
        self.take_profit_price_threshold = take_profit_price_threshold
        self.min_take_profit_roi = min_take_profit_roi
        self.late_cycle_roi = late_cycle_roi
        self.fee_per_contract = fee_per_contract
        self.min_spot_diff = min_spot_diff
        self.chop_spot_diff = chop_spot_diff
        self.max_entry_price = Decimal(str(max_entry_price))
        self.hard_kill_price = Decimal(str(hard_kill_price))
        self.min_entry_price = Decimal(str(min_entry_price))
        self.macro_bull_threshold_pct = macro_bull_threshold_pct
        self.macro_bear_threshold_pct = macro_bear_threshold_pct
        self.max_spot_history_seconds = max_spot_history_seconds
        self.onnx_orderflow_weight = onnx_orderflow_weight

        # Rolling spot buffer: list of (timestamp_monotonic_or_epoch, price)
        self._spot_buffer: Deque[Tuple[float, float]] = collections.deque()

        # Underpinning EV & Quarter-Kelly Optimizer
        self._ev_engine = StatisticalEVEngine(
            min_ev_threshold=min_ev_dollars,
            min_edge_pct=min_edge_pct,
            fee_per_contract=fee_per_contract,
            fractional_kelly=0.15,
            max_portfolio_risk_pct=Decimal("0.05"),
            vpin_safe_threshold=vpin_safe_threshold,
            vpin_toxic_threshold=vpin_toxic_threshold,
        )

    def record_spot_tick(self, timestamp: float, price: float) -> None:
        """Append a spot price tick to the internal rolling buffer."""
        if price <= 0.0:
            return
        self._spot_buffer.append((timestamp, price))
        cutoff = timestamp - self.max_spot_history_seconds
        while self._spot_buffer and self._spot_buffer[0][0] < cutoff:
            self._spot_buffer.popleft()

    def compute_macro_trend(
        self,
        current_spot: float,
        current_time: Optional[float] = None,
        external_spot_history: Optional[List[Tuple[float, float]]] = None,
    ) -> Tuple[float, float, str]:
        """Compute rolling 1-hour and 15-minute percentage return and classify regime.

        Returns:
            (trend_1h_pct, trend_15m_pct, regime_str)
            where regime_str in ('MACRO_BULL', 'MACRO_BEAR', 'MACRO_CHOP')
        """
        now_ts = current_time or time.time()
        self.record_spot_tick(now_ts, current_spot)

        buf = external_spot_history or list(self._spot_buffer)
        if not buf or len(buf) < 2:
            return 0.0, 0.0, "MACRO_CHOP"

        target_1h = now_ts - 3600.0
        target_15m = now_ts - 900.0

        p_1h: Optional[float] = None
        p_15m: Optional[float] = None

        for ts, p in buf:
            if ts <= target_1h:
                p_1h = p
            if ts <= target_15m and p_15m is None:
                p_15m = p

        if p_1h is None and buf:
            oldest_ts, oldest_p = buf[0]
            elapsed = max(1.0, now_ts - oldest_ts)
            p_1h = oldest_p if elapsed >= 300.0 else current_spot

        if p_15m is None and buf:
            p_15m = buf[0][1]

        trend_1h_pct = ((current_spot - p_1h) / p_1h * 100.0) if (p_1h and p_1h > 0) else 0.0
        trend_15m_pct = ((current_spot - p_15m) / p_15m * 100.0) if (p_15m and p_15m > 0) else 0.0

        if trend_1h_pct >= self.macro_bull_threshold_pct or (
            trend_1h_pct > 0.05 and trend_15m_pct >= 0.10
        ):
            regime = "MACRO_BULL"
        elif trend_1h_pct <= self.macro_bear_threshold_pct or (
            trend_1h_pct < -0.05 and trend_15m_pct <= -0.10
        ):
            regime = "MACRO_BEAR"
        else:
            regime = "MACRO_CHOP"

        return round(trend_1h_pct, 3), round(trend_15m_pct, 3), regime

    def evaluate(
        self,
        book: Optional[L2BookState],
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        recent_trades: Optional[List[TradeEvent]] = None,
        total_equity: Decimal = Decimal("25.00"),
        max_position_size: int = 1,
        estimated_vpin: float = 0.15,
        current_time: Optional[float] = None,
        spot_history: Optional[List[Tuple[float, float]]] = None,
        onnx_result: Optional[Dict[str, Any]] = None,
    ) -> MacroTrendDecision:
        """Evaluate market and order book against Macro Trend Dominion quantitative pillars."""
        spot_diff = spot_price - target_strike

        # Parse ONNX Bitcoin Microstructure Orderflow (Trained on underlying BTC orderflow)
        onnx_signal = "WAIT"
        onnx_conf = 0.0
        onnx_prob_long = 0.33
        onnx_prob_short = 0.33
        onnx_prob_wait = 0.34
        onnx_has_data = False

        if onnx_result:
            onnx_has_data = True
            onnx_signal = str(onnx_result.get("signal", "WAIT")).upper()
            onnx_conf = float(onnx_result.get("confidence", 0.0))
            onnx_prob_long = float(onnx_result.get("prob_long", onnx_result.get("rel_long", 0.33)))
            onnx_prob_short = float(onnx_result.get("prob_short", onnx_result.get("rel_short", 0.33)))
            onnx_prob_wait = float(onnx_result.get("prob_wait", 0.34))
            if "vpin_score" in onnx_result and estimated_vpin == 0.15:
                try:
                    estimated_vpin = float(onnx_result["vpin_score"])
                except Exception:
                    pass

        trend_1h_pct, trend_15m_pct, macro_regime = self.compute_macro_trend(
            current_spot=spot_price,
            current_time=current_time,
            external_spot_history=spot_history,
        )

        effective_max_size = 1 if total_equity < Decimal("50.00") else min(max_position_size, 2)

        # Book Validity Check
        if not book or not book.yes_book or not book.no_book:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                macro_regime=macro_regime,
                trend_1h_pct=trend_1h_pct,
                trend_15m_pct=trend_15m_pct,
                vpin=estimated_vpin,
                onnx_signal=onnx_signal,
                onnx_confidence=onnx_conf,
                onnx_prob_long=onnx_prob_long,
                onnx_prob_short=onnx_prob_short,
                onnx_prob_wait=onnx_prob_wait,
                rationale="L2 Order Book invalid or crossed. Awaiting clean touch quote.",
            )

        best_yes_ask = book.best_yes_ask
        best_no_ask = book.best_no_ask
        if best_yes_ask is None or best_no_ask is None:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                macro_regime=macro_regime,
                trend_1h_pct=trend_1h_pct,
                trend_15m_pct=trend_15m_pct,
                vpin=estimated_vpin,
                onnx_signal=onnx_signal,
                onnx_confidence=onnx_conf,
                onnx_prob_long=onnx_prob_long,
                onnx_prob_short=onnx_prob_short,
                onnx_prob_wait=onnx_prob_wait,
                rationale="Incomplete two-sided book (missing inside ask). Waiting for quote.",
            )

        if estimated_vpin > self.vpin_toxic_threshold:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                macro_regime=macro_regime,
                trend_1h_pct=trend_1h_pct,
                trend_15m_pct=trend_15m_pct,
                vpin=estimated_vpin,
                vpin_is_safe=False,
                onnx_signal=onnx_signal,
                onnx_confidence=onnx_conf,
                onnx_prob_long=onnx_prob_long,
                onnx_prob_short=onnx_prob_short,
                onnx_prob_wait=onnx_prob_wait,
                rationale=f"VPIN Toxicity Veto: Score={estimated_vpin:.2f} > {self.vpin_toxic_threshold:.2f}. "
                          f"Suppressing trades to prevent adverse whale selection.",
            )

        required_diff = self.chop_spot_diff if macro_regime == "MACRO_CHOP" else self.min_spot_diff
        if abs(spot_diff) < required_diff:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                macro_regime=macro_regime,
                trend_1h_pct=trend_1h_pct,
                trend_15m_pct=trend_15m_pct,
                vpin=estimated_vpin,
                onnx_signal=onnx_signal,
                onnx_confidence=onnx_conf,
                onnx_prob_long=onnx_prob_long,
                onnx_prob_short=onnx_prob_short,
                onnx_prob_wait=onnx_prob_wait,
                rationale=f"Spot-Strike Proximity Veto: |Diff|=${abs(spot_diff):.2f} < ${required_diff:.0f} threshold "
                          f"in {macro_regime}. Coin-flip territory, skipping.",
            )

        tau_mins = max(0.1, time_to_expiry_s / 60.0)

        # PLAYBOOK 3: Late-Cycle High-Certainty Gamma Sniper (45s <= T <= 240s)
        if 45 <= time_to_expiry_s <= 240:
            stage = "gamma_sniper"
            playbook_title = "Playbook 3: Late-Cycle Gamma Sniper"

            tau_sqrt = math.sqrt(tau_mins)
            expected_vol = max(4.0, self.default_btc_1m_volatility * tau_sqrt)
            z_score = spot_diff / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            if onnx_has_data:
                # Bayesian Orderflow Fusion: Macro Moneyness (65%) + ONNX BTC Orderflow (35%)
                w_onnx = self.onnx_orderflow_weight
                fused_yes = (1.0 - w_onnx) * prob_yes_raw + w_onnx * onnx_prob_long
                fused_no = (1.0 - w_onnx) * (1.0 - prob_yes_raw) + w_onnx * onnx_prob_short
                norm = fused_yes + fused_no
                prob_yes = max(0.02, min(0.98, fused_yes / norm if norm > 0 else prob_yes_raw))
                prob_no = 1.0 - prob_yes
                prob_wait = max(0.05, onnx_prob_wait * 0.15)
            else:
                prob_yes = max(0.02, min(0.98, prob_yes_raw))
                prob_no = 1.0 - prob_yes
                prob_wait = 0.05

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                total_equity=total_equity,
                max_position_size=effective_max_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
            )

            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                onnx_tag = f" • ONNX: {onnx_signal} ({onnx_conf*100:.0f}%)" if onnx_has_data else ""
                rationale = (
                    f"[{playbook_title}] High-Certainty Harvest | "
                    f"Regime: {macro_regime} (1h: {trend_1h_pct:+.2f}%){onnx_tag} | "
                    f"Diff=${spot_diff:+.1f} | T={int(time_to_expiry_s)}s | "
                    f"True Prob: {target_prob*100:.1f}% vs Market: ${ev_res.market_price} | "
                    f"Edge: +{float(ev_res.statistical_edge)*100:.1f}% | Net EV: +${float(ev_res.expected_value):.2f}"
                )
                return self._build_decision(
                    playbook_title=playbook_title,
                    stage=stage,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    p_up=prob_yes,
                    p_down=prob_no,
                    p_wait=prob_wait,
                    vpin=estimated_vpin,
                    vpin_is_safe=True,
                    ev_res=ev_res,
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    rationale=rationale,
                    effective_max_size=effective_max_size,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_conf,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    onnx_has_data=onnx_has_data,
                )

        # PLAYBOOK 2: Trend Continuation Pullback (240s < T <= 600s)
        elif 240 < time_to_expiry_s <= 600:
            stage = "trend_continuation"
            playbook_title = "Playbook 2: Trend Continuation Pullback"

            ofi_ratio = 0.0
            if recent_trades:
                recent_window = [t for t in recent_trades if (time.time() - t.timestamp.timestamp()) <= 180.0]
                if recent_window:
                    yes_vol = sum(t.count for t in recent_window if t.side == OrderSide.YES)
                    no_vol = sum(t.count for t in recent_window if t.side == OrderSide.NO)
                    tot_vol = yes_vol + no_vol
                    if tot_vol > 0:
                        ofi_ratio = (yes_vol - no_vol) / tot_vol

            tau_sqrt = math.sqrt(tau_mins)
            expected_vol = max(6.0, self.default_btc_1m_volatility * tau_sqrt)
            base_drift = 0.15 * ofi_ratio * expected_vol
            macro_drift = 0.20 * (trend_1h_pct / 0.50) * expected_vol
            z_score = (spot_diff + base_drift + macro_drift) / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            if onnx_has_data:
                # Bayesian Orderflow Fusion: Macro Moneyness (65%) + ONNX BTC Orderflow (35%)
                w_onnx = self.onnx_orderflow_weight
                fused_yes = (1.0 - w_onnx) * prob_yes_raw + w_onnx * onnx_prob_long
                fused_no = (1.0 - w_onnx) * (1.0 - prob_yes_raw) + w_onnx * onnx_prob_short
                norm = fused_yes + fused_no
                prob_yes = max(0.05, min(0.95, fused_yes / norm if norm > 0 else prob_yes_raw))
                prob_no = 1.0 - prob_yes
                prob_wait = max(0.08, onnx_prob_wait * 0.20)
            else:
                prob_yes = max(0.05, min(0.95, prob_yes_raw))
                prob_no = 1.0 - prob_yes
                prob_wait = 0.10

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                total_equity=total_equity,
                max_position_size=effective_max_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
            )

            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                onnx_tag = f" • ONNX: {onnx_signal} ({onnx_conf*100:.0f}%)" if onnx_has_data else ""
                rationale = (
                    f"[{playbook_title}] Macro Trend Continuation | "
                    f"Regime: {macro_regime} (1h: {trend_1h_pct:+.2f}%, 15m: {trend_15m_pct:+.2f}%){onnx_tag} | "
                    f"Diff=${spot_diff:+.1f} | OFI={ofi_ratio:+.2f} | "
                    f"True Prob: {target_prob*100:.1f}% vs Market: ${ev_res.market_price} | "
                    f"Edge: +{float(ev_res.statistical_edge)*100:.1f}% | Net EV: +${float(ev_res.expected_value):.2f}"
                )
                return self._build_decision(
                    playbook_title=playbook_title,
                    stage=stage,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    p_up=prob_yes,
                    p_down=prob_no,
                    p_wait=prob_wait,
                    vpin=estimated_vpin,
                    vpin_is_safe=True,
                    ev_res=ev_res,
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    rationale=rationale,
                    effective_max_size=effective_max_size,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_conf,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    onnx_has_data=onnx_has_data,
                )

        # PLAYBOOK 1: Macro Trend Expansion (600s < T <= 900s)
        elif 600 < time_to_expiry_s <= 900:
            stage = "trend_expansion"
            playbook_title = "Playbook 1: Macro Trend Expansion"

            if abs(spot_diff) < 40.0:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    vpin=estimated_vpin,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_conf,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    rationale=f"[{playbook_title}] Waiting for breakout: |Diff|=${abs(spot_diff):.2f} < $40.00.",
                )

            tau_sqrt = math.sqrt(tau_mins)
            expected_vol = max(8.0, self.default_btc_1m_volatility * tau_sqrt)
            macro_drift = 0.25 * (trend_1h_pct / 0.50) * expected_vol
            z_score = (spot_diff + macro_drift) / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            if onnx_has_data:
                # Bayesian Orderflow Fusion: Macro Moneyness (65%) + ONNX BTC Orderflow (35%)
                w_onnx = self.onnx_orderflow_weight
                fused_yes = (1.0 - w_onnx) * prob_yes_raw + w_onnx * onnx_prob_long
                fused_no = (1.0 - w_onnx) * (1.0 - prob_yes_raw) + w_onnx * onnx_prob_short
                norm = fused_yes + fused_no
                prob_yes = max(0.08, min(0.92, fused_yes / norm if norm > 0 else prob_yes_raw))
                prob_no = 1.0 - prob_yes
                prob_wait = max(0.10, onnx_prob_wait * 0.25)
            else:
                prob_yes = max(0.08, min(0.92, prob_yes_raw))
                prob_no = 1.0 - prob_yes
                prob_wait = 0.15

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                total_equity=total_equity,
                max_position_size=effective_max_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
            )

            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                onnx_tag = f" • ONNX: {onnx_signal} ({onnx_conf*100:.0f}%)" if onnx_has_data else ""
                rationale = (
                    f"[{playbook_title}] Macro Trend Breakout | "
                    f"Regime: {macro_regime} (1h: {trend_1h_pct:+.2f}%){onnx_tag} | "
                    f"Diff=${spot_diff:+.1f} | T={int(time_to_expiry_s)}s | "
                    f"True Prob: {target_prob*100:.1f}% vs Market: ${ev_res.market_price} | "
                    f"Edge: +{float(ev_res.statistical_edge)*100:.1f}% | Net EV: +${float(ev_res.expected_value):.2f}"
                )
                return self._build_decision(
                    playbook_title=playbook_title,
                    stage=stage,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    p_up=prob_yes,
                    p_down=prob_no,
                    p_wait=prob_wait,
                    vpin=estimated_vpin,
                    vpin_is_safe=True,
                    ev_res=ev_res,
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    rationale=rationale,
                    effective_max_size=effective_max_size,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_conf,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    onnx_has_data=onnx_has_data,
                )

        return self._build_wait_decision(
            time_to_expiry_s=time_to_expiry_s,
            spot_diff=spot_diff,
            macro_regime=macro_regime,
            trend_1h_pct=trend_1h_pct,
            trend_15m_pct=trend_15m_pct,
            vpin=estimated_vpin,
            onnx_signal=onnx_signal,
            onnx_confidence=onnx_conf,
            onnx_prob_long=onnx_prob_long,
            onnx_prob_short=onnx_prob_short,
            onnx_prob_wait=onnx_prob_wait,
            rationale=f"Cycle stage idle (T={int(time_to_expiry_s)}s). Awaiting high-edge setup.",
        )

    def _build_decision(
        self,
        playbook_title: str,
        stage: str,
        macro_regime: str,
        trend_1h_pct: float,
        trend_15m_pct: float,
        p_up: float,
        p_down: float,
        p_wait: float,
        vpin: float,
        vpin_is_safe: bool,
        ev_res: ExpectedValueResult,
        time_to_expiry_s: float,
        spot_diff: float,
        rationale: str,
        effective_max_size: int = 1,
        onnx_signal: str = "WAIT",
        onnx_confidence: float = 0.0,
        onnx_prob_long: float = 0.0,
        onnx_prob_short: float = 0.0,
        onnx_prob_wait: float = 0.0,
        onnx_has_data: bool = False,
    ) -> MacroTrendDecision:
        """Enforce strict trend alignment, ONNX orderflow concordance, and entry price gates."""
        if ev_res.recommended_side in (OrderSide.YES, OrderSide.NO) and ev_res.recommended_contracts > 0:
            target_ask = float(ev_res.market_price)

            # 1. Strict Macro Trend Following Gate
            if macro_regime == "MACRO_BULL" and ev_res.recommended_side == OrderSide.NO:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    vpin=vpin,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_confidence,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    rationale=(
                        f"Macro Trend Veto: Prohibiting NO trade during MACRO_BULL trend "
                        f"(1h: {trend_1h_pct:+.2f}%, 15m: {trend_15m_pct:+.2f}%). "
                        f"Never bet against an active macro bull expansion."
                    ),
                )

            if macro_regime == "MACRO_BEAR" and ev_res.recommended_side == OrderSide.YES:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    vpin=vpin,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_confidence,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    rationale=(
                        f"Macro Trend Veto: Prohibiting YES trade during MACRO_BEAR trend "
                        f"(1h: {trend_1h_pct:+.2f}%, 15m: {trend_15m_pct:+.2f}%). "
                        f"Never catch a falling knife during macro bear dump."
                    ),
                )

            # 2. ONNX Bitcoin Orderflow Contradiction Veto (Shield against adverse BTC microstructure)
            if onnx_has_data:
                if ev_res.recommended_side == OrderSide.YES:
                    if onnx_signal == "SHORT" and (onnx_confidence >= 0.55 or onnx_prob_short >= 0.58):
                        return self._build_wait_decision(
                            time_to_expiry_s=time_to_expiry_s,
                            spot_diff=spot_diff,
                            macro_regime=macro_regime,
                            trend_1h_pct=trend_1h_pct,
                            trend_15m_pct=trend_15m_pct,
                            vpin=vpin,
                            onnx_signal=onnx_signal,
                            onnx_confidence=onnx_confidence,
                            onnx_prob_long=onnx_prob_long,
                            onnx_prob_short=onnx_prob_short,
                            onnx_prob_wait=onnx_prob_wait,
                            rationale=(
                                f"ONNX Orderflow Contradiction Veto: Vetoing YES trade because Bitcoin orderflow "
                                f"model indicates active selling pressure [SHORT, Conf={onnx_confidence*100:.1f}%, P(SHORT)={onnx_prob_short*100:.1f}%]. "
                                f"Do not buy YES against incoming Bitcoin dump."
                            ),
                        )
                elif ev_res.recommended_side == OrderSide.NO:
                    if onnx_signal == "LONG" and (onnx_confidence >= 0.55 or onnx_prob_long >= 0.58):
                        return self._build_wait_decision(
                            time_to_expiry_s=time_to_expiry_s,
                            spot_diff=spot_diff,
                            macro_regime=macro_regime,
                            trend_1h_pct=trend_1h_pct,
                            trend_15m_pct=trend_15m_pct,
                            vpin=vpin,
                            onnx_signal=onnx_signal,
                            onnx_confidence=onnx_confidence,
                            onnx_prob_long=onnx_prob_long,
                            onnx_prob_short=onnx_prob_short,
                            onnx_prob_wait=onnx_prob_wait,
                            rationale=(
                                f"ONNX Orderflow Contradiction Veto: Vetoing NO trade because Bitcoin orderflow "
                                f"model indicates active buying pressure [LONG, Conf={onnx_confidence*100:.1f}%, P(LONG)={onnx_prob_long*100:.1f}%]. "
                                f"Do not buy NO against incoming Bitcoin rally."
                            ),
                        )

                # 3. Extreme Orderflow Uncertainty Veto
                if onnx_prob_wait >= 0.70 and abs(spot_diff) < self.chop_spot_diff:
                    return self._build_wait_decision(
                        time_to_expiry_s=time_to_expiry_s,
                        spot_diff=spot_diff,
                        macro_regime=macro_regime,
                        trend_1h_pct=trend_1h_pct,
                        trend_15m_pct=trend_15m_pct,
                        vpin=vpin,
                        onnx_signal=onnx_signal,
                        onnx_confidence=onnx_confidence,
                        onnx_prob_long=onnx_prob_long,
                        onnx_prob_short=onnx_prob_short,
                        onnx_prob_wait=onnx_prob_wait,
                        rationale=(
                            f"ONNX Neutral Orderflow Veto: P(WAIT)={onnx_prob_wait*100:.1f}% dominates in chop zone "
                            f"(|Diff|=${abs(spot_diff):.1f} < ${self.chop_spot_diff:.0f}). Suppressing trade to avoid coin-toss flip."
                        ),
                    )

            # Tier 1 Hard Ceiling: > $0.68
            if target_ask > self.hard_kill_price:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    vpin=vpin,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_confidence,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    rationale=(
                        f"Price Cap Veto (Hard Kill): Recommended {ev_res.recommended_side.value.upper()} "
                        f"ask=${target_ask:.2f} > ${self.hard_kill_price:.2f}. "
                        f"Inverted risk/reward ratio. Skipping."
                    ),
                )

            # Tier 2 Standard Cap: > $0.62 unless deep ITM (>= $80 separation)
            if target_ask > self.max_entry_price and abs(spot_diff) < 80.0:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    vpin=vpin,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_confidence,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    rationale=(
                        f"Price Cap Veto (Standard): Recommended {ev_res.recommended_side.value.upper()} "
                        f"ask=${target_ask:.2f} > ${self.max_entry_price:.2f}. "
                        f"Requires deep separation (|Diff|=${abs(spot_diff):.2f} < $80.00). Skipping."
                    ),
                )

            # Tier 3 Price Floor: < $0.30
            if target_ask < self.min_entry_price:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    macro_regime=macro_regime,
                    trend_1h_pct=trend_1h_pct,
                    trend_15m_pct=trend_15m_pct,
                    vpin=vpin,
                    onnx_signal=onnx_signal,
                    onnx_confidence=onnx_confidence,
                    onnx_prob_long=onnx_prob_long,
                    onnx_prob_short=onnx_prob_short,
                    onnx_prob_wait=onnx_prob_wait,
                    rationale=(
                        f"Price Floor Veto: Recommended {ev_res.recommended_side.value.upper()} "
                        f"ask=${target_ask:.2f} < ${self.min_entry_price:.2f} floor. "
                        f"Low-probability lottery trap. Skipping."
                    ),
                )

        is_yes = ev_res.recommended_side == OrderSide.YES
        is_no = ev_res.recommended_side == OrderSide.NO
        rec_contracts = min(effective_max_size, ev_res.recommended_contracts)

        return MacroTrendDecision(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            active_playbook=playbook_title,
            playbook_stage=stage,
            macro_regime=macro_regime,
            trend_1h_pct=round(trend_1h_pct, 2),
            trend_15m_pct=round(trend_15m_pct, 2),
            p_up=round(p_up, 4),
            p_down=round(p_down, 4),
            p_wait=round(p_wait, 4),
            vpin=round(vpin, 3),
            vpin_is_safe=vpin_is_safe,
            ev_yes=round(float(ev_res.expected_value) if is_yes else 0.0, 4),
            ev_no=round(float(ev_res.expected_value) if is_no else 0.0, 4),
            edge_yes=round(float(ev_res.statistical_edge) if is_yes else 0.0, 4),
            edge_no=round(float(ev_res.statistical_edge) if is_no else 0.0, 4),
            kelly_f_yes=round(float(ev_res.kelly_fraction) if is_yes else 0.0, 4),
            kelly_f_no=round(float(ev_res.kelly_fraction) if is_no else 0.0, 4),
            recommended_side=ev_res.recommended_side.value if ev_res.recommended_side else "wait",
            recommended_contracts=rec_contracts,
            rationale=rationale,
            edge_pct=round(float(ev_res.statistical_edge) * 100.0, 2),
            time_to_expiry_s=round(time_to_expiry_s, 1),
            spot_diff=round(spot_diff, 2),
            onnx_signal=onnx_signal,
            onnx_confidence=round(onnx_confidence, 4),
            onnx_prob_long=round(onnx_prob_long, 4),
            onnx_prob_short=round(onnx_prob_short, 4),
            onnx_prob_wait=round(onnx_prob_wait, 4),
        )

    def _build_wait_decision(
        self,
        time_to_expiry_s: float,
        spot_diff: float,
        macro_regime: str = "MACRO_CHOP",
        trend_1h_pct: float = 0.0,
        trend_15m_pct: float = 0.0,
        vpin: float = 0.15,
        vpin_is_safe: bool = True,
        rationale: str = "Waiting for macro trend & market triggers.",
        onnx_signal: str = "WAIT",
        onnx_confidence: float = 0.0,
        onnx_prob_long: float = 0.0,
        onnx_prob_short: float = 0.0,
        onnx_prob_wait: float = 0.0,
    ) -> MacroTrendDecision:
        """Construct default wait decision."""
        return MacroTrendDecision(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            active_playbook="Awaiting Macro Setup",
            playbook_stage="none",
            macro_regime=macro_regime,
            trend_1h_pct=round(trend_1h_pct, 2),
            trend_15m_pct=round(trend_15m_pct, 2),
            p_up=0.50,
            p_down=0.50,
            p_wait=0.00,
            vpin=round(vpin, 3),
            vpin_is_safe=vpin_is_safe,
            ev_yes=0.0,
            ev_no=0.0,
            edge_yes=0.0,
            edge_no=0.0,
            kelly_f_yes=0.0,
            kelly_f_no=0.0,
            recommended_side="wait",
            recommended_contracts=0,
            rationale=rationale,
            edge_pct=0.0,
            time_to_expiry_s=round(time_to_expiry_s, 1),
            spot_diff=round(spot_diff, 2),
            onnx_signal=onnx_signal,
            onnx_confidence=round(onnx_confidence, 4),
            onnx_prob_long=round(onnx_prob_long, 4),
            onnx_prob_short=round(onnx_prob_short, 4),
            onnx_prob_wait=round(onnx_prob_wait, 4),
        )

    def evaluate_exit(
        self,
        side: OrderSide | str,
        entry_price: Decimal,
        size: int,
        book: Optional[L2BookState],
        time_to_expiry_s: float,
        spot_price: float = 0.0,
        target_strike: float = 0.0,
    ) -> MacroTrendExitDecision:
        """Evaluate open position against Take-Profit and Cut-Loss Salvage rules."""
        if not book or size <= 0:
            return MacroTrendExitDecision(
                should_exit=False,
                exit_reason="NONE",
                exit_price=Decimal("0.00"),
                profit_pct=0.0,
                unrealized_pnl=Decimal("0.00"),
                rationale="No order book or zero position size.",
            )

        side_is_yes = (side == OrderSide.YES) if isinstance(side, OrderSide) else (str(side).lower() == "yes")
        best_bid = book.best_yes_bid if side_is_yes else book.best_no_bid

        if best_bid is None or best_bid <= Decimal("0.00"):
            return MacroTrendExitDecision(
                should_exit=False,
                exit_reason="NO_BID",
                exit_price=Decimal("0.00"),
                profit_pct=0.0,
                unrealized_pnl=Decimal("0.00"),
                rationale=f"Cannot exit: No active bid on the {'YES' if side_is_yes else 'NO'} book.",
            )

        safe_entry = max(Decimal("0.01"), entry_price)
        gross_pnl_per_ct = best_bid - safe_entry
        net_pnl_per_ct = gross_pnl_per_ct - self.fee_per_contract
        total_net_pnl = net_pnl_per_ct * Decimal(str(size))
        roi = float(gross_pnl_per_ct / safe_entry)
        spot_diff = spot_price - target_strike if (spot_price > 0 and target_strike > 0) else 0.0

        # Rule 1: Asymmetric Tail Risk Ceiling (Bid >= $0.95)
        if best_bid >= self.take_profit_price_threshold and net_pnl_per_ct > Decimal("0.00"):
            return MacroTrendExitDecision(
                should_exit=True,
                exit_reason="TAKE_PROFIT_CEILING",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"🎯 [TAKE PROFIT CEILING] Best bid ${best_bid:.2f} >= ${self.take_profit_price_threshold:.2f} | "
                    f"Net profit +${total_net_pnl:.2f} (+{roi*100:.1f}% ROI) | "
                    f"Liquidating early to lock in 95%+ max gain."
                ),
            )

        # Rule 2: Late-Cycle Harvest (T <= 120s, Bid >= $0.85, ROI >= 15%)
        if time_to_expiry_s <= 120.0 and best_bid >= Decimal("0.85") and roi >= self.late_cycle_roi and net_pnl_per_ct > Decimal("0.00"):
            return MacroTrendExitDecision(
                should_exit=True,
                exit_reason="LATE_CYCLE_HARVEST",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"⏱️ [LATE CYCLE HARVEST] T={int(time_to_expiry_s)}s <= 120s | "
                    f"Bid ${best_bid:.2f} with +{roi*100:.1f}% ROI | "
                    f"Net profit +${total_net_pnl:.2f} | Securing gains before settlement volatility."
                ),
            )

        # Rule 3: Target ROI Harvest (ROI >= 20%, Bid >= $0.80)
        if roi >= self.min_take_profit_roi and best_bid >= Decimal("0.80") and net_pnl_per_ct > Decimal("0.00"):
            return MacroTrendExitDecision(
                should_exit=True,
                exit_reason="TAKE_PROFIT_ROI",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"💰 [TAKE PROFIT ROI] Net ROI +{roi*100:.1f}% >= +{self.min_take_profit_roi*100:.0f}% at ${best_bid:.2f} | "
                    f"Net profit +${total_net_pnl:.2f}."
                ),
            )

        # Rule 4: Late-Cycle Cut-Loss Salvage (T <= 90s, Spot broken > $50 adverse)
        is_deep_otm = False
        if side_is_yes and spot_diff <= -50.0:
            is_deep_otm = True
        elif not side_is_yes and spot_diff >= 50.0:
            is_deep_otm = True

        if time_to_expiry_s <= 90.0 and is_deep_otm and best_bid >= Decimal("0.08"):
            salvaged_amount = best_bid * Decimal(str(size))
            return MacroTrendExitDecision(
                should_exit=True,
                exit_reason="CUT_LOSS_SALVAGE",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"🛡️ [CUT LOSS SALVAGE] T={int(time_to_expiry_s)}s <= 90s | "
                    f"Spot Diff=${spot_diff:+.1f} is severely adverse | "
                    f"Salvaging ${salvaged_amount:.2f} at bid ${best_bid:.2f} to protect bankroll."
                ),
            )

        pnl_prefix = "+" if total_net_pnl >= Decimal("0.00") else "-"
        return MacroTrendExitDecision(
            should_exit=False,
            exit_reason="HOLD",
            exit_price=best_bid,
            profit_pct=round(roi * 100.0, 2),
            unrealized_pnl=round(total_net_pnl, 4),
            rationale=f"Holding position: Bid ${best_bid:.2f} (ROI: {roi*100:+.1f}%, PnL: {pnl_prefix}${abs(total_net_pnl):.2f}).",
        )
