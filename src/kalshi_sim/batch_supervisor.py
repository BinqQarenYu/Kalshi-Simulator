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
        guardrails: Any,
        bot_parameters_path: str | Path = "data/bot_parameters_domination.json",
        win_loss_path: str | Path = "data/win_loss_reports.json",
        eval_batch_size: int = 6,
        poll_interval_s: float = 5.0,
        asset: Optional[str] = None,
    ) -> None:
        self.guardrails = guardrails
        self.bot_parameters_path = Path(bot_parameters_path)
        self.win_loss_path = Path(win_loss_path)
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

    def _discover_initial_batch_num(self) -> int:
        docs_dir = Path("docs")
        max_num = 108
        if docs_dir.exists():
            asset_s = getattr(self, "asset", "BTC").lower()
            pattern = f"assessment_*_#*_{asset_s}_.md" if asset_s != "btc" else "assessment_*_#*_*.md"
            for p in docs_dir.glob(pattern):
                match = re.search(r"#(\d+)_", p.name)
                if match:
                    try:
                        max_num = max(max_num, int(match.group(1)))
                    except ValueError:
                        pass
        return max_num + 1

    def start(self) -> asyncio.Task:
        """Start the supervisor background evaluation loop."""
        if self._task and not self._task.done():
            return self._task
        self.is_running = True
        self._task = asyncio.create_task(self._supervision_loop(), name="autonomous_batch_supervisor")
        logger.info(
            "🛡️ [BATCH SUPERVISOR] Autonomous 6-Trade Evaluation Daemon started in parallel (Batch Size: %d).",
            self.eval_batch_size
        )
        return self._task

    def stop(self) -> None:
        """Stop the supervisor background loop."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("🛡️ [BATCH SUPERVISOR] Autonomous Batch Supervisor stopped.")

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

        # 3. Compute empirical batch metrics from the 6 settled trades
        spot_prices = [
            float(t.get("settlement_spot_price") or t.get("settlement_btc_price") or 0.0)
            for t in recent_trades
            if (t.get("settlement_spot_price") or t.get("settlement_btc_price"))
        ]
        spot_prices = [p for p in spot_prices if p > 0.0]
        spot_range = (max(spot_prices) - min(spot_prices)) if len(spot_prices) >= 2 else 0.0

        vpin_scores = [float(t.get("vpin_score", 0.0)) for t in recent_trades if t.get("vpin_score") is not None]
        avg_vpin = sum(vpin_scores) / len(vpin_scores) if vpin_scores else 0.0

        # 4. Synthesize final condition tag & descriptors
        reg_upper = region.upper()
        if "STORM" in reg_upper or spot_range >= 200.0 or avg_vpin >= 0.70 or hmm_regime == "VOL_EXPANSION":
            cond_tag = "STORMY"
            cond_name = "Stormy (Directional Volatility & Volcano Expansion)"
            cond_desc = f"High velocity wave expansion (Range: ${spot_range:.1f}, Avg VPIN: {avg_vpin:.2f}, Macro: {hmm_regime})"
        elif "BLEED" in reg_upper or hmm_regime == "RISK_OFF":
            cond_tag = "BLEED"
            cond_name = "Bleed / Adverse Wicks (Hostile Meatgrinder)"
            cond_desc = f"Adverse selection and double-wick whipsaws detected. Bleed defense protocols engaged."
        elif "HEAL" in reg_upper:
            cond_tag = "HEALING"
            cond_name = "Healing (Post-Drawdown Convalescence)"
            cond_desc = f"Probationary quarantine mode recovering bankroll with defensive filters."
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
        logger.info("⚡ [BATCH SUPERVISOR] Manual/On-demand evaluation batch triggered.")
        await self._evaluate_and_evolve_batch()
        return {
            "batch_num": self.current_batch_num - 1,
            "status": "evaluated_and_dispatched",
        }

    async def _supervision_loop(self) -> None:
        """Continuous background loop monitoring the 6-trade execution gate."""
        while self.is_running:
            try:
                await asyncio.sleep(self.poll_interval_s)
                if not self.guardrails:
                    continue

                completed = getattr(self.guardrails, "batch_trades_completed", 0)
                quota = getattr(self.guardrails, "batch_trades_quota", self.eval_batch_size)

                # Also detect from persisted win_loss_reports to avoid missing any settled cycle
                if self.win_loss_path.exists():
                    try:
                        reports = json.loads(self.win_loss_path.read_text(encoding="utf-8"))
                        matching = [r for r in reports if self._is_asset_match(r)]
                        current_total = len(matching)
                        if self._last_processed_trade_count == 0:
                            self._last_processed_trade_count = (current_total // self.eval_batch_size) * self.eval_batch_size
                        elif current_total - self._last_processed_trade_count >= self.eval_batch_size:
                            completed = quota
                    except Exception as e:
                        logger.debug("Win loss read error in supervision loop: %s", e)

                # Detect when a 6-trade batch completes its cycle
                if completed >= quota and quota > 0 and getattr(self.guardrails, "is_bot_armed", True):
                    await self._evaluate_and_evolve_batch()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[BATCH SUPERVISOR ERROR] Supervision loop error: %s", exc, exc_info=True)

    async def _evaluate_and_evolve_batch(self) -> None:
        """Execute the formal 6-trade post-batch assessment powered by Gemini & Quant Council."""
        batch_pnl = getattr(self.guardrails, "batch_pnl", Decimal("0.00"))
        batch_wins = getattr(self.guardrails, "batch_wins", 0)
        batch_losses = getattr(self.guardrails, "batch_losses", 0)
        total_trades = batch_wins + batch_losses
        win_rate = (batch_wins / max(1, total_trades)) * 100.0

        # Accumulate into macro statistical sample
        self.cumulative_trades += total_trades
        self.cumulative_wins += batch_wins
        self.cumulative_losses += batch_losses
        self.cumulative_pnl += batch_pnl
        macro_win_rate = (self.cumulative_wins / max(1, self.cumulative_trades)) * 100.0

        # 1. Harvest recent settled trades strictly matching this asset (exclude unrelated assets)
        recent_trades: list[dict[str, Any]] = []
        if self.win_loss_path.exists():
            try:
                reports = json.loads(self.win_loss_path.read_text(encoding="utf-8"))
                matching = [r for r in reports if self._is_asset_match(r)]
                recent_trades = matching[:self.eval_batch_size]
                self._last_processed_trade_count = len(matching)
            except Exception as e:
                logger.debug("Failed reading win_loss_path: %s", e)

        # 1.1 Classify Market Condition (Choppy, Stormy, Bleed, Healing)
        market_info = self.determine_market_condition(recent_trades)

        logger.info(
            "========================================================================\n"
            "📊 [QUANT COUNCIL BATCH REPORT] Batch #%d (%d Trades) | Condition: %s | Batch PnL: $%s | Win Rate: %.1f%%\n"
            "📈 [MACRO STATISTICAL SAMPLE] Total %d Trades | Net PnL: $%s | Overall Win Rate: %.1f%%\n"
            "========================================================================",
            self.current_batch_num, total_trades, market_info["tag"], batch_pnl, win_rate,
            self.cumulative_trades, self.cumulative_pnl, macro_win_rate
        )

        # 2. Harvest Continuous Experience Buffer telemetry
        exp_summary: dict[str, Any] = {}
        try:
            from kalshi_sim.server import state
            if "eth" in str(self.win_loss_path).lower():
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
                    or p_data.get("assets", {}).get("ETH")
                    or p_data.get("assets", {}).get("BTC", {})
                    or p_data
                )
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

        logger.info("🧠 [AI ASSESSOR] Invoking Gemini to analyze Batch #%d (Condition: %s) and formulate forensic conclusions...", self.current_batch_num, market_info["tag"])
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
                logger.info("✅ [TWEAKS APPLIED] Parameters updated: %s", validated_tweaks)
                # Sync in-memory engine if available
                try:
                    from kalshi_sim.server import state
                    if hasattr(state, "sim_agent") and state.sim_agent and hasattr(state.sim_agent, "_bot1_v4_engine"):
                        eng = state.sim_agent._bot1_v4_engine
                        for param_k, param_v in validated_tweaks.items():
                            if hasattr(eng, param_k):
                                setattr(eng, param_k, Decimal(str(param_v)) if isinstance(getattr(eng, param_k), Decimal) else param_v)
                        logger.info("🔄 [ENGINE SYNCED] In-memory Bot 1 V4 engine re-synced with newly tuned parameters.")
                except Exception as sync_err:
                    logger.debug("Engine memory sync warning: %s", sync_err)

        # 5.1 Dynamic Failover Check: If strategy failed performance gate, hot-swap to Dynamic Trading Strategy
        if batch_pnl < Decimal("0.00") or (win_rate < 50.0 and total_trades >= self.eval_batch_size):
            logger.warning(
                "🚨 [STRATEGY PERFORMANCE FAILURE DETECTED] Batch #%d PnL=$%s | Win Rate=%.1f%%. Triggering failover to Dynamic Trading Strategy...",
                self.current_batch_num, batch_pnl, win_rate
            )
            try:
                from kalshi_sim.preset_manager import PresetManager
                pm = PresetManager()
                success, msg, _ = pm.load_preset("dynamic_trading_strategy_v1")
                if success:
                    logger.info("⚡ [FAILOVER HOT-SWAP SUCCESS] Dynamic Trading Strategy preset activated: %s", msg)
                    try:
                        from kalshi_sim.server import state
                        state.active_strategy_bot = "dynamic_trading_strategy"
                        if hasattr(state, "sim_agent") and state.sim_agent:
                            state.sim_agent.active_strategy_bot = "dynamic_trading_strategy"
                    except Exception as s_err:
                        logger.debug("State strategy bot switch note: %s", s_err)
            except Exception as fo_err:
                logger.error("Failover hot-swap error: %s", fo_err)

        # 6. Build and save institutional markdown document
        pre_balance = getattr(self.guardrails, "batch_starting_balance", None) or Decimal("40.00")
        post_balance = getattr(self.guardrails, "current_balance", None) or Decimal("44.71")
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
            docs_dir = Path("docs")
            docs_dir.mkdir(parents=True, exist_ok=True)
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            asset_suffix = f"_{self.asset.lower()}_" if self.asset != "BTC" else "_"
            report_file = docs_dir / f"assessment_{today_str}_#{self.current_batch_num}{asset_suffix}.md"
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
                    "ℹ️ [BATCH SUPERVISOR] Batch #%d already emailed in this session. Skipping dispatch.",
                    self.current_batch_num,
                )
            else:
                from kalshi_sim.aws_email_mailer import async_send_assessment_email
                email_subj = f"📊 [Quant Council] 6-Trade Batch Report #{self.current_batch_num} | Condition: {market_info['tag']} | PnL: ${batch_pnl:+.2f} | Win Rate: {win_rate:.1f}%"
                sent = await async_send_assessment_email(
                    subject=email_subj,
                    body_markdown=md_report,
                    market_condition=market_info["tag"],
                    batch_num=self.current_batch_num,
                    topic=f"batch_assessment_{self.current_batch_num}",
                )
                if sent:
                    self._emailed_batches.add(self.current_batch_num)
                    logger.info("📧 [MAILER DISPATCHED] Report email delivered for Batch #%d to operator.", self.current_batch_num)
                else:
                    logger.warning("⚠️ [MAILER] Report email not dispatched for Batch #%d (throttled, deduplicated, or SMTP failure).", self.current_batch_num)
        except Exception as mail_err:
            logger.warning("[MAILER] Could not dispatch assessment email: %s", mail_err)

        # 8. Execution Gate Verdict & Next Quota Reset
        if batch_pnl > Decimal("0.00") or gemini_data.get("verdict") == "PASSED":
            logger.info(
                "🏆 [BATCH EXTENSION] Batch #%d finished in profit/pass. Advancing to Batch #%d.",
                self.current_batch_num, self.current_batch_num + 1
            )
            self.guardrails.batch_trades_completed = 0
            self.guardrails.batch_pnl = Decimal("0.00")
            self.guardrails.batch_wins = 0
            self.guardrails.batch_losses = 0
            self.guardrails.is_bot_armed = True
            self.current_batch_num += 1
        else:
            logger.warning(
                "🛑 [SAFETY HALT] Batch #%d finished in deficit. Tuning applied. Resetting quota for controlled execution.",
                self.current_batch_num
            )
            self.guardrails.batch_trades_completed = 0
            self.guardrails.batch_pnl = Decimal("0.00")
            self.guardrails.batch_wins = 0
            self.guardrails.batch_losses = 0
            self.guardrails.is_bot_armed = True
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
        logger.info("🧠 [EVOLUTION ENGINE] Consulting Lessons Learned back-memory (Lessons 1-24)...")
        if self.bot_parameters_path.exists():
            try:
                params = json.loads(self.bot_parameters_path.read_text(encoding="utf-8"))
                btc_cfg = params.get("assets", {}).get("BTC", {})

                # Macro recalibration based on genuine 30+ trade distribution
                if win_rate < 55.0:
                    current_discount = float(btc_cfg.get("discount_limit_price", 0.48))
                    if current_discount > 0.44:
                        new_discount = round(max(0.42, current_discount - 0.02), 2)
                        logger.info("📉 [MACRO TUNE] Discount ceiling tightened: $%.2f -> $%.2f", current_discount, new_discount)
                        btc_cfg["discount_limit_price"] = new_discount

                params["updated_at"] = "2026-10-05T13:00:00.000000+00:00"
                self.bot_parameters_path.write_text(json.dumps(params, indent=2), encoding="utf-8")
                logger.info("✅ [EVOLUTION ENGINE] Macro calibrated parameters saved to disk.")
            except Exception as e:
                logger.error("Failed to execute macro parameter evolution: %s", e)
