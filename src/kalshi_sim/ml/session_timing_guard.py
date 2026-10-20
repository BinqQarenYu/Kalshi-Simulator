"""Session Timing Guard — Empirical Time-of-Day Veto & Golden Boost Engine.

Enforces institutional session gating derived from 2,249 real trades:
1. Toxic Bleed Windows (Auto-Veto):
   - 05:00 - 07:59 ET (Pre-Market Dead Zone: 23.5% WR, -$62.83 deficit, 07:00 ET is 2.7% WR)
   - 10:00 - 10:59 ET (US Cash Open Whipsaw: 24.4% WR, -$24.61 deficit)
   - 22:00 - 22:59 ET (Late Night Asia Chop: 20.7% WR, -$23.83 deficit)

2. Golden Liquidity Windows (Priority Boost):
   - 20:00 - 21:59 ET (Asia Open Momentum: 85.5% WR, +$44.32 Net PnL - #1 All-Time Best Hour)
   - 11:00 - 12:59 ET (Midday US Trend: 100% WR, +$26.04 Net PnL)
   - 02:00 - 04:59 ET (London Cash Open: 57-69% WR, +$40.37 Net PnL)
   - 16:00 - 18:59 ET (US Market Close: 59-61% WR, +$28.22 Net PnL)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import os
from typing import NamedTuple, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("kalshi_sim.session_timing_guard")


class TimingVerdict(NamedTuple):
    allowed: bool
    is_golden: bool
    is_toxic: bool
    reason: str
    hour_et: int
    session_name: str


class SessionTimingGuard:
    """Evaluates time-of-day edge and enforces automatic session vetoes / golden boosts."""

    TOXIC_HOURS = {5, 6, 7, 22}
    WHIPSAW_HOURS = {10}
    PRIME_GOLDEN_HOURS = {20, 21, 11, 12}
    SECONDARY_GOLDEN_HOURS = {2, 3, 4, 16, 17, 18}

    def __init__(self, enabled: bool = True) -> None:
        env_val = os.getenv("ENABLE_SESSION_TIMING_GUARD", "true").lower()
        self.enabled = enabled and (env_val not in ("false", "0", "off"))

    def get_current_et_datetime(self, ref_time: Optional[datetime] = None) -> datetime:
        """Return current or reference datetime localized to America/New_York (Eastern Time)."""
        if ref_time is not None:
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)
            return ref_time.astimezone(ZoneInfo("America/New_York"))
        try:
            return datetime.now(ZoneInfo("America/New_York"))
        except Exception:
            # Fallback to UTC - 4
            now_utc = datetime.now(timezone.utc)
            return now_utc.astimezone(timezone(timedelta(hours=-4)))

    def evaluate_timing(
        self,
        ref_time: Optional[datetime] = None,
        macro_regime: str = "CHOP",
        spot_diff: Optional[Decimal | float] = None,
    ) -> TimingVerdict:
        """Evaluate current cycle time against empirical win/loss session archives."""
        if not self.enabled:
            return TimingVerdict(
                allowed=True,
                is_golden=False,
                is_toxic=False,
                reason="Session timing guard disabled by configuration.",
                hour_et=-1,
                session_name="DISABLED",
            )

        now_et = self.get_current_et_datetime(ref_time)
        hour = now_et.hour
        regime_upper = (macro_regime or "CHOP").upper()
        diff_val = abs(Decimal(str(spot_diff))) if spot_diff is not None else Decimal("0.0")

        # 1. Hard Toxic Hours (05:00-07:59 ET & 22:00-22:59 ET)
        if hour in (5, 6, 7):
            return TimingVerdict(
                allowed=False,
                is_golden=False,
                is_toxic=True,
                reason=f"🛑 [TIMING VETO: PRE-MARKET DEAD ZONE] Hour {hour:02d}:00 ET has 23.5% empirical WR and -$62.83 cumulative deficit. Standing down.",
                hour_et=hour,
                session_name="PRE_MARKET_DEAD_ZONE",
            )

        if hour == 22:
            return TimingVerdict(
                allowed=False,
                is_golden=False,
                is_toxic=True,
                reason=f"🛑 [TIMING VETO: LATE NIGHT CHOP] Hour 22:00 ET has 20.7% empirical WR and -$23.83 cumulative deficit. Standing down.",
                hour_et=hour,
                session_name="LATE_NIGHT_ASIA_CHOP",
            )

        # 2. US Cash Open Whipsaw (10:00-10:59 ET): Allowed only under wide STORM
        if hour in self.WHIPSAW_HOURS:
            is_storm = "STORM" in regime_upper or "VOLCANO" in regime_upper
            wide_separation = diff_val >= Decimal("4.00")  # ETH $4 or BTC $40+
            if not (is_storm and wide_separation):
                return TimingVerdict(
                    allowed=False,
                    is_golden=False,
                    is_toxic=True,
                    reason=f"🛑 [TIMING VETO: US OPEN WHIPSAW] Hour 10:00 ET has 24.4% empirical WR (-$24.61). Vetoed unless wide STORM (|diff| >= 4.00, got {diff_val}).",
                    hour_et=hour,
                    session_name="US_OPEN_WHIPSAW",
                )

        # 3. Prime Golden Windows
        if hour in (20, 21):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: ASIA OPEN ALPHA] Hour {hour:02d}:00 ET is #1 all-time best session (85.5% WR, +$44.32 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="ASIA_OPEN_ALPHA",
            )

        if hour in (11, 12):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: US MIDDAY TREND] Hour {hour:02d}:00 ET is 100% empirical WR window (+$26.04 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="US_MIDDAY_TREND",
            )

        # 4. Secondary Golden Windows
        if hour in (2, 3, 4):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: LONDON OPEN] Hour {hour:02d}:00 ET London liquidity expansion (57-69% WR, +$40.37 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="LONDON_OPEN",
            )

        if hour in (16, 17, 18):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: US CASH CLOSE] Hour {hour:02d}:00 ET US Close flow (59-61% WR, +$28.22 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="US_CASH_CLOSE",
            )

        # 5. Standard Neutral Session
        return TimingVerdict(
            allowed=True,
            is_golden=False,
            is_toxic=False,
            reason=f"Standard session window ({hour:02d}:00 ET). Normal regime filters apply.",
            hour_et=hour,
            session_name="STANDARD_SESSION",
        )


_DEFAULT_GUARD = SessionTimingGuard()

def get_session_timing_guard() -> SessionTimingGuard:
    """Return default singleton SessionTimingGuard."""
    return _DEFAULT_GUARD
