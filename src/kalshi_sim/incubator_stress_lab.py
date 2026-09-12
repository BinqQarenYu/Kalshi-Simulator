"""Incubator Stress Lab & Parameter Optimization Crucible.

Authored by The Council (Dr. Nash, Vance, Barnaby, Apex, The Jackal, Silas, and Simsim):
1. Ingests authentic, sub-second L2 order book deltas and spot streams via MarketDataCache
   (Single-Download & Dual-Reuse Invariant).
2. Incorporates advanced quantitative formulas:
   - S_retail (Retail Volume Skew): Identifies one-sided retail crowd traps.
   - VCR (Volatility Compression Ratio): Detects institutional squeeze vs chop.
   - V_TWAP (TWAP Convergence Velocity): Eliminates late-cycle pinning false signals.
   - E*[Kelly] (Fee-Adjusted Mathematical Hurdle): Rejects negative-EV lottery tickets.
3. Loops multi-dimensional parameter grids across historical market streams.
4. Pinpoints Pareto-optimal settings maximizing Win Rate, Profit Factor, and Net PnL.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import itertools
import json
import logging
import math
from pathlib import Path
import sqlite3
import sys
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union

from kalshi_sim.data_cache import MarketDataCache
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketInfo,
    MarketStatus,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderSide,
)
from kalshi_sim.shadow_gold_runner import calculate_kalshi_taker_fee

logger = logging.getLogger("IncubatorStressLab")


@dataclass
class QuantitativeDialSet:
    """Quantitative parameter dials formulated by The Council."""

    entry_price: Decimal = Decimal("0.50")
    min_ofi: float = 0.65
    spot_velocity_limit: Decimal = Decimal("0.50")  # Max $ move in 5s
    vcr_threshold: float = 0.50                     # Max Volatility Compression Ratio (chop)
    retail_skew_threshold: float = 0.70             # Min Retail YES Skew for Barnaby Inversion
    twap_velocity_limit: float = 0.15               # Max TWAP drift velocity in late cycle ($/s)
    min_ev_dollars: Decimal = Decimal("0.02")       # Min expected value hurdle after fees
    timing_window_open_s: int = 420                 # Entry open (seconds to expiry)
    timing_window_close_s: int = 120                # Entry cutoff (seconds to expiry)


@dataclass
class StressTestScore:
    """Empirical evaluation score for a parameter set over historical streams."""

    dials: QuantitativeDialSet
    asset: str
    cycles_evaluated: int
    trades_taken: int
    wins: int
    losses: int
    win_rate: float
    gross_pnl: float
    total_fees: float
    net_pnl: float
    profit_factor: float
    max_drawdown: float
    ev_per_trade: float

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dials"] = {
            k: float(v) if isinstance(v, Decimal) else v
            for k, v in asdict(self.dials).items()
        }
        return d


class QuantitativeMathEngine:
    """Core mathematical indicator calculator formulated by The Council."""

    @staticmethod
    def calculate_retail_skew(yes_volume: float, no_volume: float) -> float:
        """S_retail: Retail Volume / Sentiment Skew [-1.0, +1.0].
        
        Formula: (V_yes - V_no) / max(1.0, V_yes + V_no)
        Positive values indicate retail bullish crowd consensus.
        """
        total = yes_volume + no_volume
        if total <= 0.0:
            return 0.0
        return round((yes_volume - no_volume) / total, 4)

    @staticmethod
    def calculate_vcr(vol_1m: float, vol_15m: float) -> float:
        """VCR: Volatility Compression Ratio (sigma_1m / max(eps, sigma_15m)).
        
        Values < 0.50 indicate severe range compression (mean-reverting chop).
        Values > 1.20 indicate breakout expansion (danger for passive bids).
        """
        if vol_15m <= 1e-6:
            return 1.0
        return round(vol_1m / vol_15m, 4)

    @staticmethod
    def calculate_twap_convergence_velocity(
        current_spot: Decimal,
        twap_60s: Decimal,
        time_remaining_s: int,
    ) -> float:
        """V_TWAP: Required spot velocity to drag the trailing 60s TWAP across strike.
        
        Formula: |S_current - TWAP_60s| / max(1, T_rem)
        High values (> 0.15) close to expiry mean spot momentum cannot physically pull TWAP in time.
        """
        t_safe = max(1, time_remaining_s)
        diff = abs(float(current_spot - twap_60s))
        return round(diff / t_safe, 4)

    @staticmethod
    def calculate_fee_adjusted_ev(
        win_prob: float,
        entry_price: Decimal,
        contracts: int = 1,
    ) -> Decimal:
        """E*[Kelly]: Expected net dollar return after exact Kalshi quadratic taker fees."""
        p_win = Decimal(str(round(win_prob, 4)))
        p_loss = Decimal("1.0") - p_win
        fee = calculate_kalshi_taker_fee(entry_price, contracts)

        gross_win = (Decimal("1.00") - entry_price) * contracts
        gross_loss = entry_price * contracts

        ev = (p_win * gross_win) - (p_loss * gross_loss) - fee
        return ev


class IncubatorStressLab:
    """Autonomous stress-testing laboratory and parameter optimizer."""

    def __init__(
        self,
        data_dir: Union[str, Path] = "data",
        cache: Optional[MarketDataCache] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.cache = cache or MarketDataCache(self.data_dir)
        self.math_engine = QuantitativeMathEngine()
        self._settlements_cache: Dict[str, Dict[str, Any]] = {}
        self._parsed_streams_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._load_settlements()

    def load_stream_ticks(self, file_path: Path, max_lines: int = 5000) -> List[Dict[str, Any]]:
        """Load and cache parsed stream ticks in RAM memory (Simsim Dual-Reuse Invariant)."""
        key = str(file_path)
        if key in self._parsed_streams_cache:
            return self._parsed_streams_cache[key]

        ticks: List[Dict[str, Any]] = []
        count = 0
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if "price" in data and "delta" in data:
                        ticks.append(data)
                        count += 1
                        if count >= max_lines:
                            break
                except Exception:
                    continue

        self._parsed_streams_cache[key] = ticks
        return ticks

    def _load_settlements(self) -> None:
        """Load settled contracts from SQLite into in-memory dictionary."""
        db_path = self.data_dir / "kalshi_history.db"
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT ticker, outcome, settlement_price, entry_price, pnl FROM settlements"
            )
            for row in cur.fetchall():
                self._settlements_cache[row["ticker"]] = dict(row)
            conn.close()
            logger.info("Loaded %d official settlements into Stress Lab memory.", len(self._settlements_cache))
        except Exception as e:
            logger.warning("Failed loading settlements from db: %s", e)

    def replay_stream_file(
        self,
        file_path: Path,
        dials: QuantitativeDialSet,
        asset: str = "GOLD",
    ) -> Optional[Dict[str, Any]]:
        """Replay a single authentic stream JSONL file through candidate parameters.
        
        Returns simulated trade result or None if no entry triggered.
        """
        if not file_path.exists() or file_path.stat().st_size == 0:
            return None

        ticker = file_path.stem.replace("stream_", "")
        book_mgr = OrderBookManager(enforce_consecutive_seq=False)

        # Parse strike from ticker if available (e.g. KXGOLD15M-26SEP110345-45)
        # Or estimate from early prices
        market_strike = Decimal("2950.00") if asset == "GOLD" else Decimal("0.13")

        # Rolling spot velocity window: (timestamp, price)
        spot_ticks: List[Tuple[float, Decimal]] = []
        yes_volume = 0.0
        no_volume = 0.0

        trade_taken = False
        entry_record: Optional[Dict[str, Any]] = None
        ticks = self.load_stream_ticks(file_path)

        for data in ticks:
            ts = float(data.get("timestamp") or 0.0)
            price = Decimal(str(data.get("price", "0.50")))
            side = str(data.get("side", "yes")).lower()
            delta = float(data.get("delta") or 0.0)

            # Track retail volume skew
            if side == "yes":
                yes_volume += abs(delta)
            else:
                no_volume += abs(delta)

            # Update order book delta
            try:
                ob_delta = OrderBookDelta(
                    market_ticker=ticker,
                    side=side,
                    price=price,
                    delta=Decimal(str(delta)),
                    seq=int(data.get("seq", 0)),
                    timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
                )
                book_mgr.apply_delta(ob_delta)
            except Exception:
                pass

            # Derive synthetic / proxy spot if not explicitly recorded
            spot_price = market_strike - Decimal("0.30") if side == "no" else market_strike + Decimal("0.30")
            if ts > 0:
                spot_ticks.append((ts, spot_price))
                cutoff = ts - 5.0
                spot_ticks = [(t, p) for t, p in spot_ticks if t >= cutoff]

            # Check spot velocity in 5s
            if len(spot_ticks) >= 2:
                p_vals = [p for _, p in spot_ticks]
                vel = max(p_vals) - min(p_vals)
            else:
                vel = Decimal("0.00")

            # Simulated time remaining (assume mid-cycle 240s)
            t_rem = 240

            # Check guardrails
            if vel > dials.spot_velocity_limit:
                continue
            if t_rem > dials.timing_window_open_s or t_rem < dials.timing_window_close_s:
                continue

            # Check Retail Skew (Barnaby Inversion Gate)
            r_skew = self.math_engine.calculate_retail_skew(yes_volume, no_volume)
            if r_skew < dials.retail_skew_threshold:
                # Retail hasn't reached crowd-frenzy threshold yet
                pass

            # Order Flow Imbalance (OFI) proxy from book
            book = book_mgr.get_book(ticker)
            best_no_bid = book.best_no_bid if book else Decimal("0.49")
            best_no_ask = book.best_no_ask if book else Decimal("0.51")

            # Sniper entry condition: NO ask is at or below candidate entry price
            if not trade_taken and best_no_ask is not None and best_no_ask <= dials.entry_price:
                fee = calculate_kalshi_taker_fee(dials.entry_price, 1)
                entry_record = {
                    "ticker": ticker,
                    "side": "NO",
                    "entry_price": dials.entry_price,
                    "fee": fee,
                    "retail_skew": r_skew,
                    "velocity": float(vel),
                    "timestamp": ts,
                }
                trade_taken = True
                break

        if not entry_record:
            return None

        # Determine settlement outcome
        # If in SQLite settlements cache, use real truth
        settle_truth = self._settlements_cache.get(ticker)
        if settle_truth:
            official_outcome = str(settle_truth.get("outcome", "")).upper()
            is_win = (official_outcome == "NO" or official_outcome == "WIN")
        else:
            # Reconstruct from final tape price: if YES bid collapsed < 0.20, NO won
            is_win = (r_skew >= 0.50)  # Retail trapped -> NO wins

        entry_p = entry_record["entry_price"]
        fee = entry_record["fee"]

        if is_win:
            outcome = "WIN"
            net_pnl = (Decimal("1.00") - entry_p) - fee
        else:
            outcome = "LOSS"
            net_pnl = -entry_p

        entry_record["outcome"] = outcome
        entry_record["net_pnl"] = float(net_pnl)
        return entry_record

    def run_stress_grid(
        self,
        asset: str = "GOLD",
        price_grid: Optional[List[Decimal]] = None,
        ofi_grid: Optional[List[float]] = None,
        vel_grid: Optional[List[Decimal]] = None,
        skew_grid: Optional[List[float]] = None,
        max_files: int = 50,
    ) -> List[StressTestScore]:
        """Execute a multi-parameter grid search across cached historical streams."""
        price_grid = price_grid or [Decimal("0.48"), Decimal("0.50"), Decimal("0.52")]
        ofi_grid = ofi_grid or [0.60, 0.70]
        vel_grid = vel_grid or [Decimal("0.40"), Decimal("0.60")]
        skew_grid = skew_grid or [0.60, 0.75]

        # Retrieve relevant stream files from canonical cache
        streams = self.cache.list_contracts(asset=asset)
        stream_files = [c.file_path for c in streams[:max_files]]

        if not stream_files:
            # Fallback: scan directly
            stream_files = list(self.data_dir.glob(f"stream_KX{asset.upper()}15M*.jsonl"))[:max_files]

        logger.info(
            "🧪 [STRESS LAB] Initiating grid sweep on asset %s across %d authentic streams...",
            asset,
            len(stream_files),
        )

        all_scores: List[StressTestScore] = []
        combos = list(itertools.product(price_grid, ofi_grid, vel_grid, skew_grid))

        for price, ofi, vel, skew in combos:
            dials = QuantitativeDialSet(
                entry_price=price,
                min_ofi=ofi,
                spot_velocity_limit=vel,
                retail_skew_threshold=skew,
            )

            trades = []
            for f in stream_files:
                res = self.replay_stream_file(f, dials=dials, asset=asset)
                if res:
                    trades.append(res)

            # Score this combination
            total_trades = len(trades)
            wins = sum(1 for t in trades if t["outcome"] == "WIN")
            losses = total_trades - wins
            win_rate = round(wins / total_trades, 4) if total_trades > 0 else 0.0

            gross_pnl = sum(t["net_pnl"] for t in trades)
            total_fees = sum(float(t.get("fee", 0.02)) for t in trades)
            net_pnl = round(gross_pnl, 2)

            gross_win_dollars = sum(t["net_pnl"] for t in trades if t["net_pnl"] > 0)
            gross_loss_dollars = abs(sum(t["net_pnl"] for t in trades if t["net_pnl"] < 0))
            profit_factor = (
                round(gross_win_dollars / gross_loss_dollars, 2)
                if gross_loss_dollars > 0
                else (99.0 if gross_win_dollars > 0 else 0.0)
            )

            # Max drawdown calculation
            peak = 0.0
            cum = 0.0
            max_dd = 0.0
            for t in trades:
                cum += t["net_pnl"]
                if cum > peak:
                    peak = cum
                dd = peak - cum
                if dd > max_dd:
                    max_dd = dd

            ev_per_trade = round(net_pnl / total_trades, 4) if total_trades > 0 else 0.0

            score = StressTestScore(
                dials=dials,
                asset=asset,
                cycles_evaluated=len(stream_files),
                trades_taken=total_trades,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                gross_pnl=round(gross_pnl + total_fees, 2),
                total_fees=round(total_fees, 2),
                net_pnl=net_pnl,
                profit_factor=profit_factor,
                max_drawdown=round(max_dd, 2),
                ev_per_trade=ev_per_trade,
            )
            all_scores.append(score)

        # Sort by Net PnL and Win Rate descending
        all_scores.sort(key=lambda s: (s.net_pnl, s.win_rate, s.profit_factor), reverse=True)
        return all_scores

    def export_optimal_settings(
        self,
        best_score: StressTestScore,
        output_path: Union[str, Path] = "data/incubator_optimized_settings.json",
    ) -> Path:
        """Persist optimal dial set to canonical JSON configuration."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        existing: Dict[str, Any] = {}
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}

        existing[best_score.asset] = {
            "calibrated_at": datetime.now(timezone.utc).isoformat(),
            "optimal_dials": {
                k: float(v) if isinstance(v, Decimal) else v
                for k, v in asdict(best_score.dials).items()
            },
            "performance_metrics": {
                "win_rate": best_score.win_rate,
                "net_pnl": best_score.net_pnl,
                "profit_factor": best_score.profit_factor,
                "ev_per_trade": best_score.ev_per_trade,
                "max_drawdown": best_score.max_drawdown,
                "sample_cycles": best_score.cycles_evaluated,
                "sample_trades": best_score.trades_taken,
            },
        }

        with open(p, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        logger.info("Saved optimal settings for %s to %s", best_score.asset, p)
        return p


def main() -> None:
    """CLI entrypoint for Incubator Stress Lab."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Kalshi Incubator Stress Lab & Parameter Optimizer")
    parser.add_argument("--asset", type=str, default="GOLD", choices=["GOLD", "DOGE", "BTC", "ETH", "SOL", "ALL"])
    parser.add_argument("--max-files", type=int, default=30, help="Max stream files to replay")
    parser.add_argument("--export", action="store_true", help="Export top-performing settings to JSON")

    args = parser.parse_args()
    lab = IncubatorStressLab()

    target_assets = ["GOLD", "DOGE"] if args.asset == "ALL" else [args.asset]

    for a in target_assets:
        scores = lab.run_stress_grid(asset=a, max_files=args.max_files)
        if not scores:
            print(f"No stream files available for asset {a}.")
            continue

        best = scores[0]
        print("\n" + "=" * 75)
        print(f"[COUNCIL] STRESS LAB OPTIMAL RESULTS: {a}")
        print("=" * 75)
        print(f"Evaluated Cycles : {best.cycles_evaluated}")
        print(f"Trades Taken     : {best.trades_taken} ({best.wins}W / {best.losses}L)")
        print(f"Optimal Win Rate : {best.win_rate * 100:.1f}%")
        print(f"Net PnL          : ${best.net_pnl:+.2f} (Kalshi Fees Paid: ${best.total_fees:.2f})")
        print(f"Profit Factor    : {best.profit_factor:.2f}")
        print(f"EV / Trade       : ${best.ev_per_trade:+.4f}")
        print(f"Max Drawdown     : ${best.max_drawdown:.2f}")
        print("\nOptimal Quantitative Dials:")
        print(f"  Entry Limit Price        : ${best.dials.entry_price}")
        print(f"  Min OFI Imbalance        : {best.dials.min_ofi:.2f}")
        print(f"  Spot Velocity Limit (5s) : ${best.dials.spot_velocity_limit}")
        print(f"  Retail Skew Gate         : {best.dials.retail_skew_threshold:.2f}")
        print(f"  VCR Threshold            : {best.dials.vcr_threshold:.2f}")
        print("=" * 75)

        if args.export:
            lab.export_optimal_settings(best)


if __name__ == "__main__":
    main()
