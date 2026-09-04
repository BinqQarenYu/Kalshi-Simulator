"""Agent_Token_Credit — Token/Credit Conservation & Anti-Redundancy Guardian.

Lightweight telemetry tracker for monitoring API call volume, WebSocket throughput,
tool call patterns, and computing a conservation efficiency score.
Exposes status via get_status() for the /api/state broadcast payload.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger("kalshi_sim.token_credit")


class AgentTokenCredit:
    """Token/Credit Conservation Telemetry & Governance Agent."""

    def __init__(
        self,
        max_history: int = 200,
        api_call_warn_threshold: int = 500,
        ws_msg_warn_threshold: int = 50_000,
    ) -> None:
        self._max_history = max_history
        self._api_call_warn_threshold = api_call_warn_threshold
        self._ws_msg_warn_threshold = ws_msg_warn_threshold

        # Counters — reset per session (server restart)
        self._session_start_ts: float = time.monotonic()
        self._session_start_utc: str = datetime.now(timezone.utc).isoformat()

        # REST API call tracking
        self._rest_api_calls: int = 0
        self._rest_api_calls_by_category: Dict[str, int] = {
            "market_discovery": 0,
            "balance_sync": 0,
            "order_placement": 0,
            "order_cancel": 0,
            "position_query": 0,
            "settlement_query": 0,
            "fills_query": 0,
            "snapshot_fetch": 0,
            "other": 0,
        }

        # WebSocket message tracking
        self._ws_messages_received: int = 0
        self._ws_messages_by_type: Dict[str, int] = {
            "orderbook_delta": 0,
            "orderbook_snapshot": 0,
            "ticker": 0,
            "trade": 0,
            "heartbeat": 0,
            "other": 0,
        }

        # Subagent / tool call tracking (approximate — recorded by server hooks)
        self._subagent_spawns: int = 0
        self._tool_calls_approx: int = 0

        # Redundancy detection
        self._duplicate_reads: int = 0
        self._file_read_cache: Dict[str, float] = {}  # filepath -> last_read_ts
        self._duplicate_read_window_s: float = 30.0  # reads within 30s = redundant

        # Conservation audit trail
        self._conservation_events: list[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Recording Methods (called by server hooks)
    # -------------------------------------------------------------------------

    def record_rest_api_call(self, category: str = "other") -> None:
        """Record a REST API call to Kalshi exchange."""
        self._rest_api_calls += 1
        key = category if category in self._rest_api_calls_by_category else "other"
        self._rest_api_calls_by_category[key] += 1

    def record_ws_message(self, msg_type: str = "other") -> None:
        """Record an incoming WebSocket message."""
        self._ws_messages_received += 1
        key = msg_type if msg_type in self._ws_messages_by_type else "other"
        self._ws_messages_by_type[key] += 1

    def record_subagent_spawn(self) -> None:
        """Record a subagent spawn event."""
        self._subagent_spawns += 1

    def record_tool_call(self) -> None:
        """Record an approximate tool call."""
        self._tool_calls_approx += 1

    def record_file_read(self, filepath: str) -> bool:
        """Record a file read and detect redundancy.

        Returns True if this is a duplicate read within the window.
        """
        now = time.monotonic()
        is_duplicate = False
        if filepath in self._file_read_cache:
            elapsed = now - self._file_read_cache[filepath]
            if elapsed < self._duplicate_read_window_s:
                is_duplicate = True
                self._duplicate_reads += 1
                self._conservation_events.append({
                    "type": "REDUNDANT_READ",
                    "filepath": filepath,
                    "elapsed_seconds": round(elapsed, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                if len(self._conservation_events) > self._max_history:
                    self._conservation_events.pop(0)
        self._file_read_cache[filepath] = now
        return is_duplicate

    def record_conservation_event(
        self,
        event_type: str,
        description: str,
        tokens_saved_estimate: int = 0,
    ) -> None:
        """Record a conservation event (batched calls, skipped re-read, etc)."""
        self._conservation_events.append({
            "type": event_type,
            "description": description,
            "tokens_saved_estimate": tokens_saved_estimate,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._conservation_events) > self._max_history:
            self._conservation_events.pop(0)

    # -------------------------------------------------------------------------
    # Conservation Score Computation
    # -------------------------------------------------------------------------

    def _compute_conservation_score(self) -> float:
        """Compute a conservation efficiency score (0-100%).

        Scoring rubric:
        - Start at 100
        - Deduct for redundant reads (-2 each, max -20)
        - Deduct for excessive API calls beyond threshold (-1 per 50 excess, max -20)
        - Deduct for excessive WS messages beyond threshold (-1 per 10k excess, max -10)
        - Deduct for excessive subagent spawns (-5 each beyond 3, max -25)
        """
        score = 100.0

        # Redundant reads penalty
        redundancy_penalty = min(self._duplicate_reads * 2, 20)
        score -= redundancy_penalty

        # Excessive API calls penalty
        excess_api = max(0, self._rest_api_calls - self._api_call_warn_threshold)
        api_penalty = min(excess_api / 50, 20)
        score -= api_penalty

        # Excessive WS messages penalty (informational — not directly controllable)
        excess_ws = max(0, self._ws_messages_received - self._ws_msg_warn_threshold)
        ws_penalty = min(excess_ws / 10_000, 10)
        score -= ws_penalty

        # Excessive subagent spawns penalty
        excess_spawns = max(0, self._subagent_spawns - 3)
        spawn_penalty = min(excess_spawns * 5, 25)
        score -= spawn_penalty

        return max(0.0, round(score, 1))

    # -------------------------------------------------------------------------
    # Status & Telemetry
    # -------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current conservation telemetry status dict."""
        now = time.monotonic()
        uptime_s = now - self._session_start_ts
        uptime_minutes = round(uptime_s / 60.0, 1)

        score = self._compute_conservation_score()
        if score >= 90:
            health = "EXCELLENT"
        elif score >= 70:
            health = "GOOD"
        elif score >= 50:
            health = "WARNING"
        else:
            health = "CRITICAL"

        return {
            "agent": "Agent_Token_Credit",
            "version": "1.0.0",
            "health": health,
            "conservation_score": score,
            "session_start": self._session_start_utc,
            "uptime_minutes": uptime_minutes,
            "rest_api": {
                "total_calls": self._rest_api_calls,
                "warn_threshold": self._api_call_warn_threshold,
                "calls_by_category": dict(self._rest_api_calls_by_category),
                "calls_per_minute": round(self._rest_api_calls / max(uptime_minutes, 0.1), 2),
            },
            "websocket": {
                "total_messages": self._ws_messages_received,
                "warn_threshold": self._ws_msg_warn_threshold,
                "messages_by_type": dict(self._ws_messages_by_type),
                "messages_per_minute": round(self._ws_messages_received / max(uptime_minutes, 0.1), 2),
            },
            "redundancy": {
                "duplicate_reads": self._duplicate_reads,
                "duplicate_read_window_s": self._duplicate_read_window_s,
                "tracked_files": len(self._file_read_cache),
            },
            "subagents": {
                "total_spawns": self._subagent_spawns,
                "spawn_threshold": 3,
            },
            "tool_calls_approx": self._tool_calls_approx,
            "recent_events": self._conservation_events[-10:],
        }


# ---------------------------------------------------------------------------
# Singleton accessor (follows integrity_agent.py pattern)
# ---------------------------------------------------------------------------

_singleton: Optional[AgentTokenCredit] = None


def get_token_credit_agent() -> AgentTokenCredit:
    """Get or create the singleton AgentTokenCredit instance."""
    global _singleton
    if _singleton is None:
        _singleton = AgentTokenCredit()
    return _singleton
