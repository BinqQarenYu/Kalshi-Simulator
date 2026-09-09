"""3-Step Domination Bot (Cycle-Aware Quantitative Playbook Engine).

Implements the 3 quantitative alpha playbooks formulated for Kalshi 15-Minute Bitcoin Binary Contracts:
1. Playbook 1: Early Momentum Breakout (10:00 - 15:00 remaining)
2. Playbook 2: Mid-Cycle OFI Trend Drift (4:00 - 10:00 remaining)
3. Playbook 3: Late-Cycle High-Probability Gamma Snub (0:45 - 4:00 remaining)

Integrates sub-second spot feed index parity, continuous moneyness digital option probability estimation,
VPIN adverse selection toxicity veto, and Quarter-Kelly sizing.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
from kalshi_sim.schemas import CryptoAsset, L2BookState, OrderSide, TradeEvent, get_asset_config

logger = logging.getLogger("kalshi_sim.domination_bot")


def _standard_normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function Phi(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class DominationDecision:
    """Structured decision output from the 3-Step Domination Bot."""
    strategy_id: str
    strategy_name: str
    active_playbook: str
    playbook_stage: str  # 'breakout' | 'drift' | 'gamma_snub' | 'none'
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
    order_type: str = "limit"
    limit_price: float = 0.48


@dataclass(frozen=True)
class DominationExitDecision:
    """Structured exit decision output from the 3-Step Domination Bot."""
    should_exit: bool
    exit_reason: str  # 'TAKE_PROFIT_CEILING' | 'TAKE_PROFIT_ROI' | 'LATE_CYCLE_HARVEST' | 'HOLD' | 'NO_BID' | 'NONE'
    exit_price: Decimal
    profit_pct: float
    unrealized_pnl: Decimal
    rationale: str


class ThreeStepDominationBot:
    """Institutional Cycle-Aware 3-Step Quantitative Strategy Bot."""

    STRATEGY_ID = "3_step_domination_bot"
    STRATEGY_NAME = "3-Step Domination Bot"

    def __init__(
        self,
        min_edge_pct: float = 0.06,  # 6.0% minimum edge (raised from 4% — data shows 4-6% edge trades are coin-flips)
        min_ev_dollars: Decimal = Decimal("0.02"),  # Minimum $0.02 net EV per contract
        vpin_toxic_threshold: float = 0.60,
        vpin_safe_threshold: float = 0.35,
        default_btc_1m_volatility: float = 14.0,  # $14 typical 1-min BTC spot std dev
        take_profit_price_threshold: Decimal = Decimal("0.95"),  # 95c tail risk ceiling
        min_take_profit_roi: float = 0.20,  # +20% minimum ROI for early exit
        late_cycle_roi: float = 0.15,  # +15% minimum ROI in final 120s
        fee_per_contract: Decimal = Decimal("0.01"),  # $0.01 standard taker fee for early exits
        min_spot_diff: Optional[float] = None,  # Scaled by asset if None
        max_entry_price: Decimal = Decimal("0.62"),  # $0.62 standard entry price cap (enforces >= 1.6:1 R:R)
        discount_limit_price: Decimal = Decimal("0.48"),  # Configurable discount sniper ceiling
        min_confidence: float = 0.70,  # 70% model conviction threshold
        asset: CryptoAsset | str = CryptoAsset.BTC,
    ) -> None:
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset
        cfg = get_asset_config(self.asset)

        self.min_edge_pct = min_edge_pct
        self.min_ev_dollars = min_ev_dollars
        self.vpin_toxic_threshold = vpin_toxic_threshold
        self.vpin_safe_threshold = vpin_safe_threshold
        if default_btc_1m_volatility == 14.0 and self.asset != CryptoAsset.BTC:
            self.typical_1m_volatility = float(cfg.typical_1m_volatility)
        else:
            self.typical_1m_volatility = default_btc_1m_volatility
        self.default_btc_1m_volatility = self.typical_1m_volatility  # backward compatibility
        self.take_profit_price_threshold = take_profit_price_threshold
        self.min_take_profit_roi = min_take_profit_roi
        self.late_cycle_roi = late_cycle_roi
        self.fee_per_contract = fee_per_contract
        self.min_spot_diff = min_spot_diff if min_spot_diff is not None else float(cfg.min_spot_diff)
        self.max_entry_price = Decimal(str(max_entry_price))
        self.discount_limit_price = max(Decimal("0.10"), min(Decimal("0.65"), Decimal(str(discount_limit_price))))
        self.min_confidence = min_confidence if min_confidence <= 1.0 else (min_confidence / 100.0)

        # Underlying Stage 2 EV & Quarter-Kelly Optimizer
        self._ev_engine = StatisticalEVEngine(
            min_ev_threshold=min_ev_dollars,
            min_edge_pct=min_edge_pct,
            fee_per_contract=fee_per_contract,
            fractional_kelly=0.15,  # 15% Fractional Kelly for capital preservation
            max_portfolio_risk_pct=Decimal("0.05"),  # 5% max risk per trade
            vpin_safe_threshold=vpin_safe_threshold,
            vpin_toxic_threshold=vpin_toxic_threshold,
        )

    def set_asset(self, asset: CryptoAsset | str) -> None:
        """Calibrate bot parameters for a specific crypto asset."""
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset
        cfg = get_asset_config(self.asset)
        self.min_spot_diff = float(cfg.min_spot_diff)
        self.typical_1m_volatility = float(cfg.typical_1m_volatility)
        self.default_btc_1m_volatility = self.typical_1m_volatility
        logger.info("[DOMINATION BOT] Calibrated for %s: min_spot_diff=%.6f, 1m_vol=%.6f", cfg.name, self.min_spot_diff, self.typical_1m_volatility)

    def set_discount_limit_price(self, new_price: Decimal | float | str) -> None:
        """Dynamically update the maker discount limit price ceiling."""
        dec_price = Decimal(str(new_price))
        clamped = max(Decimal("0.10"), min(Decimal("0.65"), dec_price))
        self.discount_limit_price = clamped
        logger.info("[DOMINATION BOT] Dynamic discount limit price updated to: $%s", clamped)

    def get_parameters(self) -> Dict[str, Any]:
        """Return current live strategy parameters."""
        return {
            "asset": self.asset.value if hasattr(self, "asset") else "BTC",
            "discount_limit_price": float(self.discount_limit_price),
            "momentum_max_price": float(self.max_entry_price),
            "min_confidence": round(float(self.min_confidence) * 100.0, 1) if self.min_confidence <= 1.0 else round(float(self.min_confidence), 1),
            "min_edge_pct": round(float(self.min_edge_pct) * 100.0, 1),
            "min_ev_dollars": float(self.min_ev_dollars),
            "min_spot_diff": float(self.min_spot_diff),
            "typical_1m_volatility": float(self.typical_1m_volatility),
            "vpin_toxic_threshold": round(float(self.vpin_toxic_threshold), 2),
            "take_profit_price_threshold": float(self.take_profit_price_threshold),
            "min_take_profit_roi": round(float(self.min_take_profit_roi) * 100.0, 1),
        }

    def update_parameters(
        self,
        asset: Optional[str | CryptoAsset] = None,
        discount_limit_price: Optional[float] = None,
        momentum_max_price: Optional[float] = None,
        min_confidence: Optional[float] = None,
        min_edge_pct: Optional[float] = None,
        min_ev_dollars: Optional[float] = None,
        min_spot_diff: Optional[float] = None,
        vpin_toxic_threshold: Optional[float] = None,
        take_profit_price_threshold: Optional[float] = None,
        min_take_profit_roi: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Dynamically update strategy parameters on the fly."""
        if asset is not None:
            self.set_asset(asset)
        if discount_limit_price is not None:
            self.set_discount_limit_price(discount_limit_price)
        if momentum_max_price is not None:
            self.max_entry_price = Decimal(str(max(0.50, min(0.99, float(momentum_max_price)))))
        if min_confidence is not None:
            val = float(min_confidence)
            if val > 1.0:
                val = val / 100.0
            self.min_confidence = max(0.50, min(0.99, val))
        if min_edge_pct is not None:
            val = float(min_edge_pct)
            if val > 1.0:
                val = val / 100.0
            self.min_edge_pct = max(0.01, min(0.50, val))
            self._ev_engine.min_edge_pct = self.min_edge_pct
        if min_ev_dollars is not None:
            self.min_ev_dollars = Decimal(str(max(0.005, min(0.50, float(min_ev_dollars)))))
            self._ev_engine.min_ev_threshold = self.min_ev_dollars
        if min_spot_diff is not None:
            self.min_spot_diff = max(0.0, float(min_spot_diff))
        if vpin_toxic_threshold is not None:
            self.vpin_toxic_threshold = max(0.10, min(0.95, float(vpin_toxic_threshold)))
            self._ev_engine.vpin_toxic_threshold = self.vpin_toxic_threshold
        if take_profit_price_threshold is not None:
            self.take_profit_price_threshold = Decimal(str(max(0.50, min(0.99, float(take_profit_price_threshold)))))
        if min_take_profit_roi is not None:
            val = float(min_take_profit_roi)
            if val > 1.0:
                val = val / 100.0
            self.min_take_profit_roi = max(0.05, min(1.0, val))
        logger.info("[DOMINATION BOT] Live parameters updated: %s", self.get_parameters())
        return self.get_parameters()

    def get_dynamic_proximity_threshold(
        self,
        time_to_expiry_s: float,
        cycle_duration_s: float = 900.0,
    ) -> float:
        """Compute self-calibrating time-and-volatility-scaled minimum spot distance threshold.

        Calculates the required safety moat in dollars:
            threshold = clamp(floor, z_asset * live_vol * sqrt(tau_mins), ceiling)
            where z_asset = ceiling_moat / (baseline_vol * sqrt(cycle_mins))

        - Hard Floor: Ensures we never enter within strike noise (1.15x min_spot_diff).
        - Hard Ceiling: Caps threshold at 2.15x min_spot_diff to prevent chasing impossible moats.
        - Sweet Spot: Naturally lands at ~1.36x min_spot_diff at mid-cycle across all assets (BTC, ETH, SOL, DOGE).
        - Self-Calibrating: Adapts dynamically if parameters or volatility change, with zero manual hardcoding.
        """
        tau_mins = max(0.2, time_to_expiry_s / 60.0)
        cycle_mins = max(1.0, cycle_duration_s / 60.0)

        cfg = get_asset_config(self.asset)
        baseline_vol = float(cfg.typical_1m_volatility)
        live_vol = self.typical_1m_volatility if self.typical_1m_volatility > 0 else baseline_vol

        floor_moat = self.min_spot_diff * 1.15
        ceiling_moat = self.min_spot_diff * 2.15

        expected_full_cycle_noise = baseline_vol * math.sqrt(cycle_mins)
        if expected_full_cycle_noise > 1e-9:
            z_asset = ceiling_moat / expected_full_cycle_noise
        else:
            z_asset = 1.40

        dynamic_moat = z_asset * live_vol * math.sqrt(tau_mins)

        return max(floor_moat, min(ceiling_moat, dynamic_moat))

    @staticmethod
    def _safe_market_ask(
        recommended_side: Optional[OrderSide],
        best_yes_ask: Optional[Decimal],
        best_no_ask: Optional[Decimal],
    ) -> Optional[float]:
        """Safely extract market ask float for the recommended side, never raising TypeError."""
        if recommended_side == OrderSide.YES:
            val = best_yes_ask
        elif recommended_side == OrderSide.NO:
            val = best_no_ask
        else:
            val = best_yes_ask if best_yes_ask is not None else best_no_ask
        return float(val) if val is not None else None

    def evaluate(
        self,
        book: Optional[L2BookState],
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        recent_trades: Optional[List[TradeEvent]] = None,
        total_equity: Decimal = Decimal("100.00"),
        max_position_size: int = 1,
        estimated_vpin: float = 0.15,
    ) -> DominationDecision:
        """Execute 3-step cycle analysis and determine optimal playbook execution."""
        if not book or (not book.yes_book and not book.no_book) or spot_price <= 0 or target_strike <= 0:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=0.0,
                vpin=estimated_vpin,
                rationale="3-Step Domination Bot waiting for active order book & market feeds.",
            )

        best_yes_ask = book.best_yes_ask
        best_yes_bid = book.best_yes_bid
        best_no_ask = (Decimal("1.00") - best_yes_bid) if best_yes_bid is not None else None

        spot_diff = spot_price - target_strike
        is_vpin_safe = estimated_vpin <= self.vpin_toxic_threshold

        # Step 0: VPIN Toxicity Guardrail Check
        if not is_vpin_safe:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                vpin_is_safe=False,
                rationale=f"VPIN Toxicity Veto: Score={estimated_vpin:.2f} > {self.vpin_toxic_threshold:.2f}. "
                          f"Suppressing all trades to prevent adverse whale selection.",
            )

        # Classify Active Playbook & Cycle Duration by Expiration Window
        ticker_str = (getattr(book, "market_ticker", "") or getattr(book, "ticker", "")) if book else ""
        is_5m = ("5M" in ticker_str.upper() and "15M" not in ticker_str.upper()) or "5MIN" in ticker_str.upper()
        cycle_duration_s = 300.0 if is_5m else 900.0

        cfg = get_asset_config(self.asset)

        # Step 0.5: Dynamic Volatility-Scaled Spot-Strike Distance Filter (Option A: Self-Calibrating)
        # Replaces rigid static 2x buffer with continuous volatility and time-decay moat.
        # Clamped between Hard Floor (1.15x min_spot_diff) and Hard Ceiling (2.15x min_spot_diff).
        razor_tight_threshold = self.get_dynamic_proximity_threshold(time_to_expiry_s, cycle_duration_s=cycle_duration_s)
        if abs(spot_diff) < razor_tight_threshold:
            diff_str = cfg.format_diff(spot_diff)
            thresh_str = cfg.format_price(razor_tight_threshold)
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                rationale=f"Razor-Tight Proximity Veto (Dynamic Volatility Moat): |Diff|={abs(spot_diff):.{cfg.price_decimals}f} < {thresh_str} "
                          f"({self.asset.value} vol-adjusted threshold at T={int(time_to_expiry_s)}s). "
                          f"Asset too close to strike for current volatility regime, skipping.",
            )

        # Dynamic Playbook Timing Thresholds:
        # Standard 15M cycle: P3 in [45s, 240s], P2 in (240s, 600s], P1 in (600s, 900s], lock < 45s
        # 5M Sprint cycle:    P3 in [20s, 80s],  P2 in (80s, 200s],   P1 in (200s, 300s], lock < 20s
        if is_5m:
            p3_min_s, p3_max_s = 20, 80
            p2_min_s, p2_max_s = 80, 200
            p1_min_s = 200
        else:
            p3_min_s, p3_max_s = 45, 240
            p2_min_s, p2_max_s = 240, 600
            p1_min_s = 600

        tau_mins = max(0.1, time_to_expiry_s / 60.0)

        # Candidate pricing at user discount limit ceiling (Option B - Resting Maker Limit)
        discount_price = self.discount_limit_price
        eff_yes_price = min(best_yes_ask, discount_price) if best_yes_ask is not None else discount_price
        eff_no_price = min(best_no_ask, discount_price) if best_no_ask is not None else discount_price

        # -------------------------------------------------------------------
        # PLAYBOOK 3: Late-Cycle High-Probability Gamma Snub
        # -------------------------------------------------------------------
        if p3_min_s <= time_to_expiry_s <= p3_max_s:
            stage = "gamma_snub"
            playbook_title = "Playbook 3: Late-Cycle Gamma Snub"

            # Dynamic Volatility scaling over remaining time
            tau_sqrt = math.sqrt(tau_mins)
            vol_floor_p3 = 0.285 * self.typical_1m_volatility
            expected_vol = max(vol_floor_p3, self.typical_1m_volatility * tau_sqrt)
            z_score = spot_diff / expected_vol

            # Digital Option Cumulative Probability Phi(z)
            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.001, min(0.999, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.05

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=eff_yes_price,
                best_no_ask=eff_no_price,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
                fee_override=Decimal("0.00"),
            )

            side_str = ev_res.recommended_side.value if ev_res.recommended_side else "wait"
            edge_val = float(ev_res.statistical_edge)
            diff_str = cfg.format_diff(spot_diff)

            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] High-Certainty Expiration Harvest | "
                    f"T={int(time_to_expiry_s)}s left | Spot Diff: {diff_str} | "
                    f"True Prob: {target_prob*100:.1f}% vs Discount Target: ${discount_price:.2f} | "
                    f"Net EV: +${ev_res.expected_value:.2f}/ct | Edge: {edge_val*100:+.1f}% | "
                    f"Kelly: {ev_res.kelly_fraction*100:.1f}% ({ev_res.recommended_contracts} cts)"
                )
            else:
                rationale = (
                    f"[{playbook_title}] In Range | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | True Prob: YES {prob_yes*100:.1f}% vs NO {prob_no*100:.1f}% | "
                    f"No edge exceeding {self.min_edge_pct*100:.0f}% at ${discount_price:.2f} discount."
                )

            actual_ask_p3 = self._safe_market_ask(ev_res.recommended_side, best_yes_ask, best_no_ask)
            return self._build_decision(
                playbook_title=playbook_title,
                stage=stage,
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=prob_wait,
                vpin=estimated_vpin,
                vpin_is_safe=True,
                ev_res=ev_res,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                rationale=rationale,
                actual_market_ask=actual_ask_p3,
                cycle_duration_s=cycle_duration_s,
            )

        # -------------------------------------------------------------------
        # PLAYBOOK 2: Mid-Cycle OFI Trend Drift
        # -------------------------------------------------------------------
        elif p2_min_s < time_to_expiry_s <= p2_max_s:
            stage = "drift"
            playbook_title = "Playbook 2: Mid-Cycle OFI Trend Drift"

            # Compute Order Flow Imbalance & Level-3 Book Skew using sorted depth
            bids, asks = book.get_depth(3) if hasattr(book, "get_depth") else ([], [])
            yes_vol = float(sum(lv.quantity for lv in bids)) if bids else 1.0
            no_vol = float(sum(lv.quantity for lv in asks)) if asks else 1.0
            book_skew = (yes_vol - no_vol) / max(1.0, yes_vol + no_vol)

            # Directional drift estimation combining moneyness and book skew
            tau_sqrt = math.sqrt(tau_mins)
            vol_floor_p2 = 0.714 * self.typical_1m_volatility
            book_skew_mult = 0.857 * self.typical_1m_volatility
            expected_vol = max(vol_floor_p2, self.typical_1m_volatility * tau_sqrt)
            z_score = (spot_diff + book_skew * book_skew_mult) / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.001, min(0.999, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.12

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=eff_yes_price,
                best_no_ask=eff_no_price,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
                fee_override=Decimal("0.00"),
            )

            diff_str = cfg.format_diff(spot_diff)
            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] Directional Trend Drift | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | Book Skew: {book_skew:+.2f} | "
                    f"Model Prob: {target_prob*100:.1f}% | Edge: {float(ev_res.statistical_edge)*100:+.1f}% | "
                    f"Optimal Size: {ev_res.recommended_contracts} cts"
                )
            else:
                rationale = (
                    f"[{playbook_title}] Monitoring Trend | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | Awaiting high-conviction order flow edge."
                )

            actual_ask_p2 = self._safe_market_ask(ev_res.recommended_side, best_yes_ask, best_no_ask)
            return self._build_decision(
                playbook_title=playbook_title,
                stage=stage,
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=prob_wait,
                vpin=estimated_vpin,
                vpin_is_safe=True,
                ev_res=ev_res,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                rationale=rationale,
                actual_market_ask=actual_ask_p2,
                cycle_duration_s=cycle_duration_s,
            )

        # -------------------------------------------------------------------
        # PLAYBOOK 1: Early Momentum Breakout
        # -------------------------------------------------------------------
        elif time_to_expiry_s > p1_min_s:
            stage = "breakout"
            playbook_title = "Playbook 1: Early Momentum Breakout"

            # Check for fast breakout velocity across strike
            tau_sqrt = math.sqrt(tau_mins)
            vol_floor_p1 = 1.285 * self.typical_1m_volatility
            expected_vol = max(vol_floor_p1, self.typical_1m_volatility * tau_sqrt)
            z_score = spot_diff / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.001, min(0.999, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.20

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=eff_yes_price,
                best_no_ask=eff_no_price,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
                fee_override=Decimal("0.00"),
            )

            diff_str = cfg.format_diff(spot_diff)
            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] Early Breakout Velocity | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | Confidence: {target_prob*100:.1f}% | "
                    f"Edge: {float(ev_res.statistical_edge)*100:+.1f}% | Kelly: {ev_res.kelly_fraction*100:.1f}%"
                )
            else:
                rationale = (
                    f"[{playbook_title}] Cycle Start Window | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | Scanning for momentum velocity across strike."
                )

            actual_ask_p1 = self._safe_market_ask(ev_res.recommended_side, best_yes_ask, best_no_ask)
            return self._build_decision(
                playbook_title=playbook_title,
                stage=stage,
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=prob_wait,
                vpin=estimated_vpin,
                vpin_is_safe=True,
                ev_res=ev_res,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                rationale=rationale,
                actual_market_ask=actual_ask_p1,
                cycle_duration_s=cycle_duration_s,
            )

        # Expiry lock window (< p3_min_s)
        else:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                rationale=f"Cycle Closing Window (T={int(time_to_expiry_s)}s < {p3_min_s}s). New entries locked for settlement.",
            )

    def _build_decision(
        self,
        playbook_title: str,
        stage: str,
        p_up: float,
        p_down: float,
        p_wait: float,
        vpin: float,
        vpin_is_safe: bool,
        ev_res: ExpectedValueResult,
        time_to_expiry_s: float,
        spot_diff: float,
        rationale: str,
        actual_market_ask: Optional[float] = None,
        cycle_duration_s: float = 900.0,
    ) -> DominationDecision:
        """Construct normalized DominationDecision object with dynamic price cap protection."""
        discount_price_val = float(self.discount_limit_price)

        # Dynamic Two-Tier Entry Price Cap (Q3 Winning Choice)
        if ev_res.recommended_side in (OrderSide.YES, OrderSide.NO) and ev_res.recommended_contracts > 0:
            target_prob = p_up if ev_res.recommended_side == OrderSide.YES else p_down
            if target_prob < self.min_confidence:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"AI Conviction Veto: {ev_res.recommended_side.value.upper()} model conviction={target_prob*100:.1f}% "
                        f"< {self.min_confidence*100:.0f}% threshold. Awaiting higher statistical conviction."
                    ),
                )

            target_ask = actual_market_ask if actual_market_ask is not None else float(ev_res.market_price)
            # Tier 1: Absolute hard ceiling above $0.72 (inverted R:R suicide)
            if target_ask > 0.72:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"Price Cap Veto (Hard Kill): Recommended {ev_res.recommended_side.value.upper()} ask=${target_ask:.2f} > $0.72 max ceiling. "
                        f"Inverted risk/reward ratio ({target_ask*100:.0f}c risk to win {(1.0-target_ask)*100:.0f}c). Skipping."
                    ),
                )
            cfg = get_asset_config(self.asset)
            deep_separation_diff = self.min_spot_diff * 2.3
            # Tier 2: Standard cap ($0.62) unless spot diff is deep in-the-money
            if target_ask > self.max_entry_price and abs(spot_diff) < deep_separation_diff:
                deep_sep_str = cfg.format_price(deep_separation_diff)
                diff_str = cfg.format_diff(spot_diff)
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"Price Cap Veto (Standard): Recommended {ev_res.recommended_side.value.upper()} ask=${target_ask:.2f} > ${self.max_entry_price:.2f} cap. "
                        f"Requires deep spot separation (|Diff|={diff_str} < {deep_sep_str}). Skipping."
                    ),
                )

            # Momentum Alignment Filter (P0 Fix — data: 0W/6L for contrarian NO in VOL_UP)
            # When the asset has moved meaningfully away from strike, bet WITH the direction.
            # Contrarian bets (against momentum) require 2.5x higher edge threshold.
            edge_pct = float(ev_res.statistical_edge) * 100.0
            contrarian_min_edge = 15.0  # 15% minimum edge for contrarian bets
            is_contrarian = False
            if spot_diff > self.min_spot_diff and ev_res.recommended_side == OrderSide.NO:
                # Asset above strike (VOLATILE_UP) but betting NO (price will drop) — contrarian
                is_contrarian = True
            elif spot_diff < -self.min_spot_diff and ev_res.recommended_side == OrderSide.YES:
                # Asset below strike (VOLATILE_DOWN) but betting YES (price will rise) — contrarian
                is_contrarian = True

            if is_contrarian and edge_pct < contrarian_min_edge:
                diff_str = cfg.format_diff(spot_diff)
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"Momentum Alignment Veto: {ev_res.recommended_side.value.upper()} is contrarian "
                        f"(Diff={diff_str}). Edge={edge_pct:.1f}% < {contrarian_min_edge:.0f}% "
                        f"contrarian threshold. Bet WITH momentum, not against it."
                    ),
                )

            # Marginal Zone Edge Boost (Post-Mortem Fix — 9 consecutive losses from thin-edge trades)
            # Dynamic moat catches |spot_diff| < dynamic_threshold. This secondary filter catches
            # the transition zone up to 1.5x of that threshold where signals exist but are still developing.
            # Require 12% minimum edge to filter noise trades that don't survive reversals.
            razor_tight_threshold = self.get_dynamic_proximity_threshold(time_to_expiry_s, cycle_duration_s=cycle_duration_s)
            marginal_zone_upper = razor_tight_threshold * 1.5
            marginal_min_edge = 12.0  # 12% minimum edge in marginal territory
            if abs(spot_diff) < marginal_zone_upper and edge_pct < marginal_min_edge:
                diff_str = cfg.format_diff(spot_diff)
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"Marginal Zone Veto: |Diff|={abs(spot_diff):.{cfg.price_decimals}f} < {marginal_zone_upper:.{cfg.price_decimals}f} "
                        f"(1.5x dynamic moat). Edge={edge_pct:.1f}% < {marginal_min_edge:.0f}% "
                        f"marginal threshold. Signal too weak to survive 15-min reversal risk."
                    ),
                )

        is_yes = ev_res.recommended_side == OrderSide.YES
        is_no = ev_res.recommended_side == OrderSide.NO
        chosen_side_str = ev_res.recommended_side.value if ev_res.recommended_side else "wait"
        cfg = get_asset_config(self.asset)

        if (is_yes or is_no) and ev_res.recommended_contracts > 0:
            target_side = chosen_side_str.upper()
            potential_reward = 1.0 - discount_price_val
            payoff_mult = potential_reward / discount_price_val if discount_price_val > 0 else 1.0
            target_prob = p_up if is_yes else p_down
            diff_str = cfg.format_diff(spot_diff)
            rationale = (
                f"[{playbook_title}] Discount Sniper | Resting Limit BUY {target_side} @ ${discount_price_val:.2f} ($0.00 Fee) | "
                f"T={int(time_to_expiry_s)}s left | Spot Diff: {diff_str} | "
                f"Model Prob: {target_prob*100:.1f}% | Risk: ${discount_price_val:.2f} | "
                f"Reward: +${potential_reward:.2f} ({payoff_mult:.2f}x) | Kelly: {ev_res.recommended_contracts} cts"
            )

        return DominationDecision(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            active_playbook=playbook_title,
            playbook_stage=stage,
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
            recommended_side=chosen_side_str,
            recommended_contracts=min(ev_res.recommended_contracts, 1),
            rationale=rationale,
            edge_pct=round(float(ev_res.statistical_edge) * 100.0, 2),
            time_to_expiry_s=round(time_to_expiry_s, 1),
            spot_diff=round(spot_diff, cfg.price_decimals),
            order_type="limit",
            limit_price=discount_price_val,
        )

    def _build_wait_decision(
        self,
        time_to_expiry_s: float,
        spot_diff: float,
        vpin: float = 0.15,
        vpin_is_safe: bool = True,
        rationale: str = "Waiting for market trigger conditions.",
    ) -> DominationDecision:
        """Construct default wait decision."""
        cfg = get_asset_config(self.asset)
        return DominationDecision(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            active_playbook="Awaiting Cycle Window",
            playbook_stage="none",
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
            spot_diff=round(spot_diff, cfg.price_decimals),
            order_type="limit",
            limit_price=float(self.discount_limit_price),
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
    ) -> DominationExitDecision:
        """Evaluate open position against quantitative Take-Profit and Early Liquidation rules."""
        if not book or size <= 0:
            return DominationExitDecision(
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
            return DominationExitDecision(
                should_exit=False,
                exit_reason="NO_BID",
                exit_price=Decimal("0.00"),
                profit_pct=0.0,
                unrealized_pnl=Decimal("0.00"),
                rationale=f"Cannot exit: No active bid on the {'YES' if side_is_yes else 'NO'} book to liquidate against.",
            )

        safe_entry = max(Decimal("0.01"), entry_price)
        gross_pnl_per_ct = best_bid - safe_entry
        net_pnl_per_ct = gross_pnl_per_ct - self.fee_per_contract
        total_net_pnl = net_pnl_per_ct * Decimal(str(size))
        roi = float(gross_pnl_per_ct / safe_entry)

        # Rule 1: Asymmetric Tail Risk Ceiling (e.g. Bid >= $0.95 or $0.98)
        # Eliminates holding to $1.00 when 95%+ of value is captured and remaining upside is tiny
        if best_bid >= self.take_profit_price_threshold and net_pnl_per_ct > Decimal("0.00"):
            return DominationExitDecision(
                should_exit=True,
                exit_reason="TAKE_PROFIT_CEILING",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"🎯 [TAKE PROFIT CEILING] Best bid ${best_bid:.2f} >= ${self.take_profit_price_threshold:.2f} ceiling | "
                    f"Net profit +${total_net_pnl:.2f} (+{roi*100:.1f}% ROI) | "
                    f"Liquidating early to eliminate asymmetric late-cycle reversal risk."
                ),
            )

        # Rule 2: Late-Cycle Expiration Defense (T <= 120s, Bid >= $0.85, ROI >= 15%)
        # In final 2 minutes, binary gamma risk explodes; lock in gains before unpredictable settlement
        if time_to_expiry_s <= 120.0 and best_bid >= Decimal("0.85") and roi >= self.late_cycle_roi and net_pnl_per_ct > Decimal("0.00"):
            return DominationExitDecision(
                should_exit=True,
                exit_reason="LATE_CYCLE_HARVEST",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"⏱️ [LATE CYCLE HARVEST] T={int(time_to_expiry_s)}s <= 120s | "
                    f"Bid ${best_bid:.2f} with +{roi*100:.1f}% ROI | "
                    f"Net profit +${total_net_pnl:.2f} | Locking in win before binary settlement volatility."
                ),
            )

        # Rule 3: High-Gain Target ROI Harvest (ROI >= 20% and Bid >= $0.80)
        if roi >= self.min_take_profit_roi and best_bid >= Decimal("0.80") and net_pnl_per_ct > Decimal("0.00"):
            return DominationExitDecision(
                should_exit=True,
                exit_reason="TAKE_PROFIT_ROI",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"💰 [TAKE PROFIT ROI] Net ROI +{roi*100:.1f}% >= +{self.min_take_profit_roi*100:.0f}% target at ${best_bid:.2f} | "
                    f"Net profit +${total_net_pnl:.2f} | Securing banked returns."
                ),
            )

        pnl_prefix = "+" if total_net_pnl >= Decimal("0.00") else "-"
        return DominationExitDecision(
            should_exit=False,
            exit_reason="HOLD",
            exit_price=best_bid,
            profit_pct=round(roi * 100.0, 2),
            unrealized_pnl=round(total_net_pnl, 4),
            rationale=f"Holding position: Bid ${best_bid:.2f} (ROI: {roi*100:+.1f}%, PnL: {pnl_prefix}${abs(total_net_pnl):.2f}) has not hit take-profit criteria.",
        )

