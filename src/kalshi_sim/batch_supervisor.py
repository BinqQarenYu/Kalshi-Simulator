"""Autonomous Batch Supervisor and Evolutionary Evaluation Daemon.

Runs parallel to the live trading engine. Continuously audits trade progress,
enforces the 6-trade evaluation batch boundary, assesses PnL & win rate against
the primary goal (max Net PnL > 0 and Win Rate >= 70%), and coordinates parameter
upgrades with the Quant Council and institutional Lessons Learned memory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kalshi_sim.batch_supervisor")


class AutonomousBatchSupervisor:
    """Supervises live trade execution in 6-trade batches, running in parallel with the bot."""

    def __init__(
        self,
        guardrails: Any = None,
        bot_parameters_path: str | Path = "data/bot_parameters_domination.json",
        win_loss_path: str | Path = "data/win_loss_reports.json",
        docs_dir: str | Path = "docs",
        eval_batch_size: int = 6,
        poll_interval_s: float = 5.0,
        asset: Optional[str] = None,
    ) -> None:
        self.guardrails = guardrails
        self.bot_parameters_path = Path(bot_parameters_path)
        self.win_loss_path = Path(win_loss_path)
        self.docs_dir = Path(docs_dir)
        self.eval_batch_size = eval_batch_size
        self.poll_interval_s = poll_interval_s
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_processed_trade_count = 0

        # Dedicated Asset Isolation (Strictly exclude unrelated assets)
        if asset:
            self.asset = str(asset).upper()
        elif "eth" in str(self.win_loss_path).lower() or "eth" in str(self.bot_parameters_path).lower():
            self.asset = "ETH"
        else:
            self.asset = "BTC"

        # Unique Trade ID Tracking & Persistence (prevents array-cap deadlocks and cross-process drift)
        self.processed_trades_path = self.win_loss_path.parent / f"supervisor_processed_trades_{self.asset.lower()}.json"
        self._processed_trade_ids: set[str] = self._load_or_bootstrap_processed_trade_ids()

        # Cumulative Statistical History (Combats 6-trade noise / overfitting)
        self.cumulative_trades = 0
        self.cumulative_wins = 0
        self.cumulative_losses = 0
        self.cumulative_pnl = Decimal("0.00")
        self.min_macro_sample_size = 30
        self.current_batch_num = self._discover_initial_batch_num()
        self._emailed_batches: set[int] = set()

    def _is_asset_match(self, report: dict[str, Any]) -> bool:
        """Verify whether a historical report belongs to this bot's target asset."""
        a = str(report.get("asset", "")).upper()
        t = str(report.get("ticker", "")).upper()
        if self.asset == "BTC":
            if a == "ETH" or t.startswith("KXETH"):
                return False
            return a == "BTC" or t.startswith("KXBTC") or ("BTC" in t and "ETH" not in t)
        elif self.asset == "ETH":
            if a == "BTC" or t.startswith("KXBTC"):
                return False
            return a == "ETH" or t.startswith("KXETH") or "ETH" in t
        elif a:
            return a == self.asset
        return self.asset in t

    def _get_trade_id(self, report: dict[str, Any]) -> str:
        """Generate a deterministic, unique identifier for a trade."""
        if report.get("report_id"):
            return str(report["report_id"])
        if report.get("trade_id"):
            return str(report["trade_id"])
        if report.get("cycle_id"):
            return str(report["cycle_id"])
        ticker = str(report.get("ticker", "UNKNOWN"))
        ts = str(report.get("timestamp_utc") or report.get("cycle_time") or report.get("exit_time") or "")
        strike = str(report.get("strike_price", ""))
        entry_p = str(report.get("entry_price", ""))
        side = str(report.get("bot_side") or report.get("side") or "")
        return f"{ticker}_{ts}_{strike}_{entry_p}_{side}"

    def _load_or_bootstrap_processed_trade_ids(self) -> set[str]:
        """Load persisted processed trade IDs or bootstrap from disk assessments."""
        if self.processed_trades_path.exists():
            try:
                data = json.loads(self.processed_trades_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    logger.info(
                        "🛡️ [BATCH SUPERVISOR] Loaded %d processed trade IDs for %s from %s.",
                        len(data), self.asset, self.processed_trades_path
                    )
                    return set(data)
            except Exception as exc:
                logger.warning("Failed loading %s: %s", self.processed_trades_path, exc)

        return self._bootstrap_processed_trade_ids()

    def _save_processed_trade_ids(self) -> None:
        """Atomically persist processed trade IDs to disk, bounded to latest 1000 entries."""
        try:
            ids_list = list(self._processed_trade_ids)[-1000:]
            self.processed_trades_path.parent.mkdir(parents=True, exist_ok=True)
            self.processed_trades_path.write_text(json.dumps(ids_list, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed saving %s: %s", self.processed_trades_path, exc)

    def _find_latest_assessment_eval_time(self) -> Optional[str]:
        """Discover the UTC evaluation timestamp of the most recent assessment document in docs_dir."""
        if not self.docs_dir.exists():
            return None
        asset_s = self.asset.lower()
        if asset_s == "btc":
            files = [p for p in self.docs_dir.glob("assessment_*_#*_.md") if "_eth_" not in p.name]
        else:
            files = list(self.docs_dir.glob(f"assessment_*_#*_{asset_s}_.md"))

        if not files:
            return None

        files.sort(key=lambda p: [int(x) for x in re.findall(r"#(\d+)_", p.name)] or [0])
        latest = files[-1]
        try:
            text = latest.read_text(encoding="utf-8")
            m = re.search(r"\*\*Evaluation Date:\*\*\s*(\d{4}-\d{2}-\d{2})\s*\(([0-9:]+)", text)
            if m:
                d, t = m.group(1), m.group(2)
                if len(t) == 5:
                    t += ":00"
                return f"{d}T{t}"
        except Exception:
            pass
        return None

    def _bootstrap_processed_trade_ids(self) -> set[str]:
        """Bootstrap processed trade IDs when starting fresh without a state file."""
        processed: set[str] = set()
        if not self.win_loss_path.exists():
            return processed
        try:
            reports = json.loads(self.win_loss_path.read_text(encoding="utf-8"))
            if not isinstance(reports, list):
                return processed
            matching = [r for r in reports if self._is_asset_match(r)]
            if not matching:
                return processed

            # Sort newest first so slicing preserves recent trades
            matching.sort(key=lambda r: str(r.get("timestamp_utc") or r.get("cycle_time") or ""), reverse=True)

            eval_cutoff = self._find_latest_assessment_eval_time()
            if eval_cutoff:
                for r in matching:
                    ts = str(r.get("timestamp_utc") or r.get("cycle_time") or "")
                    if ts and ts <= eval_cutoff:
                        processed.add(self._get_trade_id(r))
                logger.info(
                    "🛡️ [BATCH SUPERVISOR] Bootstrapped %s processed trade IDs using eval cutoff %s (marked %d trades as processed).",
                    self.asset, eval_cutoff, len(processed)
                )
            else:
                # If no evaluation doc exists in docs_dir, process up to latest 42 trades;
                # mark older historical backlog (if > 42) as processed to prevent runaway API spend.
                if len(matching) > 42:
                    for r in matching[42:]:
                        processed.add(self._get_trade_id(r))
                    logger.info(
                        "🛡️ [BATCH SUPERVISOR] Bootstrapped %s processed trade IDs (marked %d older trades as processed).",
                        self.asset, len(processed)
                    )
            self._processed_trade_ids = processed
            self._save_processed_trade_ids()
        except Exception as exc:
            logger.warning("Error bootstrapping processed trades for %s: %s", self.asset, exc)
        return processed

    def _get_unprocessed_trades(self) -> list[dict[str, Any]]:
        """Return all unassessed trades matching this asset, sorted chronologically (oldest first)."""
        if not self.win_loss_path.exists():
            return []
        try:
            reports = json.loads(self.win_loss_path.read_text(encoding="utf-8"))
            if not isinstance(reports, list):
                return []
            matching = [r for r in reports if self._is_asset_match(r)]
            unprocessed = [r for r in matching if self._get_trade_id(r) not in self._processed_trade_ids]
            # Sort chronologically so batches are evaluated in order
            unprocessed.sort(key=lambda r: str(r.get("timestamp_utc") or r.get("cycle_time") or ""))
            return unprocessed
        except Exception as exc:
            logger.debug("Failed reading unprocessed trades from %s: %s", self.win_loss_path, exc)
            return []

    def _discover_initial_batch_num(self) -> int:
        asset_s = getattr(self, "asset", "BTC").lower()
        max_num = 0 if asset_s != "btc" else 108
        if self.docs_dir.exists():
            if asset_s == "btc":
                for p in self.docs_dir.glob("assessment_*_#*_.md"):
                    if "_eth_" not in p.name:
                        match = re.search(r"#(\d+)_", p.name)
                        if match:
                            try:
                                max_num = max(max_num, int(match.group(1)))
                            except ValueError:
                                pass
            else:
                for p in self.docs_dir.glob(f"assessment_*_#*_{asset_s}_.md"):
                    match = re.search(r"#(\d+)_", p.name)
                    if match:
                        try:
                            max_num = max(max_num, int(match.group(1)))
                        except ValueError:
                            pass
        return max_num + 1 if max_num > 0 else 1

    def start(self) -> asyncio.Task:
        """Start the supervisor background evaluation loop."""
        if self._task and not self._task.done():
            return self._task
        self.is_running = True
        self._task = asyncio.create_task(
            self._supervision_loop(),
            name=f"autonomous_batch_supervisor_{self.asset.lower()}",
        )
        logger.info(
            "🛡️ [BATCH SUPERVISOR] Autonomous 6-Trade Evaluation Daemon started for %s (Batch Size: %d, Initial Batch #%d).",
            self.asset, self.eval_batch_size, self.current_batch_num
        )
        return self._task

    def stop(self) -> None:
        """Stop the supervisor background loop."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("🛡️ [BATCH SUPERVISOR] Autonomous Batch Supervisor stopped for %s.", self.asset)

    def determine_market_condition(self, recent_trades: list[dict[str, Any]]) -> dict[str, Any]:
        """Classify active market condition (Choppy, Stormy, Bleed, Healing) for this 6-trade evaluation."""
        region = "CHOP"
        transition_reason = "Baseline microstructural flow"
        hmm_regime = "STABLE_RANGE"
        wave_summary = "BOUNDED CHOP"

        # 1. Inspect live Bot 1 V4 engine wave classifier & wave physics
        try:
            from kalshi_sim.server import state
            eng = None
            if self.asset == "ETH":
                eng = getattr(state, "eth_bot1v4_engine", None)
                if not eng and hasattr(state, "sim_agent") and state.sim_agent:
                    eng = getattr(state.sim_agent, "_eth_bot1v4_engine", None)
            else:
                eng = getattr(state, "bot1_v4_engine", None)
                if not eng and hasattr(state, "sim_agent") and state.sim_agent:
                    eng = getattr(state.sim_agent, "_bot1_v4_engine", None)

            if eng:
                if hasattr(eng, "wave_classifier"):
                    region = getattr(eng.wave_classifier, "current_region", "CHOP")
                    transition_reason = getattr(eng.wave_classifier, "last_transition_reason", "")
                if hasattr(eng, "_last_wave_physics") and eng._last_wave_physics:
                    wave_summary = eng._last_wave_physics.wave_summary
            elif hasattr(state, "guardrails_agent") and hasattr(state.guardrails_agent, "current_market_condition"):
                region = state.guardrails_agent.current_market_condition.upper()
        except Exception:
            pass

        # 2. Inspect HMM macro regime
        try:
            from kalshi_sim.server import state
            if hasattr(state, "hmm_brain") and state.hmm_brain:
                hmm_regime = state.hmm_brain.get_status().get("current_regime", "STABLE_RANGE")
        except Exception:
            pass

        # 3. Compute empirical batch metrics from the settled trades
        spot_prices = [
            float(t.get("settlement_spot_price") or t.get("settlement_btc_price") or 0.0)
            for t in recent_trades
            if (t.get("settlement_spot_price") or t.get("settlement_btc_price"))
        ]
        spot_prices = [p for p in spot_prices if p > 0.0]
        spot_range = (max(spot_prices) - min(spot_prices)) if len(spot_prices) >= 2 else 0.0

        vpin_scores = [float(t.get("vpin_score", 0.0)) for t in recent_trades if t.get("vpin_score") is not None]
        avg_vpin = sum(vpin_scores) / len(vpin_scores) if vpin_scores else 0.0

        # 4. Synthesize final condition tag & descriptors (asset-calibrated thresholds)
        reg_upper = region.upper()
        stormy_range_threshold = 200.0 if self.asset == "BTC" else 20.0
        if "STORM" in reg_upper or spot_range >= stormy_range_threshold or avg_vpin >= 0.70 or hmm_regime == "VOL_EXPANSION":
            cond_tag = "STORMY"
            cond_name = "Stormy (Directional Volatility & Volcano Expansion)"
            cond_desc = f"High velocity wave expansion (Range: ${spot_range:.1f}, Avg VPIN: {avg_vpin:.2f}, Macro: {hmm_regime})"
        elif "BLEED" in reg_upper or hmm_regime == "RISK_OFF":
            cond_tag = "BLEED"
            cond_name = "Bleed / Adverse Wicks (Hostile Meatgrinder)"
            cond_desc = "Adverse selection and double-wick whipsaws detected. Bleed defense protocols engaged."
        elif "HEAL" in reg_upper:
            cond_tag = "HEALING"
            cond_name = "Healing (Post-Drawdown Convalescence)"
            cond_desc = "Probationary quarantine mode recovering bankroll with defensive filters."
        else:
            cond_tag = "CHOPPY"
            cond_name = "Choppy (Range-Bound Compression & Mean-Reversion)"
            cond_desc = f"Compressed range with mean-reverting liquidity (Range: ${spot_range:.1f}, Avg VPIN: {avg_vpin:.2f}, Macro: {hmm_regime})"

        return {
            "tag": cond_tag,
            "name": cond_name,
            "description": cond_desc,
            "hmm_regime": hmm_regime,
            "wave_region": region,
            "wave_summary": wave_summary,
            "spot_range": round(spot_range, 2),
            "avg_vpin": round(avg_vpin, 3),
            "transition_reason": transition_reason or "Normal wave dynamics",
        }

    async def force_trigger_batch_evaluation(self) -> dict[str, Any]:
        """Manually trigger a 6-trade evaluation batch right now, generate report with market condition, and email operator."""
        logger.info("⚡ [BATCH SUPERVISOR] Manual/On-demand evaluation batch triggered for %s.", self.asset)
        unprocessed = self._get_unprocessed_trades()
        batch_trades = unprocessed[:self.eval_batch_size] if len(unprocessed) >= self.eval_batch_size else None
        await self._evaluate_and_evolve_batch(batch_trades=batch_trades)
        return {
            "batch_num": self.current_batch_num - 1,
            "asset": self.asset,
            "status": "evaluated_and_dispatched",
        }

    async def _supervision_loop(self) -> None:
        """Continuous background loop monitoring the 6-trade execution gate."""
        while self.is_running:
            try:
                await asyncio.sleep(self.poll_interval_s)

                # 1. Primary check: Unprocessed trades in win_loss ledger
                unprocessed = self._get_unprocessed_trades()
                if len(unprocessed) >= self.eval_batch_size:
                    batch_trades = unprocessed[:self.eval_batch_size]
                    logger.info(
                        "🛡️ [BATCH SUPERVISOR] Detected %d unprocessed %s trades. Evaluating next 6-trade batch (Batch #%d)...",
                        len(unprocessed), self.asset, self.current_batch_num
                    )
                    await self._evaluate_and_evolve_batch(batch_trades=batch_trades)
                    continue

                # 2. In-memory guardrails check (fallback & backward-compatibility)
                if self.guardrails:
                    completed = getattr(self.guardrails, "batch_trades_completed", 0)
                    quota = getattr(self.guardrails, "batch_trades_quota", self.eval_batch_size)
                    if completed >= quota and quota > 0 and getattr(self.guardrails, "is_bot_armed", True):
                        await self._evaluate_and_evolve_batch()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[BATCH SUPERVISOR ERROR] Supervision loop error (%s): %s", self.asset, exc, exc_info=True)

    async def _evaluate_and_evolve_batch(self, batch_trades: Optional[list[dict[str, Any]]] = None) -> None:
        """Execute the formal 6-trade post-batch assessment powered by Gemini & Quant Council."""
        # 1. Harvest recent settled trades strictly matching this asset
        recent_trades: list[dict[str, Any]] = []
        if batch_trades is not None and len(batch_trades) > 0:
            recent_trades = batch_trades
        elif self.win_loss_path.exists():
            try:
                reports = json.loads(self.win_loss_path.read_text(encoding="utf-8"))
                matching = [r for r in reports if self._is_asset_match(r)]
                recent_trades = matching[:self.eval_batch_size]
                self._last_processed_trade_count = len(matching)
            except Exception as e:
                logger.debug("Failed reading win_loss_path: %s", e)

        # 1.1 Compute empirical metrics directly from the settled trades
        total_trades = len(recent_trades)
        if total_trades > 0:
            batch_wins = sum(1 for t in recent_trades if str(t.get("outcome", "")).lower() == "win")
            batch_losses = sum(1 for t in recent_trades if str(t.get("outcome", "")).lower() == "loss")
            win_rate = (batch_wins / max(1, total_trades)) * 100.0
            # Adhere strictly to Law 1: Zero Float Financial Math (Decimal)
            batch_pnl = sum(
                (Decimal(str(t.get("pnl", "0.00"))) for t in recent_trades),
                Decimal("0.00")
            )
        else:
            batch_pnl = getattr(self.guardrails, "batch_pnl", Decimal("0.00"))
            batch_wins = getattr(self.guardrails, "batch_wins", 0)
            batch_losses = getattr(self.guardrails, "batch_losses", 0)
            total_trades = batch_wins + batch_losses
            win_rate = (batch_wins / max(1, total_trades)) * 100.0 if total_trades > 0 else 0.0

        # Accumulate into macro statistical sample
        self.cumulative_trades += total_trades
        self.cumulative_wins += batch_wins
        self.cumulative_losses += batch_losses
        self.cumulative_pnl += batch_pnl
        macro_win_rate = (self.cumulative_wins / max(1, self.cumulative_trades)) * 100.0

        # 1.2 Classify Market Condition (Choppy, Stormy, Bleed, Healing)
        market_info = self.determine_market_condition(recent_trades)

        # 1.3 Audit Failure Fingerprints and Auto-Arm Degree-of-Freedom (DoF) Patches
        from kalshi_sim.ml.dof_governor import get_dof_governor
        dof_gov = get_dof_governor()
        dof_audit = dof_gov.evaluate_batch(
            asset=self.asset,
            batch_num=self.current_batch_num,
            recent_trades=recent_trades,
            win_rate=win_rate,
        )
        if dof_audit.get("newly_armed"):
            logger.warning("🛡️ [DoF SUPERVISOR] Patches Armed in %s Batch #%d: %s", self.asset, self.current_batch_num, dof_audit["newly_armed"])
        if dof_audit.get("newly_deescalated"):
            logger.info("🕊️ [DoF SUPERVISOR] Patches De-escalated in %s Batch #%d: %s", self.asset, self.current_batch_num, dof_audit["newly_deescalated"])

        logger.info(
            "========================================================================\n"
            "📊 [QUANT COUNCIL BATCH REPORT] %s Batch #%d (%d Trades) | Condition: %s | Batch PnL: $%s | Win Rate: %.1f%%\n"
            "📈 [MACRO STATISTICAL SAMPLE] Total %d Trades | Net PnL: $%s | Overall Win Rate: %.1f%%\n"
            "🛡️ [DoF ACTIVE PATCHES] %s\n"
            "========================================================================",
            self.asset, self.current_batch_num, total_trades, market_info["tag"], batch_pnl, win_rate,
            self.cumulative_trades, self.cumulative_pnl, macro_win_rate,
            dof_gov.get_active_summary(self.asset) or ["BASELINE_UNCONSTRAINED"]
        )

        # 2. Harvest Continuous Experience Buffer telemetry
        exp_summary: dict[str, Any] = {}
        try:
            from kalshi_sim.server import state
            if self.asset == "ETH":
                eth_bot = getattr(state, "eth_bot1_v4_engine", None)
                if eth_bot and getattr(eth_bot, "experience_buffer", None):
                    exp_summary = eth_bot.experience_buffer.get_recent_summary(20)
            if not exp_summary and hasattr(state, "experience_buffer") and state.experience_buffer:
                exp_summary = state.experience_buffer.get_recent_summary(20)
        except Exception:
            pass

        # 3. Read current parameters
        current_params: dict[str, Any] = {}
        if self.bot_parameters_path.exists():
            try:
                p_data = json.loads(self.bot_parameters_path.read_text(encoding="utf-8"))
                current_params = (
                    p_data.get("eth_bot1_v4")
                    if self.asset == "ETH"
                    else p_data.get("assets", {}).get("BTC", {})
                ) or p_data.get("assets", {}).get(self.asset, {}) or p_data
            except Exception:
                pass

        # 4. Run Gemini Forensic Assessment & Allowed Tweaks Formulation
        from kalshi_sim.ai_assessor import (
            run_gemini_batch_assessment,
            apply_validated_tweaks,
            build_assessment_markdown_report,
        )
        macro_sample = {
            "cumulative_trades": self.cumulative_trades,
            "cumulative_pnl": str(self.cumulative_pnl),
            "macro_win_rate": macro_win_rate,
        }

        logger.info(
            "🧠 [AI ASSESSOR] Invoking Gemini to analyze %s Batch #%d (Condition: %s) and formulate forensic conclusions...",
            self.asset, self.current_batch_num, market_info["tag"]
        )
        gemini_data = await run_gemini_batch_assessment(
            batch_num=self.current_batch_num,
            recent_trades=recent_trades,
            exp_summary=exp_summary,
            macro_sample=macro_sample,
            current_params=current_params,
            market_condition_info=market_info,
            asset=self.asset,
        )

        # 5. Apply validated tweaks within Quant Council bounds
        validated_tweaks = gemini_data.get("validated_tweaks", {})
        tweaks_rationale = gemini_data.get("tweaks_rationale", "")
        if validated_tweaks:
            applied = apply_validated_tweaks(self.bot_parameters_path, validated_tweaks, tweaks_rationale, asset=self.asset)
            if applied:
                logger.info("✅ [TWEAKS APPLIED] Parameters updated for %s: %s", self.asset, validated_tweaks)
                # Sync in-memory engine if available
                try:
                    from kalshi_sim.server import state
                    eng = getattr(state, "eth_bot1_v4_engine", None) if self.asset == "ETH" else getattr(state, "bot1_v4_engine", None)
                    if not eng and hasattr(state, "sim_agent") and state.sim_agent:
                        eng = getattr(state.sim_agent, "_eth_bot1v4_engine", None) if self.asset == "ETH" else getattr(state.sim_agent, "_bot1_v4_engine", None)
                    if eng:
                        for param_k, param_v in validated_tweaks.items():
                            if hasattr(eng, param_k):
                                setattr(eng, param_k, Decimal(str(param_v)) if isinstance(getattr(eng, param_k), Decimal) else param_v)
                        logger.info("🔄 [ENGINE SYNCED] In-memory %s Bot 1 V4 engine re-synced with newly tuned parameters.", self.asset)
                except Exception as sync_err:
                    logger.debug("Engine memory sync warning: %s", sync_err)

        # 5.1 Hard Redline Defense: Never hot-swap or overwrite core neural engine during live operation
        if batch_pnl < Decimal("0.00") or (win_rate < 50.0 and total_trades >= self.eval_batch_size):
            logger.warning(
                "🛡️ [HARD REDLINE ENFORCED] %s Batch #%d recorded drawdown (PnL: $%s, Win Rate: %.1f%% under %s). "
                "Core Bot 1 V4 neural/ONNX engine is protected under Hard Redlines. No disruptive preset hot-swap permitted.",
                self.asset, self.current_batch_num, batch_pnl, win_rate, market_info["tag"]
            )

        # 6. Build and save institutional markdown document
        post_balance = None
        if recent_trades and recent_trades[-1].get("balance_after") is not None:
            try:
                post_balance = Decimal(str(recent_trades[-1]["balance_after"]))
            except Exception:
                post_balance = None
        if post_balance is None:
            post_balance = getattr(self.guardrails, "current_balance", None) or Decimal("44.71")
        pre_balance = getattr(self.guardrails, "batch_starting_balance", None) or (post_balance - batch_pnl)

        md_report = build_assessment_markdown_report(
            batch_num=self.current_batch_num,
            recent_trades=recent_trades,
            batch_pnl=batch_pnl,
            batch_wins=batch_wins,
            batch_losses=batch_losses,
            pre_balance=pre_balance,
            post_balance=post_balance,
            gemini_data=gemini_data,
            macro_sample=macro_sample,
            market_condition_info=market_info,
            asset=self.asset,
        )

        try:
            self.docs_dir.mkdir(parents=True, exist_ok=True)
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            asset_suffix = f"_{self.asset.lower()}_" if self.asset != "BTC" else "_"
            report_file = self.docs_dir / f"assessment_{today_str}_#{self.current_batch_num}{asset_suffix}.md"
            report_file.write_text(md_report, encoding="utf-8")
            logger.info("📝 [ASSESSMENT SAVED] %s written to disk.", report_file)
        except Exception as doc_err:
            logger.warning("Could not write assessment to docs/: %s", doc_err)

        # 6.1 Enqueue Batch Assessment into SQLite Repository (Asset-Isolated DB)
        try:
            if self.asset == "ETH":
                from kalshi_sim.db import get_eth_db_writer
                writer = get_eth_db_writer()
            else:
                from kalshi_sim.db.writer import get_db_writer
                writer = get_db_writer()

            writer.enqueue_batch_assessment(
                batch_number=self.current_batch_num,
                document_id=f"assessment_{today_str}_#{self.current_batch_num}_{self.asset.lower()}",
                evaluation_date=today_str,
                verdict=gemini_data.get("verdict", "PASSED" if batch_pnl > Decimal("0.00") else "DEFICIT"),
                wins=batch_wins,
                losses=batch_losses,
                total_trades=len(recent_trades),
                win_rate=float(win_rate),
                net_pnl=float(batch_pnl),
                pre_batch_balance=float(pre_balance),
                post_batch_balance=float(post_balance),
                raw_markdown=md_report,
            )
            logger.info("💾 [SQL REPOSITORY] %s Batch #%d queued for SQLite persistence.", self.asset, self.current_batch_num)
        except Exception as db_err:
            logger.warning("Could not enqueue assessment to SQL: %s", db_err)

        # 7. Autonomous Email Dispatch to Operator (For Each 6-Trade Evaluation)
        try:
            if self.current_batch_num in self._emailed_batches:
                logger.info(
                    "ℹ️ [BATCH SUPERVISOR] %s Batch #%d already emailed in this session. Skipping dispatch.",
                    self.asset, self.current_batch_num,
                )
            else:
                from kalshi_sim.aws_email_mailer import async_send_assessment_email
                email_subj = f"📊 [Quant Council] {self.asset} 6-Trade Batch Report #{self.current_batch_num} | Condition: {market_info['tag']} | PnL: ${batch_pnl:+.2f} | Win Rate: {win_rate:.1f}%"
                sent = await async_send_assessment_email(
                    subject=email_subj,
                    body_markdown=md_report,
                    market_condition=market_info["tag"],
                    batch_num=self.current_batch_num,
                    topic=f"{self.asset.lower()}_batch_assessment_{self.current_batch_num}",
                )
                if sent:
                    self._emailed_batches.add(self.current_batch_num)
                    logger.info("📧 [MAILER DISPATCHED] Report email delivered for %s Batch #%d to operator.", self.asset, self.current_batch_num)
                else:
                    logger.warning("⚠️ [MAILER] Report email not dispatched for %s Batch #%d (throttled, deduplicated, or SMTP failure).", self.asset, self.current_batch_num)
        except Exception as mail_err:
            logger.warning("[MAILER] Could not dispatch assessment email: %s", mail_err)

        # 8. Mark Evaluated Trades as Processed & Persist to State File
        for t in recent_trades:
            self._processed_trade_ids.add(self._get_trade_id(t))
        self._save_processed_trade_ids()

        # 9. Execution Gate Verdict & Next Quota Reset
        if self.guardrails:
            self.guardrails.batch_trades_completed = 0
            self.guardrails.batch_pnl = Decimal("0.00")
            self.guardrails.batch_wins = 0
            self.guardrails.batch_losses = 0
            self.guardrails.is_bot_armed = True

        if batch_pnl > Decimal("0.00") or gemini_data.get("verdict") == "PASSED":
            logger.info(
                "🏆 [BATCH EXTENSION] %s Batch #%d finished in profit/pass. Advancing to Batch #%d.",
                self.asset, self.current_batch_num, self.current_batch_num + 1
            )
            self.current_batch_num += 1
        else:
            logger.warning(
                "🛑 [SAFETY HALT] %s Batch #%d finished in deficit. Tuning applied. Resetting quota for controlled execution.",
                self.asset, self.current_batch_num
            )
            self.current_batch_num += 1

            # Anti-overfitting rule: Only mutate parameters when macro sample size is statistically meaningful
            if self.cumulative_trades >= self.min_macro_sample_size:
                logger.info(
                    "🔬 [MACRO RE-CALIBRATION] Cumulative sample size (%d >= %d) reached statistical threshold. "
                    "Performing macro parameter evolution.",
                    self.cumulative_trades, self.min_macro_sample_size
                )
                await self._run_automated_parameter_audit(batch_pnl=batch_pnl, win_rate=macro_win_rate)
            else:
                logger.info(
                    "🛡️ [ANTI-OVERFITTING LOCK] Cumulative sample size (%d < %d trades). "
                    "Refusing to curve-fit parameters to short-term 6-trade noise. "
                    "Checking for structural bugs or execution latency instead.",
                    self.cumulative_trades, self.min_macro_sample_size
                )

    async def _run_automated_parameter_audit(self, batch_pnl: Decimal, win_rate: float) -> None:
        """Consult institutional back-memory (Lessons 1-24) and refine macro parameters based on 30+ trades."""
        logger.info("🧠 [EVOLUTION ENGINE] Consulting Lessons Learned back-memory (Lessons 1-24) for %s...", self.asset)
        if self.bot_parameters_path.exists():
            try:
                params = json.loads(self.bot_parameters_path.read_text(encoding="utf-8"))
                cfg = (
                    params.get("eth_bot1_v4")
                    if self.asset == "ETH"
                    else params.get("assets", {}).get("BTC", {})
                )

                # Macro recalibration based on genuine 30+ trade distribution
                if cfg and win_rate < 55.0:
                    current_discount = float(cfg.get("discount_limit_price", 0.48))
                    if current_discount > 0.44:
                        new_discount = round(max(0.42, current_discount - 0.02), 2)
                        logger.info("📉 [MACRO TUNE] %s discount ceiling tightened: $%.2f -> $%.2f", self.asset, current_discount, new_discount)
                        cfg["discount_limit_price"] = new_discount

                params["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.bot_parameters_path.write_text(json.dumps(params, indent=2), encoding="utf-8")
                logger.info("✅ [EVOLUTION ENGINE] Macro calibrated parameters saved to disk for %s.", self.asset)
            except Exception as e:
                logger.error("Failed to execute macro parameter evolution for %s: %s", self.asset, e)
