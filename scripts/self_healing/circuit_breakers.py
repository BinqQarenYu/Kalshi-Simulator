"""
circuit_breakers.py — The 5 Responsible Circuit Breakers
Guarantees absolute safety, live trading sanctuary, and anti-thrashing.
"""

import time
import urllib.request
import json
from pathlib import Path
from typing import Tuple, Dict, Any

QUARANTINE_FILE = Path("docs/audits/quarantined_files.json")


class CircuitBreakerManager:
    def __init__(self, port: int = 8000, blackout_seconds: int = 240):
        self.status_url = f"http://localhost:{port}/api/state"
        self.blackout_seconds = blackout_seconds
        self._ensure_quarantine_db()

    def _ensure_quarantine_db(self):
        if not QUARANTINE_FILE.parent.exists():
            QUARANTINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not QUARANTINE_FILE.exists():
            QUARANTINE_FILE.write_text("{}", encoding="utf-8")

    def _load_quarantine(self) -> Dict[str, Any]:
        try:
            return json.loads(QUARANTINE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_quarantine(self, data: Dict[str, Any]):
        QUARANTINE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_file_quarantined(self, file_path: str) -> bool:
        """Circuit Breaker 5: 3-Strike Poison Pill Check."""
        db = self._load_quarantine()
        if file_path in db:
            record = db[file_path]
            # 24 hours quarantine: 86400 seconds
            if time.time() - record.get("quarantined_at", 0) < 86400:
                return True
        return False

    def record_failure_strike(self, file_path: str) -> int:
        """Records a failure strike against a file. Quarantines if strikes >= 2."""
        db = self._load_quarantine()
        record = db.get(file_path, {"strikes": 0, "quarantined_at": 0})
        record["strikes"] += 1
        if record["strikes"] >= 2:
            record["quarantined_at"] = time.time()
        db[file_path] = record
        self._save_quarantine(db)
        return record["strikes"]

    def check_live_sanctuary(self) -> Tuple[bool, str]:
        """
        Circuit Breaker 1: Live Sanctuary Mutex.
        Returns (is_safe_to_operate, reason).
        """
        try:
            req = urllib.request.Request(self.status_url, headers={"User-Agent": "AutonomousSentinel/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status != 200:
                    return False, f"Server returned HTTP {resp.status}"
                data = json.loads(resp.read().decode("utf-8"))

            # 1. Check if an active real-money trade is in progress
            port_positions = data.get("portfolio", {}).get("positions", [])
            live_positions = data.get("live_portfolio", {}).get("positions", [])
            total_positions = len(port_positions) + len(live_positions)
            if total_positions > 0:
                return False, f"Live sanctuary active: {total_positions} open positions on market."

            # 2. Check time remaining to expiry (Trade Blackout Window)
            t_rem = data.get("market", {}).get("time_left_seconds")
            if t_rem is not None and t_rem <= self.blackout_seconds:
                return False, f"Trade Blackout Window active: {t_rem}s <= {self.blackout_seconds}s to expiration."

            return True, "Safe to operate: Bot is flat and outside blackout window."

        except Exception as e:
            # If server is not responding, we fail safe: do NOT alter files
            return False, f"Mother Server unreachable: {e}"


if __name__ == "__main__":
    cb = CircuitBreakerManager()
    safe, reason = cb.check_live_sanctuary()
    print(f"[*] Circuit Breaker Status: Safe={safe} | Reason={reason}")
