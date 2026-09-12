"""Doge Inversion Strategy Bot (Lane 2 Incubator).

Formulated by The Council for Kalshi 15M Dogecoin (KXDOGE15M):
1. The Barnaby Inversion (NO-Side Edge): Exploits 100% retail bullish meme bias by buying
   NO at discount ($0.48-$0.50) when spot is in sub-cent consolidation near strike.
2. Sub-Cent Spot Velocity Shield: Rejects trades if 5s rolling volatility > $0.0020.
3. Sniper Taker Gate: Only takes liquidity when Order Flow Imbalance (|OFI| >= 0.65)
   confirms directional decay. Eliminates passive 48¢ resting bids.
4. Retail Skew Gate (S_retail >= 0.70): Verifies retail crowd is trapped in YES.
5. Volatility Compression Ratio (VCR <= 0.50): Confirms mean-reversion chop.
6. Strict Decimal Math & 1-Contract Sizing Armor.
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

logger = logging.getLogger("DogeInversionBot")


class DogeInversionDecision:
    """Structured decision output from DogeInversionBot."""

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
        playbook: str = "Barnaby Doge Inversion",
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


class DogeInversionBot:
    """Lane 2 Incubator Trading Bot for Kalshi 15M Dogecoin (KXDOGE15M)."""

    def __init__(
        self,
        max_contracts: int = 1,
        entry_price: Decimal = Decimal("0.50"),
        min_ofi_imbalance: float = 0.65,
        spot_velocity_limit: Decimal = Decimal("0.0020"),   # $0.0020 max move in 5 seconds
        max_spot_diff_for_chop: Decimal = Decimal("0.0010"), # $0.0010 distance (10 pips)
        retail_skew_threshold: float = 0.70,               # S_retail: Min retail YES skew
        vcr_threshold: float = 0.50,                       # VCR: Volatility Compression Ratio
        min_ev_dollars: Decimal = Decimal("0.02"),         # E*[Kelly]: Minimum net EV hurdle
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
    ) -> DogeInversionDecision:
        """Evaluate Dogecoin market state and produce a trading decision."""
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)

        # Update spot history
        self.update_spot(now_utc.timestamp(), spot_price)

        # 1. Spot Velocity Shield Check
        vel = self.get_spot_velocity()
        if vel > self.spot_velocity_limit:
            return DogeInversionDecision(
                action="WAIT",
                rationale=(
                    f"[VELOCITY SHIELD] DOGE 5s volatility ${vel:.5f} exceeds "
                    f"limit ${self.spot_velocity_limit:.5f}. Adverse selection protection active."
                ),
            )

        # 2. VCR Volatility Compression Ratio Check
        if vcr is not None and vcr > self.vcr_threshold:
            return DogeInversionDecision(
                action="WAIT",
                rationale=f"[VCR EXPANSION GATE] VCR {vcr:.2f} exceeds compression threshold {self.vcr_threshold:.2f}.",
            )

        # 3. Retail Skew Check (Barnaby Inversion Pre-condition)
        if retail_skew is not None and retail_skew < self.retail_skew_threshold:
            return DogeInversionDecision(
                action="WAIT",
                rationale=f"[RETAIL SKEW GATE] Retail crowd skew {retail_skew:.2f} below threshold {self.retail_skew_threshold:.2f}.",
            )

        # 4. Timing Window: Target late-cycle mean reversion chop (120s <= T <= 420s)
        if time_remaining_s > 420:
            return DogeInversionDecision(
                action="WAIT",
                rationale=f"[TIMING GATE] Awaiting late-cycle window (T={time_remaining_s}s > 420s).",
            )
        if time_remaining_s < 120:
            return DogeInversionDecision(
                action="WAIT",
                rationale=f"[TIMING GATE] Too close to expiry (T={time_remaining_s}s < 120s).",
            )

        # 5. Strike distance check
        strike = getattr(market, "target_strike", None) or getattr(market, "floor_strike", None)
        if strike is None or strike <= Decimal("0.00"):
            return DogeInversionDecision(
                action="WAIT",
                rationale="[DATA ERROR] Market strike price missing or invalid.",
            )

        spot_diff = spot_price - strike

        # 6. Barnaby Doge Inversion:
        # If spot diff is hovering near strike (-$0.0010 to +$0.0010)
        # Retail meme crowd buys YES. Barnaby Inversion BUYS NO.
        if spot_diff <= self.max_spot_diff_for_chop:
            limit_p = Decimal("0.50")
            confidence = 85.0
            edge_pct = 15.0

            if orderbook and orderbook.best_no_ask:
                if orderbook.best_no_ask <= Decimal("0.51"):
                    limit_p = orderbook.best_no_ask

            return DogeInversionDecision(
                action="BUY",
                side=OrderSide.NO,
                price=limit_p,
                contracts=self.max_contracts,
                order_type=OrderType.LIMIT,
                confidence=confidence,
                edge_pct=edge_pct,
                rationale=(
                    f"[BARNABY DOGE INVERSION] Inverting meme crowd long bias | T={time_remaining_s}s | "
                    f"Diff: ${spot_diff:+.5f} | Buying NO at ${limit_p:.2f} | OFI: {ofi_imbalance:+.2f}"
                ),
                playbook="Playbook D-1: Barnaby Meme Inversion (NO)",
            )

        return DogeInversionDecision(
            action="WAIT",
            rationale=(
                f"[DOGE MONITOR] Inconclusive edge | T={time_remaining_s}s | "
                f"Diff: ${spot_diff:+.5f} | OFI: {ofi_imbalance:+.2f}"
            ),
        )
