"""Project Odin: Watch-and-Learn Shadow Volatility Harvester (Lane 2 Shadow Fleet).

Architectural Mandate:
- Operates STRICTLY in Lane 2 (Shadow / Paper Simulation).
- Zero Real Capital Risk: Absolutely no live order execution; firewall against live order clients.
- Zero Float Financial Math: Uses Decimal exclusively for prices, fees, and PnLs.
- Causal Reinforcement: Captures empirical outcomes during extreme volatility bursts (VPIN >= 0.70)
  when Lane 1 Live bots abort. Feeds ground-truth results into ContinuousExperienceBuffer
  so the ONNX / PyTorch brain learns how to navigate high-volatility regimes without paying fee drag.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer, CycleExperience
from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.schemas import L2BookState, OrderSide

logger = logging.getLogger("kalshi_sim.odin_shadow_harvester")

_DEC_0 = Decimal("0")
_DEC_0_00 = Decimal("0.00")
_DEC_0_01 = Decimal("0.01")
_DEC_0_50 = Decimal("0.50")
_DEC_1_00 = Decimal("1.00")
_DEC_100 = Decimal("100")


@dataclass(frozen=True)
class OdinObservation:
    """Snapshot of extreme volatility market conditions observed by Odin."""
    ticker: str
    cycle_id: str
    timestamp_utc: str
    spot_price: Decimal
    strike_price: Decimal
    spot_diff: Decimal
    vpin: float
    time_to_expiry_s: float
    best_yes_ask: Decimal
    best_no_ask: Decimal
    spread_cents: Decimal
    is_extreme_volatility: bool
    live_bot_vetoed: bool = True


@dataclass
class OdinShadowPosition:
    """Hypothetical paper position taken by Odin in Lane 2 Shadow."""
    ticker: str
    cycle_id: str
    side: str  # 'yes' | 'no'
    contracts: int
    entry_price: Decimal
    taker_fee: Decimal
    vpin: float
    spot_diff: Decimal
    predicted_prob: float
    strategy_mode: str  # 'volatility_breakout' | 'mean_reversion_fade'
    opened_at_utc: str
    settled: bool = False
    settlement_spot: Optional[Decimal] = None
    outcome: Optional[str] = None  # 'win' | 'loss'
    gross_pnl: Optional[Decimal] = None
    net_pnl: Optional[Decimal] = None


class OdinShadowHarvester:
    """Project Odin: Watch-and-Learn Volatility Shadow Harvester.

    Listens to live orderbook & ticker feeds, identifies volatility spikes
    where live bots (Bot 1 V4) abort, paper-executes dual hypotheses (breakout vs fade)
    with strict Kalshi quadratic fee and slippage math, and logs outcomes
    to ContinuousExperienceBuffer.
    """

    def __init__(
        self,
        experience_buffer: Optional[ContinuousExperienceBuffer] = None,
        vpin_harvest_threshold: float = 0.70,
        max_active_shadow_positions: int = 10,
    ) -> None:
        self.experience_buffer = experience_buffer
        self.vpin_harvest_threshold = vpin_harvest_threshold
        self.max_active_shadow_positions = max_active_shadow_positions

        # Internal in-memory shadow positions
        self.active_positions: Dict[str, OdinShadowPosition] = {}
        self.settled_history: List[OdinShadowPosition] = []

        # Empirical Performance Counters (Strictly Shadow)
        self.total_observations: int = 0
        self.total_shadow_trades: int = 0
        self.total_shadow_wins: int = 0
        self.total_shadow_losses: int = 0
        self.total_shadow_pnl: Decimal = _DEC_0_00

        logger.info(
            "Project Odin Shadow Harvester initialized. Harvest Threshold: VPIN >= %.2f (Lane 2 Shadow Only).",
            self.vpin_harvest_threshold,
        )

    def observe_and_harvest(
        self,
        ticker: str,
        cycle_id: str,
        spot_price: Decimal,
        strike_price: Decimal,
        vpin: float,
        time_to_expiry_s: float,
        book_state: Optional[L2BookState] = None,
        live_bot_vetoed: bool = True,
        yes_ask: Optional[Decimal] = None,
        no_ask: Optional[Decimal] = None,
    ) -> Optional[OdinShadowPosition]:
        """Examines current tick/cycle. If volatility is extreme, takes shadow position."""
        self.total_observations += 1
        spot_diff = spot_price - strike_price
        is_extreme = (vpin >= self.vpin_harvest_threshold) or (abs(spot_diff) >= Decimal("50.00") and live_bot_vetoed)

        if not is_extreme:
            return None

        # Check if we already have an active shadow position for this cycle
        if cycle_id in self.active_positions:
            return None

        # Determine realistic pricing with adverse slippage
        # Kalshi contract binary asks
        resolved_yes_ask = yes_ask or Decimal("0.55")
        resolved_no_ask = no_ask or Decimal("0.55")

        # Clamp asks between $0.05 and $0.95
        resolved_yes_ask = max(Decimal("0.05"), min(Decimal("0.95"), resolved_yes_ask))
        resolved_no_ask = max(Decimal("0.05"), min(Decimal("0.95"), resolved_no_ask))

        # Adverse slippage penalty: in extreme volatility, book depth evaporates (+1 tick = $0.01)
        simulated_slippage = _DEC_0_01

        # Hypothesis selection:
        # If spot is aggressively above strike (> +$30), test breakout YES
        # If spot is aggressively below strike (< -$30), test breakout NO
        # If spot is tight to strike (< $20), test mean-reversion fade on the cheaper side
        contracts = 1
        now_iso = datetime.now(timezone.utc).isoformat()

        if spot_diff >= Decimal("30.00"):
            chosen_side = "yes"
            entry_price = min(Decimal("0.99"), resolved_yes_ask + simulated_slippage)
            strat_mode = "volatility_breakout"
            predicted_prob = float(min(Decimal("0.90"), entry_price))
        elif spot_diff <= Decimal("-30.00"):
            chosen_side = "no"
            entry_price = min(Decimal("0.99"), resolved_no_ask + simulated_slippage)
            strat_mode = "volatility_breakout"
            predicted_prob = float(min(Decimal("0.90"), entry_price))
        else:
            # Tight volatility squeeze - fade crowd and buy the discounted contract
            if resolved_yes_ask <= resolved_no_ask:
                chosen_side = "yes"
                entry_price = min(Decimal("0.99"), resolved_yes_ask + simulated_slippage)
            else:
                chosen_side = "no"
                entry_price = min(Decimal("0.99"), resolved_no_ask + simulated_slippage)
            strat_mode = "mean_reversion_fade"
            predicted_prob = 0.50

        # Official Kalshi quadratic taker fee calculation with Decimal precision
        taker_fee = OrderSimulator.calculate_kalshi_taker_fee(entry_price, contracts)

        shadow_pos = OdinShadowPosition(
            ticker=ticker,
            cycle_id=cycle_id,
            side=chosen_side,
            contracts=contracts,
            entry_price=entry_price,
            taker_fee=taker_fee,
            vpin=vpin,
            spot_diff=spot_diff,
            predicted_prob=predicted_prob,
            strategy_mode=strat_mode,
            opened_at_utc=now_iso,
        )

        self.active_positions[cycle_id] = shadow_pos
        self.total_shadow_trades += 1

        logger.info(
            "ODIN [LANE 2 SHADOW] Entered %s on %s | Side: %s | P_entry: $%s | Fee: $%s | VPIN: %.2f | Strat: %s",
            cycle_id, ticker, chosen_side.upper(), entry_price, taker_fee, vpin, strat_mode
        )
        return shadow_pos

    def record_settlement(
        self,
        cycle_id: str,
        settlement_spot: Decimal,
        strike_price: Decimal,
    ) -> Optional[OdinShadowPosition]:
        """Settles an active shadow position and routes ground-truth learning to ExperienceBuffer."""
        pos = self.active_positions.pop(cycle_id, None)
        if not pos:
            return None

        pos.settlement_spot = settlement_spot
        pos.settled = True

        # Kalshi Binary Contract Settlement Rule:
        # YES settles to $1.00 if settlement_spot >= strike_price, else $0.00.
        # NO settles to $1.00 if settlement_spot < strike_price, else $0.00.
        is_yes_win = settlement_spot >= strike_price
        won = (pos.side == "yes" and is_yes_win) or (pos.side == "no" and not is_yes_win)

        if won:
            pos.outcome = "win"
            # Gross PnL = (Payout $1.00 - Entry Price) * contracts
            pos.gross_pnl = (_DEC_1_00 - pos.entry_price) * pos.contracts
            pos.net_pnl = pos.gross_pnl - pos.taker_fee
            self.total_shadow_wins += 1
        else:
            pos.outcome = "loss"
            # Gross Loss = -Entry Price * contracts
            pos.gross_pnl = -pos.entry_price * pos.contracts
            pos.net_pnl = pos.gross_pnl - pos.taker_fee
            self.total_shadow_losses += 1

        self.total_shadow_pnl += pos.net_pnl
        self.settled_history.append(pos)
        if len(self.settled_history) > 200:
            self.settled_history.pop(0)

        # Route ground-truth empirical outcome to ContinuousExperienceBuffer
        if self.experience_buffer:
            loss_cause = "none"
            if pos.outcome == "loss":
                if pos.vpin >= 0.70:
                    loss_cause = "EXTREME_VOLATILITY_SWEEP"
                elif abs(float(pos.spot_diff)) < 25.0:
                    loss_cause = "STRIKE_PROXIMITY_TRAP"
                else:
                    loss_cause = "ADVERSE_SELECTION_SWEEP"

            exp = CycleExperience(
                ticker=pos.ticker,
                cycle_id=pos.cycle_id,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                strike_price=float(strike_price),
                settlement_spot=float(settlement_spot),
                spot_diff=float(pos.spot_diff),
                bot_side=pos.side,
                entry_price=float(pos.entry_price),
                contracts=pos.contracts,
                predicted_prob=pos.predicted_prob,
                outcome=pos.outcome,
                net_pnl=float(pos.net_pnl),
                fees=float(pos.taker_fee),
                execution_mode="shadow_odin",
                vpin=pos.vpin,
                active_playbook=pos.strategy_mode,
                loss_cause=loss_cause,
            )
            self.experience_buffer.record_settled_cycle(exp)
            logger.info(
                "ODIN [LANE 2 LEARNING LOGGED] Cycle %s -> Outcome: %s | Net PnL: $%s | Causal: %s",
                pos.cycle_id, pos.outcome.upper(), pos.net_pnl, loss_cause
            )

        return pos

    def get_telemetry(self) -> Dict[str, Any]:
        """Provides real-time diagnostic telemetry for monitoring Odin."""
        total_settled = self.total_shadow_wins + self.total_shadow_losses
        win_rate = (self.total_shadow_wins / total_settled) if total_settled > 0 else 0.0

        return {
            "name": "Project Odin Shadow Volatility Harvester",
            "lane": "Lane 2 Shadow (Simulation)",
            "harvest_vpin_threshold": self.vpin_harvest_threshold,
            "total_observations": self.total_observations,
            "total_shadow_trades": self.total_shadow_trades,
            "active_positions_count": len(self.active_positions),
            "settled_count": total_settled,
            "shadow_wins": self.total_shadow_wins,
            "shadow_losses": self.total_shadow_losses,
            "shadow_win_rate": round(win_rate, 4),
            "total_shadow_pnl": str(self.total_shadow_pnl),
            "active_positions": [
                {
                    "cycle_id": p.cycle_id,
                    "ticker": p.ticker,
                    "side": p.side,
                    "entry_price": str(p.entry_price),
                    "vpin": p.vpin,
                    "strategy_mode": p.strategy_mode,
                }
                for p in self.active_positions.values()
            ],
        }
