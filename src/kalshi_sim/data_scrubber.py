import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from .config import CryptoAsset

logger = logging.getLogger(__name__)

class DataScrubber:
    "\""
    Quoquo's Pet: The Always-On Data Hygiene Gatekeeper.
    Intercepts and cleanses all raw tick data from exchanges before they reach the execution engine.
    "\""
    
    # Absolute Sanity Bounds (Hardcoded zero-hallucination physics)
    SANITY_BOUNDS = {
        CryptoAsset.BTC: (Decimal("10000"), Decimal("250000")),
        CryptoAsset.ETH: (Decimal("500"), Decimal("25000")),
        CryptoAsset.SOL: (Decimal("10"), Decimal("1000")),
        CryptoAsset.DOGE: (Decimal("0.01"), Decimal("5.00")),
    }

    @staticmethod
    def scrub_tick(asset: CryptoAsset, raw_price: Any, raw_time: Optional[str] = None) -> Optional[Decimal]:
        "\""
        Takes raw tick data, sanitizes it, enforces invariants, and returns a clean Decimal.
        Returns None if the tick is invalid (glitch, stale, or malformed).
        "\""
        # 1. Type Coercion: Enforce Decimal (Zero-Float Invariant)
        try:
            if isinstance(raw_price, float):
                # Float poison detected, cast cleanly
                clean_price = Decimal(str(raw_price))
            else:
                clean_price = Decimal(raw_price)
        except (InvalidOperation, TypeError):
            logger.warning(f"?? [SCRUBBER] VETO: Invalid price format received: {raw_price}")
            return None

        # 2. Sanity Bounds (Anti-Hallucination)
        bounds = DataScrubber.SANITY_BOUNDS.get(asset)
        if bounds:
            min_bound, max_bound = bounds
            if clean_price <= min_bound or clean_price >= max_bound:
                logger.error(f"?? [SCRUBBER] EMERGENCY VETO: Price {clean_price} for {asset.value} violates reality bounds! (Glitch Catcher)")
                return None

        # 3. Staleness / Timestamp Normalization (if provided by exchange)
        if raw_time:
            try:
                # Assuming ISO format with Z or UTC timezone
                tick_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                lag = (now - tick_time).total_seconds()
                
                # If data is more than 3000ms old, drop it as stale
                if lag > 3.0:
                    logger.warning(f"?? [SCRUBBER] VETO: Stale tick detected. Lag: {lag:.2f}s. Dropping.")
                    return None
                elif lag < -2.0:
                    logger.warning(f"?? [SCRUBBER] VETO: Future tick detected (NTP Drift?). Dropping.")
                    return None
            except ValueError:
                pass # If time is unparseable, we let it slide and rely on local clock

        return clean_price
