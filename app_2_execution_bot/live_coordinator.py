"""Cross-Bot Live Order Coordinator & CFTC Anti-Wash Trading Shield.

Ensures multiple autonomous trading bots (e.g. 3-Step Dominion and The ONNX Strategy)
can trade concurrently on a single shared Kalshi account with partitioned virtual bankrolls ($10 each)
without violating CFTC wash-trading rules, opposing position cannibalism, or micro-bankroll sizing caps.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("LiveCoordinator")

DEFAULT_COORDINATION_FILE = Path("data") / "active_cycle_coordination.json"


class LiveCoordinator:
    """Inter-process atomic coordinator enforcing anti-wash trading and cycle exposure caps."""

    def __init__(self, coord_path: Path = DEFAULT_COORDINATION_FILE) -> None:
        self.coord_path = coord_path
        self.coord_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_state(self) -> Dict[str, Any]:
        """Safely read active coordination state."""
        if not self.coord_path.exists():
            return {}
        try:
            content = self.coord_path.read_text(encoding="utf-8").strip()
            if not content:
                return {}
            return json.loads(content)
        except Exception as exc:
            logger.debug("Error reading coordination state: %s", exc)
            return {}

    def _write_state(self, state: Dict[str, Any]) -> None:
        """Atomically write state using a temporary file to avoid partial reads."""
        temp_path = self.coord_path.with_suffix(".tmp")
        try:
            temp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            temp_path.replace(self.coord_path)
        except Exception as exc:
            logger.error("Failed to write coordination state: %s", exc)

    def check_trade_permission(
        self,
        ticker: str,
        proposed_side: str,
        bot_id: str,
        requested_contracts: int = 1,
        max_combined_contracts: int = 2,
        is_live: bool = True,
    ) -> Tuple[bool, str]:
        """Validate if a proposed live order can be submitted without violating wash-trading or exposure caps.

        Returns:
            (is_permitted, rationale)
        """
        # 0. Seal of Excellence Pre-Flight Live Authorization Gate
        if is_live:
            from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
            auth_ok, auth_msg = BotDeploymentAuditor.check_live_authorization_on_disk(bot_id)
            if not auth_ok:
                veto_msg = f"SEAL OF EXCELLENCE VETO: {auth_msg}"
                logger.warning("🛡️ [SEAL OF EXCELLENCE VETO] %s rejected: %s", bot_id, veto_msg)
                return False, veto_msg

        state = self._read_state()
        if not state:
            return True, "PERMITTED_FIRST_MOVER: No active trades in flight."

        active_ticker = state.get("ticker")
        expiry_ts = state.get("expiry_ts", 0.0)

        # Check if stored state has expired (older than expiry_ts or > 20 minutes)
        now_ts = time.time()
        if expiry_ts > 0 and now_ts >= expiry_ts:
            self.clear_cycle(active_ticker)
            return True, "PERMITTED_CYCLE_EXPIRED: Prior cycle state expired."

        # If it's a completely different ticker, allow (multi-asset partitioning)
        if active_ticker and active_ticker != ticker:
            return True, f"PERMITTED_DIFFERENT_TICKER: Active trade is on {active_ticker}, requested {ticker}."

        active_side = (state.get("active_side") or "").lower()
        prop_side = proposed_side.lower()

        # 1. CFTC Anti-Wash Trading & Cross-Cannibalism Shield
        # If Bot A bought YES and Bot B proposes NO on the same ticker, STRICT VETO.
        if active_side and active_side != prop_side:
            active_trades = state.get("trades", [])
            holding_bots = [t.get("bot_id", "unknown") for t in active_trades if t.get("side") == active_side]
            bot_names = ", ".join(set(holding_bots)) or "peer bot"
            msg = (
                f"CFTC ANTI-WASH TRADING VETO: Opposing side '{active_side.upper()}' already holds active position "
                f"from [{bot_names}] on {ticker}. Opposing execution is strictly prohibited by CFTC wash-trading rules."
            )
            logger.warning("🛡️ [ANTI-WASH TRADING VETO] %s rejected for %s: %s", bot_id, prop_side.upper(), msg)
            return False, msg

        # 2. Combined Sizing Armor Check (Max 2 contracts across both bots per cycle)
        trades = state.get("trades", [])
        existing_contracts = sum(int(t.get("contracts", 1)) for t in trades)
        if existing_contracts + requested_contracts > max_combined_contracts:
            msg = (
                f"COMBINED EXPOSURE CAP VETO: Active cycle contracts ({existing_contracts}) + requested ({requested_contracts}) "
                f"exceeds multi-bot micro-bankroll cap ({max_combined_contracts} contracts max)."
            )
            logger.warning("🛡️ [EXPOSURE CAP VETO] %s rejected on %s: %s", bot_id, ticker, msg)
            return False, msg

        return True, f"PERMITTED_COOPERATIVE: Same directional bias '{prop_side.upper()}' on {ticker}."

    def record_trade(
        self,
        ticker: str,
        side: str,
        contracts: int,
        price: float,
        bot_id: str,
        expiry_ts: Optional[float] = None,
    ) -> None:
        """Atomically record an executed or resting order into the coordination registry."""
        state = self._read_state()
        now_ts = time.time()

        # If ticker changed or state empty, initialize new cycle record
        if not state or state.get("ticker") != ticker:
            state = {
                "ticker": ticker,
                "active_side": side.lower(),
                "created_ts": now_ts,
                "expiry_ts": expiry_ts or (now_ts + 900.0),
                "trades": [],
            }
        else:
            state["active_side"] = side.lower()
            if expiry_ts:
                state["expiry_ts"] = expiry_ts

        state["trades"].append({
            "bot_id": bot_id,
            "side": side.lower(),
            "contracts": contracts,
            "price": float(price),
            "timestamp": now_ts,
        })

        self._write_state(state)
        logger.info(
            "📝 [COORDINATOR RECORD] Registered %s trade for %s: %d ct %s @ $%.2f (Total trades: %d)",
            bot_id, ticker, contracts, side.upper(), price, len(state["trades"]),
        )

    def record_trade_execution(
        self,
        ticker: str,
        side: str,
        bot_id: str,
        contracts: int = 1,
        price: Any = 0.50,
        expiry_ts: Optional[float] = None,
    ) -> None:
        """Convenience alias for record_trade supporting Decimal or float prices."""
        self.record_trade(
            ticker=ticker,
            side=side,
            contracts=contracts,
            price=float(price),
            bot_id=bot_id,
            expiry_ts=expiry_ts,
        )

    def clear_cycle(self, ticker: Optional[str] = None) -> None:
        """Clear active coordination state."""
        state = self._read_state()
        if not state:
            return
        if ticker and state.get("ticker") != ticker:
            return
        try:
            if self.coord_path.exists():
                self.coord_path.unlink()
            logger.info("🧹 [COORDINATOR CLEAR] Cycle coordination state cleared for %s", ticker or "active")
        except Exception as exc:
            logger.debug("Failed clearing coordination file: %s", exc)

    def get_status(self) -> Dict[str, Any]:
        """Return human-readable summary of coordination status."""
        state = self._read_state()
        if not state:
            return {"active": False, "message": "No active live cycle locked."}
        return {
            "active": True,
            "ticker": state.get("ticker"),
            "active_side": state.get("active_side"),
            "trades_count": len(state.get("trades", [])),
            "trades": state.get("trades", []),
            "expiry_ts": state.get("expiry_ts"),
        }
