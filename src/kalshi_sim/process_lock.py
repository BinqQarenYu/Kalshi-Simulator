"""Process & Mutual Exclusion Lock Manager for Kalshi Trading Engines.

Ensures that only ONE trading engine (e.g. Standalone Bot vs. Main Dashboard)
can execute live orders on the Kalshi exchange at any given time.
"""

from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import Optional, Tuple

logger = logging.getLogger("kalshi_sim.process_lock")

DEFAULT_LOCK_FILE = Path("data") / "trading_engine.lock"


def is_pid_running(pid: int) -> bool:
    """Check whether a process PID is alive across Windows and Unix."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle == 0:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                STILL_ACTIVE = 259
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def get_active_lock_holder(lock_path: Path = DEFAULT_LOCK_FILE) -> Optional[Tuple[str, int]]:
    """Return (owner, pid) if an active process holds the trading lock, else None."""
    if not lock_path.exists():
        return None
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
        owner = data.get("owner", "unknown")
        if pid and is_pid_running(pid):
            return (owner, pid)
    except Exception as e:
        logger.debug("Failed reading lock file: %s", e)
    return None


class TradingEngineLock:
    """Mutual exclusion file-lock ensuring exclusive live order routing."""

    def __init__(self, lock_path: Path = DEFAULT_LOCK_FILE, owner_name: str = "kalshi_engine") -> None:
        self.lock_path = lock_path
        self.owner_name = owner_name
        self.acquired = False

    def acquire(self, force: bool = False) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        active_holder = get_active_lock_holder(self.lock_path)
        if active_holder:
            owner, pid = active_holder
            if pid != os.getpid():
                if not force:
                    msg = (
                        f"Trading engine lock is already held by {owner} (PID: {pid}). "
                        f"Refusing execution to prevent dual live order routing. "
                        f"Stop the active process or pass force=True to override."
                    )
                    logger.error("🛑 [LOCK COLLISION] %s", msg)
                    raise RuntimeError(msg)
                else:
                    logger.warning("⚠️ [LOCK OVERRIDE] Forcing lock takeover from PID %d (%s)", pid, owner)

        payload = {
            "owner": self.owner_name,
            "pid": os.getpid(),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self.lock_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.acquired = True
        logger.info("🔒 [ENGINE LOCK ACQUIRED] Claimed by %s (PID %d)", self.owner_name, os.getpid())
        return True

    def release(self) -> None:
        if self.acquired and self.lock_path.exists():
            try:
                data = json.loads(self.lock_path.read_text(encoding="utf-8"))
                if data.get("pid") == os.getpid():
                    self.lock_path.unlink(missing_ok=True)
                    logger.info("🔓 [ENGINE LOCK RELEASED] Lock file removed for PID %d", os.getpid())
            except Exception as e:
                logger.debug("Error releasing lock: %s", e)
            self.acquired = False
