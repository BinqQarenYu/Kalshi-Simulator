"""Session Timing Guard — Empirical Time-of-Day Veto & Dynamic Shadow Re-Admission Engine.

Architecture:
1. Strict Golden Sessions (Base Institutional Alpha):
   - Asia Open Momentum: 20:00 - 21:59 ET (03:00 - 04:59 Qatar) -> 84.4% WR
   - US Midday Trend: 11:00 - 12:59 ET (18:00 - 19:59 Qatar) -> 100% WR
   - London Cash Open: 02:00, 04:00 ET (09:00, 11:00 Qatar) -> 57-68% WR
   - Pre-NY Economic: 08:00 ET (15:00 Qatar) -> 64.0% WR
   - US Market Close: 16:00, 18:00 ET (23:00, 01:00 Qatar) -> 59-61% WR

2. Dynamic Shadow Re-Admission & Storm Override (Looking Forward While Looking at the Past):
   - Off-peak / non-golden hours default to SHADOW MODE (model trains, evaluates ticks, zero capital risk).
   - Dynamic Storm Breakout Unlock: If market expands into a wide confirmed trend (|diff| >= $10 ETH / $85 BTC),
     the time gate dynamically grants a 1-cycle execution pass.
   - Dynamic Re-Admission Ledger (data/session_dynamic_readmission.json):
     Tracks rolling shadow performance. If an off-peak hour achieves >= 3 consecutive winning shadow cycles,
     it is promoted to PROBATIONARY_LIVE with a strict 1-loss reversion shield.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import os
from typing import NamedTuple, Optional, Dict, Any, Set
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
    is_probationary: bool = False


class SessionTimingGuard:
    """Evaluates time-of-day edge with Bayesian online adaptation and dynamic shadow re-admission."""

    TOXIC_HOURS = {5, 6, 7, 22, 23}
    WHIPSAW_HOURS = {10}
    STANDBY_HOURS = {0, 1}
    PRIME_GOLDEN_HOURS = {20, 21, 11, 12}
    SECONDARY_GOLDEN_HOURS = {2, 4, 8, 16, 18}
    APPROVED_GOLDEN_HOURS = PRIME_GOLDEN_HOURS | SECONDARY_GOLDEN_HOURS

    def __init__(
        self,
        enabled: bool = True,
        strict_golden_only: Optional[bool] = None,
        readmission_file: str = "data/session_dynamic_readmission.json"
    ) -> None:
        env_val = os.getenv("ENABLE_SESSION_TIMING_GUARD", "true").lower()
        self.enabled = enabled and (env_val not in ("false", "0", "off"))
        if strict_golden_only is not None:
            self.strict_golden_only = strict_golden_only
        else:
            env_strict = os.getenv("STRICT_GOLDEN_SESSIONS_ONLY", "true").lower()
            self.strict_golden_only = env_strict in ("true", "1", "yes")

        self.readmission_file = readmission_file
        self._dynamic_promoted_hours: Set[int] = set()
        self._load_readmission_state()

    def _load_readmission_state(self) -> None:
        """Load dynamically promoted hours from the persistent readmission ledger."""
        if not os.path.exists(self.readmission_file):
            return
        try:
            with open(self.readmission_file, "r") as f:
                data = json.load(f)
            promoted = set(data.get("promoted_hours_et", []))
            self._dynamic_promoted_hours = promoted
        except Exception as e:
            logger.warning("Could not read session readmission ledger: %s", e)

    def record_shadow_settlement(self, hour_et: int, won: bool) -> None:
        """Record shadow outcome for an hour to dynamically evaluate re-admission."""
        try:
            data: Dict[str, Any] = {"hours": {}, "promoted_hours_et": []}
            if os.path.exists(self.readmission_file):
                try:
                    with open(self.readmission_file, "r") as f:
                        data = json.load(f)
                except Exception:
                    pass

            h_key = str(hour_et)
            h_stat = data.get("hours", {}).get(h_key, {
                "consecutive_shadow_wins": 0,
                "shadow_trades": 0,
                "shadow_wins": 0,
                "status": "SHADOW"
            })

            h_stat["shadow_trades"] += 1
            if won:
                h_stat["shadow_wins"] += 1
                h_stat["consecutive_shadow_wins"] += 1
                # If 3 consecutive shadow wins, promote to PROBATIONARY_LIVE
                if h_stat["consecutive_shadow_wins"] >= 3:
                    h_stat["status"] = "PROBATIONARY_LIVE"
            else:
                h_stat["consecutive_shadow_wins"] = 0
                h_stat["status"] = "SHADOW"  # Immediate 1-loss reversion

            data["hours"][h_key] = h_stat
            promoted = [int(k) for k, v in data["hours"].items() if v.get("status") == "PROBATIONARY_LIVE"]
            data["promoted_hours_et"] = promoted
            data["last_updated"] = datetime.now(timezone.utc).isoformat()

            os.makedirs(os.path.dirname(self.readmission_file) or ".", exist_ok=True)
            with open(self.readmission_file, "w") as f:
                json.dump(data, f, indent=2)

            self._dynamic_promoted_hours = set(promoted)
        except Exception as e:
            logger.warning("Error updating session readmission ledger: %s", e)

    def get_current_et_datetime(self, ref_time: Optional[datetime] = None) -> datetime:
        """Return current or reference datetime localized to America/New_York (Eastern Time)."""
        if ref_time is not None:
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)
            return ref_time.astimezone(ZoneInfo("America/New_York"))
        try:
            return datetime.now(ZoneInfo("America/New_York"))
        except Exception:
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

        # 1. Dynamic Storm Override (Looking Forward into Live Momentum)
        # If market enters a confirmed breakout with deep cushion (|diff| >= $10 ETH / $85 BTC)
        is_storm = "STORM" in regime_upper or "VOLCANO" in regime_upper
        is_massive_breakout = diff_val >= Decimal("10.00") or diff_val >= Decimal("85.00")
        if is_storm and is_massive_breakout:
            return TimingVerdict(
                allowed=True,
                is_golden=False,
                is_toxic=False,
                reason=f"⚡ [DYNAMIC STORM OVERRIDE: LIVE REGIME MOMENTUM] Confirmed STORM breakout (|diff| = {diff_val}) overrules static time filter. Dynamic execution pass granted for hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar).",
                hour_et=hour,
                session_name="DYNAMIC_STORM_OVERRIDE",
                is_warmup=False,
                is_shadow=False,
            )

        # 2. Dynamic Shadow Re-Admission Check (Promoted via Online Experience)
        if hour in self._dynamic_promoted_hours:
            return TimingVerdict(
                allowed=True,
                is_golden=False,
                is_toxic=False,
                reason=f"🌟 [DYNAMIC RE-ADMISSION: PROBATIONARY LIVE] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) achieved >= 3 consecutive shadow wins. Unlocked on probation (1-loss reversion active).",
                hour_et=hour,
                session_name="PROBATIONARY_LIVE_ADAPTATION",
                is_warmup=False,
                is_shadow=False,
                is_probationary=True
            )

        # 3. Hard Toxic Hours (05:00-07:59 ET & 22:00-23:59 ET -> AUTO-OFF)
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

        # 4. US Cash Open Whipsaw (10:00-10:59 ET -> AUTO-OFF unless wide STORM)
        if hour in self.WHIPSAW_HOURS:
            wide_separation = diff_val >= Decimal("4.00")
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

        # 5. Pre-Open Standby (00:00-01:59 ET / 07:00-08:59 Qatar -> Standby until 09:00 AM Qatar)
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

        # 6. Prime Golden Windows
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

        # 7. Secondary Golden Windows
        if hour in (2, 4):
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

        if hour in (16, 18):
            return TimingVerdict(
                allowed=True,
                is_golden=True,
                is_toxic=False,
                reason=f"🌟 [GOLDEN TIMING: US CASH CLOSE] Hour {hour:02d}:00 ET ({hour_qatar:02d}:00 Qatar) US Close flow (59-61% WR, +$28.22 PnL). Priority Unlocked.",
                hour_et=hour,
                session_name="US_CASH_CLOSE",
            )

        # 8. Strict Mode Gate for Non-Golden Sessions (Shift to Shadow Mode for Continuous ONNX Learning)
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

        # 9. Standard Neutral Session (Permissive fallback)
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
