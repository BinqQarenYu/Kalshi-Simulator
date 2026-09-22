"""Power Management and Time Formatting Utilities for Standalone Bot."""

from __future__ import annotations

import ctypes
from datetime import datetime, timedelta
import logging
import sys
from zoneinfo import ZoneInfo

from kalshi_sim.standalone_bot_modules.config import ET_ZONE

logger = logging.getLogger("StandaloneBot.Power")


def prevent_windows_sleep() -> None:
    """Keep Windows execution state active 24/7 with monitor off."""
    if sys.platform == "win32":
        try:
            try:
                import psutil
                proc = psutil.Process()
                if proc.nice() != psutil.ABOVE_NORMAL_PRIORITY_CLASS:
                    proc.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            except Exception:
                pass

            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            res = ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            )
            if res != 0:
                logger.info("🛡️ [POWER MANAGEMENT] Windows Sleep Prevention ACTIVE. System running 24/7 with external display & clamshell support.")
            else:
                logger.warning("⚠️ [POWER MANAGEMENT] SetThreadExecutionState returned 0.")
        except Exception as exc:
            logger.warning("Could not set Windows execution state: %s", exc)


def format_cycle_time_from_iso(iso_str: str) -> str:
    """Format an ISO timestamp to authentic Kalshi Eastern Time cycle interval."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        et = dt.astimezone(ET_ZONE)
        m_end = et.minute
        m_boundary = round(m_end / 15.0) * 15
        if m_boundary == 60:
            et_rounded = (et + timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0)
            m_end = 0
            hr_end = et_rounded.hour
        else:
            hr_end = et.hour
            m_end = m_boundary

        m_start = (m_end - 15) % 60
        hr_start = hr_end if m_end >= 15 else (hr_end - 1)
        ampm = "AM" if hr_end < 12 else "PM"
        hr_start_12 = hr_start % 12 or 12
        hr_end_12 = hr_end % 12 or 12
        date_str = et.strftime("%B %d")
        return f"{date_str}, {hr_start_12}:{m_start:02d} - {hr_end_12}:{m_end:02d} {ampm} ET"
    except Exception:
        return "15M Cycle"
