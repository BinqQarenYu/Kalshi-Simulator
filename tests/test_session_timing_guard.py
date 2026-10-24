"""Unit tests for SessionTimingGuard."""

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from kalshi_sim.ml.session_timing_guard import SessionTimingGuard, get_session_timing_guard


class TestSessionTimingGuard(unittest.TestCase):
    """Test suite for empirical session timing guard."""

    def setUp(self) -> None:
        self.guard = SessionTimingGuard(enabled=True)

    def _make_et_dt(self, hour: int, minute: int = 15) -> datetime:
        """Create UTC datetime corresponding to a specific Eastern Time hour."""
        return datetime(2026, 10, 20, hour, minute, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)

    def test_toxic_pre_market_dead_zone(self) -> None:
        """05:00 - 07:59 ET must be strictly vetoed."""
        for h in [5, 6, 7]:
            dt = self._make_et_dt(h)
            verdict = self.guard.evaluate_timing(ref_time=dt)
            self.assertFalse(verdict.allowed, f"Hour {h}:00 ET should be vetoed")
            self.assertTrue(verdict.is_toxic)
            self.assertEqual(verdict.session_name, "PRE_MARKET_DEAD_ZONE")
            self.assertIn("🛑 [AUTO-OFF: PRE-MARKET DEAD ZONE]", verdict.reason)

    def test_toxic_late_night_chop(self) -> None:
        """22:00 - 23:59 ET must be strictly vetoed."""
        for h in [22, 23]:
            dt = self._make_et_dt(h)
            verdict = self.guard.evaluate_timing(ref_time=dt)
            self.assertFalse(verdict.allowed)
            self.assertTrue(verdict.is_toxic)
            self.assertEqual(verdict.session_name, "LATE_NIGHT_ASIA_CHOP")
            self.assertIn("🛑 [AUTO-OFF: LATE NIGHT CHOP]", verdict.reason)

    def test_pre_open_standby(self) -> None:
        """00:00 - 01:59 ET (07:00 - 08:59 Qatar) must be in standby until 09:00 AM Qatar."""
        for h in [0, 1]:
            dt = self._make_et_dt(h)
            verdict = self.guard.evaluate_timing(ref_time=dt)
            self.assertFalse(verdict.allowed)
            self.assertFalse(verdict.is_toxic)
            self.assertEqual(verdict.session_name, "PRE_OPEN_STANDBY")
            self.assertIn("⏸️ [PRE-OPEN STANDBY]", verdict.reason)

    def test_us_cash_open_whipsaw(self) -> None:
        """10:00 ET is vetoed unless wide STORM."""
        dt = self._make_et_dt(10)
        # In CHOP: vetoed
        v_chop = self.guard.evaluate_timing(ref_time=dt, macro_regime="CHOP", spot_diff=Decimal("1.50"))
        self.assertFalse(v_chop.allowed)
        self.assertTrue(v_chop.is_toxic)
        self.assertEqual(v_chop.session_name, "US_OPEN_WHIPSAW")

        # In STORM with tight diff: vetoed
        v_tight = self.guard.evaluate_timing(ref_time=dt, macro_regime="STORM", spot_diff=Decimal("2.00"))
        self.assertFalse(v_tight.allowed)

        # In STORM with wide diff (>= 4.00): allowed
        v_wide = self.guard.evaluate_timing(ref_time=dt, macro_regime="STORM", spot_diff=Decimal("5.50"))
        self.assertTrue(v_wide.allowed)

    def test_prime_golden_windows(self) -> None:
        """20:00, 21:00, 11:00, 12:00 ET must be prioritized and marked golden."""
        for h in [20, 21]:
            dt = self._make_et_dt(h)
            v = self.guard.evaluate_timing(ref_time=dt)
            self.assertTrue(v.allowed)
            self.assertTrue(v.is_golden)
            self.assertEqual(v.session_name, "ASIA_OPEN_ALPHA")

        for h in [11, 12]:
            dt = self._make_et_dt(h)
            v = self.guard.evaluate_timing(ref_time=dt)
            self.assertTrue(v.allowed)
            self.assertTrue(v.is_golden)
            self.assertEqual(v.session_name, "US_MIDDAY_TREND")

    def test_secondary_golden_windows(self) -> None:
        """London Open (02, 04 ET) and US Close (16, 18 ET) must be golden."""
        for h in [2, 4]:
            dt = self._make_et_dt(h)
            v = self.guard.evaluate_timing(ref_time=dt)
            self.assertTrue(v.allowed)
            self.assertTrue(v.is_golden)
            self.assertEqual(v.session_name, "LONDON_OPEN")

        for h in [16, 18]:
            dt = self._make_et_dt(h)
            v = self.guard.evaluate_timing(ref_time=dt)
            self.assertTrue(v.allowed)
            self.assertTrue(v.is_golden)
            self.assertEqual(v.session_name, "US_CASH_CLOSE")

    def test_pre_ny_expansion(self) -> None:
        """Hour 08:00 ET (15:00 Qatar) pre-NY flow must be golden."""
        dt = self._make_et_dt(8)
        v = self.guard.evaluate_timing(ref_time=dt)
        self.assertTrue(v.allowed)
        self.assertTrue(v.is_golden)
        self.assertEqual(v.session_name, "PRE_NY_EXPANSION")
        self.assertIn("🌟 [GOLDEN TIMING: PRE-NY EXPANSION]", v.reason)

    def test_strict_golden_non_golden_veto(self) -> None:
        """Non-golden hours (9, 13, 14, 19) must be auto-vetoed under strict golden policy and shifted to shadow."""
        strict_guard = SessionTimingGuard(enabled=True, strict_golden_only=True)
        for h in [9, 13, 14, 19]:
            dt = self._make_et_dt(h)
            v = strict_guard.evaluate_timing(ref_time=dt)
            self.assertFalse(v.allowed)
            self.assertFalse(v.is_golden)
            self.assertTrue(v.is_shadow)
            self.assertEqual(v.session_name, "NON_GOLDEN_SHADOW")
            self.assertIn("🛑 [AUTO-OFF: NON-GOLDEN SESSION]", v.reason)

    def test_15_minute_pre_session_warmup(self) -> None:
        """At 15 minutes before an approved golden session (minute >= 45), warm-up must activate."""
        # 10:45 ET is 15 minutes before 11:00 ET (US Midday Trend)
        dt_warmup = self._make_et_dt(10, 45)
        v = self.guard.evaluate_timing(ref_time=dt_warmup)
        self.assertFalse(v.allowed)
        self.assertTrue(v.is_warmup)
        self.assertFalse(v.is_shadow)
        self.assertEqual(v.session_name, "GOLDEN_SESSION_WARMUP")
        self.assertIn("🔥 [WARM-UP BUFFER: 15-MIN PRE-SESSION]", v.reason)

        # 01:50 ET is 10 minutes before 02:00 ET (London Open)
        dt_london_warmup = self._make_et_dt(1, 50)
        v2 = self.guard.evaluate_timing(ref_time=dt_london_warmup)
        self.assertFalse(v2.allowed)
        self.assertTrue(v2.is_warmup)
        self.assertFalse(v2.is_shadow)
        self.assertEqual(v2.session_name, "GOLDEN_SESSION_WARMUP")

    def test_shift_to_shadow_after_profitable_window(self) -> None:
        """Immediately after golden window concludes (e.g. 13:00 ET after 12:00 ET), shift to shadow mode."""
        strict_guard = SessionTimingGuard(enabled=True, strict_golden_only=True)
        dt_after = self._make_et_dt(13, 5)
        v = strict_guard.evaluate_timing(ref_time=dt_after)
        self.assertFalse(v.allowed)
        self.assertTrue(v.is_shadow)
        self.assertFalse(v.is_warmup)
        self.assertEqual(v.session_name, "NON_GOLDEN_SHADOW")


if __name__ == "__main__":
    unittest.main()
