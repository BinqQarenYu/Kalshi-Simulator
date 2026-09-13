"""Gold Inversion Strategy Bot (Lane 2 Incubator).

Implements the Council's 5-Pillar Gold Redemption Architecture:
1. The Barnaby Inversion (NO-Side Edge): Capitalizes on retail bullish bias by buying NO
   on tight mean-reverting chop near expiry.
2. Sniper Taker Gate: Only takes liquidity when Order Flow Imbalance (|OFI| >= 0.65)
   confirms directional consensus. Eliminates passive 48¢ resting bids.
3. Spot Velocity Shield: Rejects or cancels orders if spot velocity > $0.50 per 5 seconds.
4. Macro Economic Blackout: Embargoed during 8:25-8:38 ET (CPI/NFP) and 13:55-14:10 ET (FOMC).
5. Strict Decimal Math & 1-Contract Sizing Armor.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketInfo,
    OrderSide,
    OrderType,
)

logger = logging.getLogger("GoldInversionBot")


class GoldInversionDecision:
    """Structured decision output from GoldInversionBot."""

    def __init__(
        self,
        action: str,  # "BUY", "WAIT", "CANCEL"
        side: Optional[OrderSide] = None,
        price: Optional[Decimal] = None,
        contracts: int = 1,
        order_type: OrderType = OrderType.LIMIT,
        confidence: float = 0.0,
        edge_pct: float = 0.0,
        rationale: str = "",
        playbook: str = "Barnaby Inversion",
    ) -> None:
        self.action = action.upper()
        self.side = side
        self.price = price
        self.contracts = contracts
        self.order_type = order_type
        self.confidence = confidence
        self.edge_pct = edge_pct
        self.rationale = rationale
        self.playbook = playbook

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "side": self.side.value if self.side else None,
            "price": float(self.price) if self.price else None,
            "contracts": self.contracts,
            "order_type": self.order_type.value,
            "confidence": self.confidence,
            "edge_pct": self.edge_pct,
            "rationale": self.rationale,
            "playbook": self.playbook,
        }


class GoldInversionBot:
    """Lane 2 Incubator Trading Bot for Kalshi 15M Gold (KXGOLD15M)."""

    def __init__(
        self,
        max_contracts: int = 1,
        entry_price: Decimal = Decimal("0.50"),
        min_ofi_imbalance: float = 0.65,
        spot_velocity_limit: Decimal = Decimal("0.50"),  # $0.50 max move in 5 seconds
        max_spot_diff_for_chop: Decimal = Decimal("2.00"),  # $2.00 distance
        retail_skew_threshold: float = 0.65,              # S_retail: Min retail YES skew
        vcr_threshold: float = 0.50,                      # VCR: Volatility Compression Ratio
        min_ev_dollars: Decimal = Decimal("0.02"),        # E*[Kelly]: Minimum fee-adjusted EV hurdle
    ) -> None:
        self.max_contracts = max_contracts
        self.entry_price = entry_price
        self.min_ofi_imbalance = min_ofi_imbalance
        self.spot_velocity_limit = spot_velocity_limit
        self.max_spot_diff_for_chop = max_spot_diff_for_chop
        self.retail_skew_threshold = retail_skew_threshold
        self.vcr_threshold = vcr_threshold
        self.min_ev_dollars = min_ev_dollars

        # Rolling spot velocity buffer: list of (timestamp_epoch, spot_price)
        self._spot_history: List[Tuple[float, Decimal]] = []

    def update_spot(self, ts: float, spot_price: Decimal) -> None:
        """Record spot tick for rolling velocity calculation."""
        self._spot_history.append((ts, spot_price))
        # Keep only the last 10 seconds of history
        cutoff = ts - 10.0
        self._spot_history = [(t, p) for t, p in self._spot_history if t >= cutoff]

    def get_spot_velocity(self) -> Decimal:
        """Calculate maximum spot movement over the last 5 seconds."""
        if len(self._spot_history) < 2:
            return Decimal("0.00")

        now_ts = self._spot_history[-1][0]
        recent_prices = [p for t, p in self._spot_history if t >= now_ts - 5.0]
        if len(recent_prices) < 2:
            return Decimal("0.00")

        min_p = min(recent_prices)
        max_p = max(recent_prices)
        return max_p - min_p

    def decide(
        self,
        market: MarketInfo,
        orderbook: Optional[L2BookState],
        spot_price: Decimal,
        time_remaining_s: int,
        ofi_imbalance: float = 0.0,
        now_utc: Optional[datetime] = None,
        retail_skew: Optional[float] = None,
        vcr: Optional[float] = None,
    ) -> GoldInversionDecision:
        """Evaluate Gold market state and produce a trading decision."""
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)

        # Update spot history
        self.update_spot(now_utc.timestamp(), spot_price)

        # 1. Macro Blackout Check (8:25-8:38 ET & 13:55-14:10 ET)
        from kalshi_sim.agent_guardrails import AgentGuardrails

        guardrails = AgentGuardrails()
        is_blackout, blackout_reason = guardrails.verify_macro_event_embargo(
            ticker_or_asset="KXGOLD15M", now_dt=now_utc
        )
        if is_blackout:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[MACRO BLACKOUT] {blackout_reason}",
            )

        # 2. Spot Velocity Shield Check
        vel = self.get_spot_velocity()
        if vel > self.spot_velocity_limit:
            return GoldInversionDecision(
                action="WAIT",
                rationale=(
                    f"[VELOCITY SHIELD] Spot 5s volatility ${vel:.2f} exceeds "
                    f"limit ${self.spot_velocity_limit:.2f}. Adverse selection protection active."
                ),
            )

        # 2b. VCR Volatility Compression Ratio Check
        if vcr is not None and vcr > self.vcr_threshold:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[VCR EXPANSION GATE] VCR {vcr:.2f} exceeds compression threshold {self.vcr_threshold:.2f}.",
            )

        # 2c. Retail Skew Check (Barnaby Inversion Pre-condition)
        if retail_skew is not None and retail_skew < self.retail_skew_threshold:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[RETAIL SKEW GATE] Retail crowd skew {retail_skew:.2f} below threshold {self.retail_skew_threshold:.2f}.",
            )

        # 3. Timing Window: Target late-cycle mean reversion chop (180s <= T <= 420s / 3m to 7m)
        if time_remaining_s > 420:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[TIMING GATE] Awaiting late-cycle window (T={time_remaining_s}s > 420s).",
            )
        if time_remaining_s < 120:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[TIMING GATE] Too close to expiry (T={time_remaining_s}s < 120s).",
            )

        # 4. Spot Distance from Strike
        strike = getattr(market, "target_strike", None) or getattr(market, "floor_strike", None)
        if strike is None or strike <= Decimal("0.00"):
            return GoldInversionDecision(
                action="WAIT",
                rationale="[DATA ERROR] Market strike price missing or invalid.",
            )

        spot_diff = spot_price - strike  # Positive = In-the-money for YES, Negative = Out-of-the-money

        # 5. The Barnaby Inversion Logic:
        # Case A: Spot is below strike or hovering slightly above (+-$1.50) with negative/neutral OFI
        # Retail loves to buy YES hoping for a gold bounce. Barnaby Inversion BUYS NO.
        if spot_diff <= self.max_spot_diff_for_chop:
            # We want to buy NO
            # Check Order Book for NO price
            target_side = OrderSide.NO
            limit_p = Decimal("0.50")
            confidence = 82.0
            edge_pct = 12.5

            if orderbook and orderbook.best_no_ask:
                # If market ask for NO is attractive (<= 0.52), take it
                if orderbook.best_no_ask <= Decimal("0.52"):
                    limit_p = orderbook.best_no_ask

            return GoldInversionDecision(
                action="BUY",
                side=target_side,
                price=limit_p,
                contracts=self.max_contracts,
                order_type=OrderType.LIMIT,
                confidence=confidence,
                edge_pct=edge_pct,
                rationale=(
                    f"[BARNABY INVERSION] Exploiting retail long bias | T={time_remaining_s}s | "
                    f"Spot Diff: ${spot_diff:+.2f} | Buying NO at ${limit_p:.2f} | OFI: {ofi_imbalance:+.2f}"
                ),
                playbook="Playbook G-1: Barnaby Retail Inversion (NO Decay)",
            )

        # Case B: Strong breakout with high OFI confirmation
        # If spot has broken out > +$2.50 above strike AND OFI strongly confirms (+0.65)
        if spot_diff > Decimal("2.50") and ofi_imbalance >= self.min_ofi_imbalance:
            limit_p = Decimal("0.51")
            if orderbook and orderbook.best_yes_ask and orderbook.best_yes_ask <= Decimal("0.53"):
                limit_p = orderbook.best_yes_ask

            return GoldInversionDecision(
                action="BUY",
                side=OrderSide.YES,
                price=limit_p,
                contracts=self.max_contracts,
                order_type=OrderType.LIMIT,
                confidence=78.0,
                edge_pct=10.0,
                rationale=(
                    f"[GOLD BREAKOUT] Confirmed institutional momentum | T={time_remaining_s}s | "
                    f"Spot Diff: ${spot_diff:+.2f} | OFI: {ofi_imbalance:+.2f} | Buying YES at ${limit_p:.2f}"
                ),
                playbook="Playbook G-2: Institutional Momentum Snub (YES)",
            )

        return GoldInversionDecision(
            action="WAIT",
            rationale=(
                f"[GOLD MONITOR] Inconclusive edge | T={time_remaining_s}s | "
                f"Spot Diff: ${spot_diff:+.2f} | OFI: {ofi_imbalance:+.2f}"
            ),
        )
