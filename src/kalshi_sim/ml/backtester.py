"""Automated Strategy Backtester & Model Comparator for Kalshi Trading Models.

Simulates historical tick replay against candidate ONNX / ML models, applying
microstructure feature extraction, Statistical EV calculation, VPIN-tapered Kelly sizing,
and realistic exchange execution fees. Computes institutional metrics: Sharpe, Sortino, Max Drawdown, Win Rate.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import onnxruntime as ort

from kalshi_sim.ml.dataset_builder import DatasetBuilder, TickFrame
from kalshi_sim.ml.statistical_ev_engine import StatisticalEVEngine
from kalshi_sim.schemas import OrderSide

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Record of a simulated backtest trade."""
    step: int
    ticker: str
    side: OrderSide
    size: int
    entry_price: float
    exit_price: float
    pnl: float
    fees: float
    vpin: float
    kelly_f: float
    is_win: bool


@dataclass
class BacktestResult:
    """Comprehensive performance statistics for a backtest run."""
    model_name: str
    initial_capital: float
    final_capital: float
    total_net_pnl: float
    total_roi_pct: float
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    total_fees_paid: float
    equity_curve: List[float] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)


class BacktestEngine:
    """Simulates trading strategy execution across historical tick frames."""

    def __init__(
        self,
        onnx_model_path: Optional[Union[str, Path]] = None,
        starting_capital: float = 10000.0,
        holding_horizon: int = 15,
        min_ev_threshold: float = 0.015,
        fee_per_contract: float = 0.01,
    ) -> None:
        self.onnx_model_path = Path(onnx_model_path) if onnx_model_path else None
        self.starting_capital = starting_capital
        self.holding_horizon = holding_horizon
        self.min_ev_threshold = min_ev_threshold
        self.fee_per_contract = fee_per_contract

        self.session: Optional[ort.InferenceSession] = None
        self.input_name: Optional[str] = None
        if self.onnx_model_path and self.onnx_model_path.exists():
            self.session = ort.InferenceSession(str(self.onnx_model_path), providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name

        self.ev_engine = StatisticalEVEngine(
            min_ev_threshold=Decimal(str(min_ev_threshold)),
            fractional_kelly=0.25,
        )

    def predict_probabilities(self, features: np.ndarray) -> Tuple[float, float, float]:
        """Generate [P(UP), P(DOWN), P(WAIT)] predictions from model or baseline."""
        if self.session and self.input_name:
            x_in = features.reshape(1, -1).astype(np.float32)
            probs = self.session.run(None, {self.input_name: x_in})[0][0]
            return float(probs[0]), float(probs[1]), float(probs[2])
        # Neutral baseline if no model provided
        return 0.333, 0.333, 0.334

    def run(self, frames: List[TickFrame], model_name: str = "CandidateModel") -> BacktestResult:
        """Run sequential tick replay simulation over provided TickFrames."""
        n_frames = len(frames)
        capital = self.starting_capital
        equity_curve: List[float] = [capital]
        trades: List[BacktestTrade] = []
        step_returns: List[float] = []

        peak_capital = capital
        max_drawdown = 0.0

        i = 0
        while i < (n_frames - self.holding_horizon):
            current_frame = frames[i]
            future_frame = frames[i + self.holding_horizon]

            p_up, p_down, p_wait = self.predict_probabilities(current_frame.features)

            # Approximate VPIN from feature 6 (VPIN PBC)
            vpin_val = float(np.clip(current_frame.features[6], 0.0, 1.0)) if len(current_frame.features) > 6 else 0.5

            yes_ask_dec = Decimal(str(round(current_frame.mid_price, 4)))
            no_ask_dec = Decimal(str(round(1.0 - current_frame.mid_price, 4)))

            ev_res = self.ev_engine.compute_optimal_execution(
                prob_up=p_up,
                prob_down=p_down,
                best_yes_ask=yes_ask_dec,
                best_no_ask=no_ask_dec,
                total_equity=Decimal(str(round(capital, 2))),
                vpin=vpin_val,
                prob_wait=p_wait,
            )

            # Check if signal recommends a trade
            if ev_res.has_positive_edge and ev_res.recommended_side in (OrderSide.YES, OrderSide.NO):
                trade_side = ev_res.recommended_side
                entry_price = current_frame.mid_price
                if trade_side == OrderSide.NO:
                    entry_price = 1.0 - entry_price

                # Determine sizing based on Kelly fraction (subject to 10% capital cap)
                kelly_pct = ev_res.kelly_fraction
                position_capital = capital * min(0.10, kelly_pct)
                contracts = max(1, int(position_capital / max(0.05, entry_price)))

                # Determine outcome at settlement horizon
                future_mid = future_frame.mid_price
                if trade_side == OrderSide.YES:
                    is_win = future_mid >= (current_frame.mid_price + 0.005)
                    exit_price = 1.0 if is_win else 0.0
                else:
                    is_win = future_mid <= (current_frame.mid_price - 0.005)
                    exit_price = 1.0 if is_win else 0.0

                fee_total = contracts * self.fee_per_contract
                gross_pnl = contracts * (exit_price - entry_price)
                net_pnl = gross_pnl - fee_total

                capital += net_pnl
                equity_curve.append(capital)
                step_returns.append(net_pnl / (contracts * entry_price + 1e-9))

                trades.append(
                    BacktestTrade(
                        step=i,
                        ticker=current_frame.ticker,
                        side=trade_side,
                        size=contracts,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        pnl=net_pnl,
                        fees=fee_total,
                        vpin=vpin_val,
                        kelly_f=kelly_pct,
                        is_win=is_win,
                    )
                )

                # Skip to end of horizon to prevent overlapping trades
                i += self.holding_horizon
            else:
                i += 1

            # Track peak and max drawdown
            if capital > peak_capital:
                peak_capital = capital
            dd = (peak_capital - capital) / peak_capital if peak_capital > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

        # Compute summary metrics
        total_trades = len(trades)
        wins = sum(1 for t in trades if t.is_win)
        losses = total_trades - wins
        win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_gains = sum(t.pnl for t in trades if t.pnl > 0)
        gross_losses = abs(sum(t.pnl for t in trades if t.pnl < 0))
        profit_factor = (gross_gains / gross_losses) if gross_losses > 0 else (10.0 if gross_gains > 0 else 1.0)

        total_net_pnl = capital - self.starting_capital
        total_roi = (total_net_pnl / self.starting_capital) * 100.0
        total_fees = sum(t.fees for t in trades)

        # Sharpe & Sortino calculation
        if step_returns:
            returns_arr = np.array(step_returns, dtype=np.float64)
            mean_ret = float(np.mean(returns_arr))
            std_ret = float(np.std(returns_arr)) + 1e-9
            sharpe = (mean_ret / std_ret) * math.sqrt(252 * 6.5 * 4)  # Annualized 15m steps

            # Exact Downside Semi-Deviation: sqrt(E[min(0, r)^2])
            downside_sq = np.minimum(0.0, returns_arr) ** 2
            downside_dev = float(np.sqrt(np.mean(downside_sq))) + 1e-9
            sortino = (mean_ret / downside_dev) * math.sqrt(252 * 6.5 * 4)
        else:
            sharpe = 0.0
            sortino = 0.0

        return BacktestResult(
            model_name=model_name,
            initial_capital=self.starting_capital,
            final_capital=capital,
            total_net_pnl=total_net_pnl,
            total_roi_pct=total_roi,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            max_drawdown_pct=max_drawdown * 100.0,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            total_fees_paid=total_fees,
            equity_curve=equity_curve,
            trades=trades,
        )


class ModelComparator:
    """Executes identical backtests across multiple model candidates and compares results."""

    def __init__(self, frames: List[TickFrame], starting_capital: float = 10000.0) -> None:
        self.frames = frames
        self.starting_capital = starting_capital

    def compare(
        self, candidate_models: List[Tuple[str, Optional[Union[str, Path]]]]
    ) -> List[BacktestResult]:
        """Run backtests for all candidate models and return ordered performance list."""
        results: List[BacktestResult] = []

        for name, path in candidate_models:
            logger.info("Running backtest replay for model: %s", name)
            engine = BacktestEngine(
                onnx_model_path=path,
                starting_capital=self.starting_capital,
            )
            res = engine.run(self.frames, model_name=name)
            results.append(res)

        # Sort by total net PnL descending
        results.sort(key=lambda r: r.total_net_pnl, reverse=True)
        return results
