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
    is_warmup: bool = False
    is_shadow: bool = False


class SessionTimingGuard:
    """Evaluates time-of-day edge and enforces automatic session vetoes / golden boosts."""

    TOXIC_HOURS = {5, 6, 7, 22, 23}
    WHIPSAW_HOURS = {10}
    STANDBY_HOURS = {0, 1}
    PRIME_GOLDEN_HOURS = {20, 21, 11, 12}
    SECONDARY_GOLDEN_HOURS = {2, 3, 4, 8, 16, 17, 18}
    APPROVED_GOLDEN_HOURS = PRIME_GOLDEN_HOURS | SECONDARY_GOLDEN_HOURS

    def __init__(self, enabled: bool = True, strict_golden_only: Optional[bool] = None) -> None:
        env_val = os.getenv("ENABLE_SESSION_TIMING_GUARD", "true").lower()
        self.enabled = enabled and (env_val not in ("false", "0", "off"))
        if strict_golden_only is not None:
            self.strict_golden_only = strict_golden_only
        else:
            env_strict = os.getenv("STRICT_GOLDEN_SESSIONS_ONLY", "true").lower()
            self.strict_golden_only = env_strict in ("true", "1", "yes")

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
                is_warmup=False,
                is_shadow=False,
            )

        now_et = self.get_current_et_datetime(ref_time)
        hour = now_et.hour
        minute = now_et.minute
        hour_qatar = (hour + 7) % 24
        next_hour = (hour + 1) % 24
        next_hour_qatar = (next_hour + 7) % 24
        regime_upper = (macro_regime or "CHOP").upper()
        diff_val = abs(Decimal(str(spot_diff))) if spot_diff is not None else Decimal("0.0")

        # 0. 15-Minute Pre-Session Warm-Up Gate:
        # Exactly 15 minutes before an approved golden session (minute >= 45 of preceding hour)
        is_entering_golden = (next_hour in self.APPROVED_GOLDEN_HOURS) and (hour not in self.APPROVED_GOLDEN_HOURS)
        if minute >= 45 and is_entering_golden:
            return TimingVerdict(
                allowed=False,
                is_golden=False,
                is_toxic=False,
                reason=f"🔥 [WARM-UP BUFFER: 15-MIN PRE-SESSION] Primes orderflow feeds, ONNX inference, and feature buffers 15m before Golden Session ({next_hour_qatar:02d}:00 Qatar / {next_hour:02d}:00 ET). Ready to fire on the hour.",
                hour_et=hour,
                session_name="GOLDEN_SESSION_WARMUP",
                is_warmup=True,
                is_shadow=False,
            )

        # 1. Hard Toxic Hours (05:00-07:59 ET & 22:00-23:59 ET -> AUTO-OFF)
        if hour in (5, 6, 7):
            return TimingVerdict(
                allowed=False,
                is_golden=False,
                is_toxic=True,
                reason=f"🛑 [AUTO-OFF: PRE-MARKET DEAD ZONE] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) has 23.5% empirical WR and -$62.83 cumulative deficit. Standing down in shadow learning mode.",
                hour_et=hour,
                session_name="PRE_MARKET_DEAD_ZONE",
                is_warmup=False,
                is_shadow=True,
            )

        if hour in (22, 23):
            return TimingVerdict(
                allowed=False,
                is_golden=False,
                is_toxic=True,
                reason=f"🛑 [AUTO-OFF: LATE NIGHT CHOP] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) has 20.7% empirical WR and -$23.83 cumulative deficit. Standing down in shadow learning mode.",
                hour_et=hour,
                session_name="LATE_NIGHT_ASIA_CHOP",
                is_warmup=False,
                is_shadow=True,
            )

        # 2. US Cash Open Whipsaw (10:00-10:59 ET -> AUTO-OFF unless wide STORM)
        if hour in self.WHIPSAW_HOURS:
            is_storm = "STORM" in regime_upper or "VOLCANO" in regime_upper
            wide_separation = diff_val >= Decimal("4.00")  # ETH $4 or BTC $40+
            if is_storm and wide_separation:
                return TimingVerdict(
                    allowed=True,
                    is_golden=False,
                    is_toxic=False,
                    reason=f"🌟 [STORM OVERRIDE: US CASH OPEN] Hour 10:00 ET wide STORM exception granted (|diff| = {diff_val} >= 4.00).",
                    hour_et=hour,
                    session_name="US_OPEN_STORM_OVERRIDE",
                    is_warmup=False,
                    is_shadow=False,
                )
            return TimingVerdict(
                allowed=False,
                is_golden=False,
                is_toxic=True,
                reason=f"🛑 [AUTO-OFF: US OPEN WHIPSAW] Hour 10:00 ET ({hour_qatar:02d}:00 Qatar) has 24.4% empirical WR (-$24.61). Vetoed unless wide STORM (|diff| >= 4.00, got {diff_val}). Standing down in shadow learning mode.",
                hour_et=hour,
                session_name="US_OPEN_WHIPSAW",
                is_warmup=False,
                is_shadow=True,
            )

        # 3. Pre-Open Standby (00:00-01:59 ET / 07:00-08:59 Qatar -> Standby until 09:00 AM Qatar)
        if hour in self.STANDBY_HOURS:
            return TimingVerdict(
                allowed=False,
                is_golden=False,
                is_toxic=False,
                reason=f"⏸️ [PRE-OPEN STANDBY] Live trading begins at 09:00 AM Qatar (02:00 ET London Open). Current time is {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar). Standing down in shadow learning mode.",
                hour_et=hour,
                session_name="PRE_OPEN_STANDBY",
                is_warmup=False,
                is_shadow=True,
            )

        # 4. Prime Golden Windows
        if hour in (20, 21):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: ASIA OPEN ALPHA] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) is #1 all-time best session (85.5% WR, +$44.32 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="ASIA_OPEN_ALPHA",
            )

        if hour in (11, 12):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: US MIDDAY TREND] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) is 100% empirical WR window (+$26.04 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="US_MIDDAY_TREND",
            )

        # 5. Secondary Golden Windows
        if hour in (2, 3, 4):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: LONDON OPEN] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) London liquidity expansion (57-69% WR, +$40.37 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="LONDON_OPEN",
            )

        if hour == 8:
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: PRE-NY EXPANSION] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) US Pre-Market Economic Release Flow (64.0% WR, +$9.95 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="PRE_NY_EXPANSION",
            )

        if hour in (16, 17, 18):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: US CASH CLOSE] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) US Close flow (59-61% WR, +$28.22 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="US_CASH_CLOSE",
            )

        # 6. Strict Mode Gate for Non-Golden Sessions (Shift to Shadow Mode for Continuous ONNX Learning)
        if self.strict_golden_only:
            return TimingVerdict(
                allowed=False,
                is_golden=False,
                is_toxic=False,
                reason=f"🛑 [AUTO-OFF: NON-GOLDEN SESSION] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) is an unproven / unprofitable session window. Strict Golden Sessions policy active. Shifted to shadow mode for continuous ONNX learning.",
                hour_et=hour,
                session_name="NON_GOLDEN_SHADOW",
                is_warmup=False,
                is_shadow=True,
            )

        # 7. Standard Neutral Session (Permissive fallback)
        return TimingVerdict(
            allowed=True,
            is_golden=False,
            is_toxic=False,
            reason=f"Standard session window ({hour:02d}:00 ET / {hour_qatar:02d}:00 Qatar). Normal regime filters apply.",
            hour_et=hour,
            session_name="STANDARD_SESSION",
        )


_DEFAULT_GUARD = SessionTimingGuard()

def get_session_timing_guard() -> SessionTimingGuard:
    """Return default singleton SessionTimingGuard."""
    return _DEFAULT_GUARD
