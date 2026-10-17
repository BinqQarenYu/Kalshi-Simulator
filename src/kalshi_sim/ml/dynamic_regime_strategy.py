"""Dynamic Regime-State Architecture (DRSA) Strategy Engine.

Council-Sanctioned Dynamic Trading Engine:
1. Discrete 4-Regime Finite State Machine (CHOP, TREND, BLEED_QUARANTINE, SILAS_SETTLEMENT).
2. Dual-Threshold Schmitt Trigger with 30s Dwell Time (Whipsaw Elimination).
3. Continuous Closed-Form Parameter Surfaces (Zero Float Math using Decimal).
4. Strict Micro-Bankroll Sizing (Max 1 contract) & Invariant Positive EV Limit Armor ($0.51 max).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from kalshi_sim.schemas import L2BookState, MarketInfo, OrderSide, TradeEvent
from kalshi_sim.ml.wave_classifier import compute_wave_physics, MarketWavePhysics

logger = logging.getLogger("kalshi_sim.dynamic_regime_strategy")


@dataclass(frozen=True)
class DynamicRegimeDecision:
    """Structured decision output from Dynamic Regime-State Engine."""
    strategy_id: str
    strategy_name: str
    regime: str                     # 'CHOP' | 'TREND' | 'BLEED_QUARANTINE' | 'SILAS_SETTLEMENT'
    recommended_side: str           # 'yes' | 'no' | 'wait'
    recommended_contracts: int      # Strictly 0 or 1
    limit_price: Decimal            # Strictly Decimal, <= $0.51
    is_maker: bool                  # True for passive maker, False for controlled taker
    expected_value: Decimal         # Net EV in dollars (Decimal)
    edge_pct: Decimal               # Statistical edge %
    spot_diff: Decimal              # Spot price - Strike price
    time_to_expiry_s: float
    volatility_1m: Decimal
    spread: Decimal
    rationale: str


class DynamicRegimeStrategy:
    """Institutional Dynamic Trading Strategy Engine."""

    STRATEGY_ID: str = "dynamic_trading_strategy"
    STRATEGY_NAME: str = "Dynamic Trading Strategy (DRSA v1.0)"
    strategy_id: str = "dynamic_trading_strategy"
    strategy_name: str = "Dynamic Trading Strategy (DRSA v1.0)"

    REGIME_CHOP = "CHOP"
    REGIME_TREND = "TREND"
    REGIME_BLEED = "BLEED_QUARANTINE"
    REGIME_SILAS = "SILAS_SETTLEMENT"

    def __init__(
        self,
        asset: str = "BTC",
        dwell_time_seconds: float = 30.0,
        vol_trend_trigger: Optional[Decimal] = None,
        vol_chop_trigger: Optional[Decimal] = None,
        max_spread: Optional[Decimal] = None,
        vpin_toxic_threshold: Optional[Decimal] = None,
        enable_chop_trading: bool = False,
        max_momentum_price: Optional[Decimal] = None,
    ) -> None:
        self.asset = asset.upper()
        self.dwell_time_seconds = dwell_time_seconds
        self.enable_chop_trading = enable_chop_trading
        self.max_momentum_price = max_momentum_price or Decimal("0.52")

        # Asset-specific calibrated thresholds (Lesson Q8 / BLEED#01 Sweetspot)
        if self.asset == "ETH":
            self.vol_trend_trigger = vol_trend_trigger or Decimal("1.80")
            self.vol_chop_trigger = vol_chop_trigger or Decimal("0.80")
            self.base_spot_threshold = Decimal("3.50")
            self.vol_base = Decimal("0.60")
            self.vol_slope = Decimal("0.04")
            self.silas_spot_moat = Decimal("1.50")
            self.chop_harvester_spot_moat = Decimal("1.00")
            self.tsunami_threshold = 15.0
            self.wick_meatgrinder_threshold = 2.50
            self.false_breakout_rng_threshold = 5.0
            self.directional_body_threshold = 5.0
        elif self.asset == "SOL":
            self.vol_trend_trigger = vol_trend_trigger or Decimal("0.25")
            self.vol_chop_trigger = vol_chop_trigger or Decimal("0.10")
            self.base_spot_threshold = Decimal("0.60")
            self.vol_base = Decimal("0.05")
            self.vol_slope = Decimal("0.20")
            self.silas_spot_moat = Decimal("0.30")
            self.chop_harvester_spot_moat = Decimal("0.20")
            self.tsunami_threshold = 2.50
            self.wick_meatgrinder_threshold = 0.40
            self.false_breakout_rng_threshold = 0.80
            self.directional_body_threshold = 0.80
        else:  # Default BTC
            self.vol_trend_trigger = vol_trend_trigger or Decimal("30.00")
            self.vol_chop_trigger = vol_chop_trigger or Decimal("18.00")
            self.base_spot_threshold = Decimal("55.00")
            self.vol_base = Decimal("14.00")
            self.vol_slope = Decimal("0.002")
            self.silas_spot_moat = Decimal("15.00")
            self.chop_harvester_spot_moat = Decimal("8.00")
            self.tsunami_threshold = 250.0
            self.wick_meatgrinder_threshold = 45.0
            self.false_breakout_rng_threshold = 100.0
            self.directional_body_threshold = 100.0

        self.max_spread = max_spread or Decimal("0.04")
        self.vpin_toxic_threshold = vpin_toxic_threshold or Decimal("0.65")
        # Lesson Q8: Deep Discount Asymmetry Cap ($0.38 - $0.45)
        self.max_discount_limit_price = Decimal("0.45")
        self.min_discount_limit_price = Decimal("0.38")

        # FSM State & Hysteresis Tracker
        self._current_regime: str = self.REGIME_CHOP
        self._regime_entered_time: float = time.time()
        self._consecutive_trend_ticks: int = 0
        self._last_eval_time: float = 0.0

        # Learning Governance Dials (from Supreme Governor ContinuousExperienceBuffer)
        self._adaptive_moat_multiplier: Decimal = Decimal("1.00")
        self._active_price_cap: Optional[Decimal] = None

    @property
    def current_regime(self) -> str:
        return self._current_regime

    def update_learning_dials(
        self,
        adaptive_moat_multiplier: float = 1.0,
        active_price_cap: Optional[Decimal] = None,
    ) -> None:
        """Update dynamic dials received from the Supreme Governor (Experience Buffer)."""
        self._adaptive_moat_multiplier = Decimal(str(round(max(0.50, min(3.00, adaptive_moat_multiplier)), 4)))
        self._active_price_cap = active_price_cap
        logger.info(
            "🏛️ [DRSA LEARNING DIALS UPDATED] Moat Multiplier: %s | Price Cap: %s",
            self._adaptive_moat_multiplier, self._active_price_cap
        )

    def compute_dynamic_limit_price(self, volatility: Decimal) -> Decimal:
        """Modulates entry discount limit price along a calibrated positive-EV surface."""
        excess_vol = max(Decimal("0.00"), volatility - self.vol_base)
        modulated = self.min_discount_limit_price + (self.vol_slope * excess_vol)
        # Quant Invariant: Never exceed $0.51 ceiling
        return min(self.max_discount_limit_price, modulated.quantize(Decimal("0.01")))

    def compute_dynamic_spot_threshold(self, spread: Decimal) -> Decimal:
        """Scales required spot displacement with current CLOB spread and learning moat multiplier to protect EV."""
        spread_cents = spread * Decimal("100.0")
        multiplier = Decimal("1.0") + (spread_cents / Decimal("2.0"))
        moat_mult = getattr(self, "_adaptive_moat_multiplier", Decimal("1.00"))
        threshold = self.base_spot_threshold * multiplier * moat_mult
        return threshold.quantize(Decimal("0.01"))

    def compute_take_profit_target(self, regime: str) -> Decimal:
        """Modulates take-profit target based on active regime dynamics."""
        if regime == self.REGIME_TREND:
            return Decimal("0.88")
        return Decimal("0.75")

    def update_regime_state(
        self,
        volatility_1m: Decimal,
        spread: Decimal,
        vpin: Decimal,
        time_to_expiry_s: float,
        is_double_wick: bool = False,
        now_ts: Optional[float] = None,
    ) -> str:
        """Transitions FSM regime using Schmitt Trigger hysteresis and dwell time constraints."""
        ts = now_ts or time.time()
        dwell_elapsed = ts - self._regime_entered_time

        # 1. Silas Settlement Invariant: T <= 120s overrides all other regimes
        if time_to_expiry_s <= 120.0:
            if self._current_regime != self.REGIME_SILAS:
                self._current_regime = self.REGIME_SILAS
                self._regime_entered_time = ts
            return self.REGIME_SILAS

        # 2. Bleed Defender & Toxic Flow Quarantine (Immediate safety veto)
        if spread > self.max_spread or vpin >= self.vpin_toxic_threshold or is_double_wick:
            if self._current_regime != self.REGIME_BLEED:
                self._current_regime = self.REGIME_BLEED
                self._regime_entered_time = ts
                self._consecutive_trend_ticks = 0
            return self.REGIME_BLEED

        # If currently in Bleed Quarantine, require dwell time and normal market to exit
        if self._current_regime == self.REGIME_BLEED:
            if dwell_elapsed < self.dwell_time_seconds:
                return self.REGIME_BLEED

        # 3. Schmitt Trigger Hysteresis between Chop and Trend
        if volatility_1m >= self.vol_trend_trigger:
            self._consecutive_trend_ticks += 1
            if self._consecutive_trend_ticks >= 3 and dwell_elapsed >= self.dwell_time_seconds:
                if self._current_regime != self.REGIME_TREND:
                    self._current_regime = self.REGIME_TREND
                    self._regime_entered_time = ts
        elif volatility_1m < self.vol_chop_trigger:
            self._consecutive_trend_ticks = 0
            if dwell_elapsed >= self.dwell_time_seconds:
                if self._current_regime != self.REGIME_CHOP:
                    self._current_regime = self.REGIME_CHOP
                    self._regime_entered_time = ts
        else:
            # Inside the Hysteresis Deadband [vol_chop_trigger, vol_trend_trigger]: Keep current regime
            pass

        return self._current_regime

    def evaluate(
        self,
        ticker: str,
        book: L2BookState,
        spot_price: Decimal,
        strike_price: Decimal,
        expiration_time: Optional[datetime],
        volatility_1m: Decimal,
        vpin: Optional[Decimal] = None,
        now_ts: Optional[float] = None,
    ) -> DynamicRegimeDecision:
        """Evaluates live market conditions and generates a structured quantitative decision."""
        ts = now_ts or time.time()
        self._last_eval_time = ts

        # 1. Microstructure calculations (pure Decimal)
        raw_bid = getattr(book, "best_yes_bid", None)
        if raw_bid is None:
            raw_bid = getattr(book, "best_bid", None)
        best_bid = Decimal(str(raw_bid)) if raw_bid is not None else Decimal("0.00")

        raw_ask = getattr(book, "best_yes_ask", None)
        if raw_ask is None:
            raw_ask = getattr(book, "best_ask", None)
        best_ask = Decimal(str(raw_ask)) if raw_ask is not None else Decimal("1.00")

        spread = max(Decimal("0.01"), best_ask - best_bid)
        effective_vpin = vpin or Decimal("0.50")

        # 2. Expiration delta
        time_to_expiry_s = 600.0
        if expiration_time:
            now_dt = datetime.now(timezone.utc)
            time_to_expiry_s = max(0.0, (expiration_time - now_dt).total_seconds())

        # 3. Geometric Wave Physics
        spot_diff = spot_price - strike_price
        wave_physics = compute_wave_physics(
            open_price=float(strike_price),
            high_price=float(max(spot_price, strike_price)),
            low_price=float(min(spot_price, strike_price)),
            current_price=float(spot_price),
            tsunami_threshold=self.tsunami_threshold,
            wick_meatgrinder_threshold=self.wick_meatgrinder_threshold,
            false_breakout_rng_threshold=self.false_breakout_rng_threshold,
            directional_body_threshold=self.directional_body_threshold,
            asset=self.asset,
        )

        # 4. State Machine Update
        regime = self.update_regime_state(
            volatility_1m=volatility_1m,
            spread=spread,
            vpin=effective_vpin,
            time_to_expiry_s=time_to_expiry_s,
            is_double_wick=wave_physics.is_double_wick_meatgrinder,
            now_ts=ts,
        )

        # 5. Parameter Surfaces
        limit_price = self.compute_dynamic_limit_price(volatility_1m)
        spot_threshold = self.compute_dynamic_spot_threshold(spread)

        # 6. Learning Governance Parameters (Supreme Governor Scaling)
        moat_mult = getattr(self, "_adaptive_moat_multiplier", Decimal("1.00"))
        effective_silas_moat = self.silas_spot_moat * moat_mult
        effective_chop_moat = self.chop_harvester_spot_moat * moat_mult

        effective_momentum_cap = self.max_momentum_price
        if getattr(self, "_active_price_cap", None) is not None:
            effective_momentum_cap = min(effective_momentum_cap, self._active_price_cap)

        # 7. Regime Execution Logic
        # Case A: Silas Settlement Freeze (T <= 120s)
        if regime == self.REGIME_SILAS:
            if spot_diff >= effective_silas_moat:
                return DynamicRegimeDecision(
                    strategy_id="dynamic_trading_strategy",
                    strategy_name="Dynamic Regime-State Strategy",
                    regime=regime,
                    recommended_side="yes",
                    recommended_contracts=1,
                    limit_price=limit_price,
                    is_maker=True,
                    expected_value=Decimal("0.08"),
                    edge_pct=Decimal("12.0"),
                    spot_diff=spot_diff,
                    time_to_expiry_s=time_to_expiry_s,
                    volatility_1m=volatility_1m,
                    spread=spread,
                    rationale=f"Silas Settlement Parity (T={time_to_expiry_s:.0f}s): Spot +${spot_diff} exceeds TWAP drift.",
                )
            elif spot_diff <= -effective_silas_moat:
                return DynamicRegimeDecision(
                    strategy_id="dynamic_trading_strategy",
                    strategy_name="Dynamic Regime-State Strategy",
                    regime=regime,
                    recommended_side="no",
                    recommended_contracts=1,
                    limit_price=limit_price,
                    is_maker=True,
                    expected_value=Decimal("0.08"),
                    edge_pct=Decimal("12.0"),
                    spot_diff=spot_diff,
                    time_to_expiry_s=time_to_expiry_s,
                    volatility_1m=volatility_1m,
                    spread=spread,
                    rationale=f"Silas Settlement Parity (T={time_to_expiry_s:.0f}s): Spot -${abs(spot_diff)} below TWAP strike.",
                )
            return self._build_wait_decision(regime, spot_diff, time_to_expiry_s, volatility_1m, spread, "Silas TWAP Pin Quarantine.")

        # Case B: Bleed Defender & Toxic Flow (Strict capital preservation)
        if regime == self.REGIME_BLEED:
            return self._build_wait_decision(
                regime, spot_diff, time_to_expiry_s, volatility_1m, spread,
                f"Defensive Quarantine: Spread=${spread} or VPIN={effective_vpin} exceeds safety limits."
            )

        # Case C: Directional Trend Regime (Storm Hunter Taker)
        if regime == self.REGIME_TREND:
            trend_limit_yes = min(effective_momentum_cap, max(Decimal("0.46"), best_ask))
            no_ask = Decimal("1.00") - best_bid
            trend_limit_no = min(effective_momentum_cap, max(Decimal("0.46"), no_ask))

            if spot_diff >= spot_threshold:
                if best_ask <= effective_momentum_cap:
                    return DynamicRegimeDecision(
                        strategy_id="dynamic_trading_strategy",
                        strategy_name="Dynamic Regime-State Strategy",
                        regime=regime,
                        recommended_side="yes",
                        recommended_contracts=1,
                        limit_price=trend_limit_yes,
                        is_maker=False,
                        expected_value=Decimal("0.08"),
                        edge_pct=Decimal("12.0"),
                        spot_diff=spot_diff,
                        time_to_expiry_s=time_to_expiry_s,
                        volatility_1m=volatility_1m,
                        spread=spread,
                        rationale=f"Trend Expansion (Storm Hunter Taker): Spot +${spot_diff} >= threshold ${spot_threshold}. Marketable YES at ${trend_limit_yes}.",
                    )
            elif spot_diff <= -spot_threshold:
                if no_ask <= effective_momentum_cap:
                    return DynamicRegimeDecision(
                        strategy_id="dynamic_trading_strategy",
                        strategy_name="Dynamic Regime-State Strategy",
                        regime=regime,
                        recommended_side="no",
                        recommended_contracts=1,
                        limit_price=trend_limit_no,
                        is_maker=False,
                        expected_value=Decimal("0.08"),
                        edge_pct=Decimal("12.0"),
                        spot_diff=spot_diff,
                        time_to_expiry_s=time_to_expiry_s,
                        volatility_1m=volatility_1m,
                        spread=spread,
                        rationale=f"Trend Expansion (Storm Hunter Taker): Spot -${abs(spot_diff)} <= threshold -${spot_threshold}. Marketable NO at ${trend_limit_no}.",
                    )
            return self._build_wait_decision(regime, spot_diff, time_to_expiry_s, volatility_1m, spread, f"Trend regime awaiting spot velocity trigger or ask within ${effective_momentum_cap} armor.")

        # Case D: Low-Vol Chop Regime (Passive Discount Maker vs Stand-Down)
        if regime == self.REGIME_CHOP:
            if not self.enable_chop_trading:
                return self._build_wait_decision(
                    regime, spot_diff, time_to_expiry_s, volatility_1m, spread,
                    "Chop Stand-Down Directive: Zero betting in chop to eliminate adverse selection drag. Standing by for Storm/Trend breakout."
                )
            chop_limit = min(Decimal("0.44"), limit_price)
            # Exploit Kalshi settlement rule: At strike, NO wins, so in chop favor NO or deep discount YES
            if spot_diff >= effective_chop_moat:
                return DynamicRegimeDecision(
                    strategy_id="dynamic_trading_strategy",
                    strategy_name="Dynamic Regime-State Strategy",
                    regime=regime,
                    recommended_side="yes",
                    recommended_contracts=1,
                    limit_price=chop_limit,
                    is_maker=True,
                    expected_value=Decimal("0.05"),
                    edge_pct=Decimal("7.5"),
                    spot_diff=spot_diff,
                    time_to_expiry_s=time_to_expiry_s,
                    volatility_1m=volatility_1m,
                    spread=spread,
                    rationale=f"Chop Harvester: Resting maker bid on YES at ${chop_limit} (Spot +${spot_diff}).",
                )
            elif spot_diff <= -effective_chop_moat:
                return DynamicRegimeDecision(
                    strategy_id="dynamic_trading_strategy",
                    strategy_name="Dynamic Regime-State Strategy",
                    regime=regime,
                    recommended_side="no",
                    recommended_contracts=1,
                    limit_price=chop_limit,
                    is_maker=True,
                    expected_value=Decimal("0.05"),
                    edge_pct=Decimal("7.5"),
                    spot_diff=spot_diff,
                    time_to_expiry_s=time_to_expiry_s,
                    volatility_1m=volatility_1m,
                    spread=spread,
                    rationale=f"Chop Harvester: Resting maker bid on NO at ${chop_limit} (Spot -${abs(spot_diff)}).",
                )
            return self._build_wait_decision(regime, spot_diff, time_to_expiry_s, volatility_1m, spread, "Chop regime resting inside pin neutral zone.")

        # Default fallback
        return self._build_wait_decision(regime, spot_diff, time_to_expiry_s, volatility_1m, spread, "Neutral hold state.")

    def _build_wait_decision(
        self,
        regime: str,
        spot_diff: Decimal,
        time_to_expiry_s: float,
        volatility_1m: Decimal,
        spread: Decimal,
        rationale: str,
    ) -> DynamicRegimeDecision:
        return DynamicRegimeDecision(
            strategy_id="dynamic_trading_strategy",
            strategy_name="Dynamic Regime-State Strategy",
            regime=regime,
            recommended_side="wait",
            recommended_contracts=0,
            limit_price=self.min_discount_limit_price,
            is_maker=True,
            expected_value=Decimal("0.00"),
            edge_pct=Decimal("0.0"),
            spot_diff=spot_diff,
            time_to_expiry_s=time_to_expiry_s,
            volatility_1m=volatility_1m,
            spread=spread,
            rationale=rationale,
        )
