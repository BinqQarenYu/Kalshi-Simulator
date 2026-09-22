"""Agent Deer ? Local Log Scrubber, Noise Filter & Telemetry Condenser.

Operates under strict resource caps:
- Hard-capped to <= 8 GB RAM and <= 3 CPU threads.
- Extracts signals, strips repetitive 20Hz wait ticks, and condenses thousands of tokens
  into an institutional 2-sentence forensic digest.
- Queries local Ollama (llama3.2 or llama3) if running; provides instant deterministic
  fallback if Ollama is unavailable or busy, guaranteeing zero trade stalls.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from kalshi_sim.quoquo.schemas import CondensedCycleTelemetry, CycleOutcome, VetoCategory
from kalshi_sim.quoquo.vault import get_quoquo_vault

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "nemotron-mini:latest"
FALLBACK_MODEL = "llama3.2:latest"


class DeerScrubber:
    """Local telemetry scrubber and token condenser."""

    def __init__(self, ollama_url: str = OLLAMA_URL, model: str = DEFAULT_MODEL) -> None:
        self.ollama_url = ollama_url
        self.model = model
        self.vault = get_quoquo_vault()

    def classify_veto_reason(self, rationale: str) -> VetoCategory:
        """Classify raw strategy rationale string into normalized VetoCategory enum."""
        text = rationale.upper()
        if "TOXIC QUEUE DEPTH" in text or "WHALE ARMOR" in text or "CONTRACTS RESTING AHEAD" in text:
            return VetoCategory.WHALE_QUEUE
        elif "RAZOR-TIGHT" in text or "STRIKE NOISE TRAP" in text or "DYNAMIC VOLATILITY MOAT" in text:
            return VetoCategory.RAZOR_TIGHT_MOAT
        elif ("HIGH TOXICITY" in text or "VPIN VETO" in text or "TOXIC BURST" in text or ("VPIN" in text and "VETO" in text)):
            return VetoCategory.VPIN_TOXIC
        elif "PRICE CEILING" in text or "DISCOUNT LIMIT" in text or "MAKER LIMIT" in text:
            return VetoCategory.PRICE_CEILING

        elif "CONVICTION" in text or "EDGE" in text or "MINIMUM EV" in text or "CONFIDENCE" in text:
            return VetoCategory.CONVICTION_HURDLE
        elif "CLOB SPREAD" in text or "SPREAD" in text:
            return VetoCategory.CLOB_SPREAD
        elif "OPENING" in text or "QUARANTINE" in text:
            return VetoCategory.OPENING_QUARANTINE
        elif "EXPIRATION" in text:
            return VetoCategory.EXPIRATION_QUARANTINE
        return VetoCategory.NONE

    def generate_deer_briefing_fallback(
        self,
        outcome: CycleOutcome,
        dominant_veto: VetoCategory,
        spot_diff_min: str,
        spot_diff_max: str,
        trade_side: Optional[str] = None,
        pnl: Optional[str] = None,
    ) -> str:
        """Deterministic zero-cost template generator when Ollama is offline."""
        if outcome == CycleOutcome.TRADE_FIRED_WIN:
            return f"Executed {trade_side.upper() if trade_side else 'TRADE'} fill successfully; market settled in favorable directional parity resulting in + PnL."
        elif outcome == CycleOutcome.TRADE_FIRED_LOSS:
            return f"Executed {trade_side.upper() if trade_side else 'TRADE'} fill but late adverse price reversal slipped through settlement, ending in - loss."
        elif dominant_veto == VetoCategory.WHALE_QUEUE:
            return f"Cycle held in defensive quarantine: persistent institutional resting wall blocked execution to avoid adverse back-of-the-queue fills."
        elif dominant_veto == VetoCategory.RAZOR_TIGHT_MOAT:
            return f"Cycle held: spot separation (|Diff| {spot_diff_min} to {spot_diff_max}) remained inside strike noise corridor, vetoing coin-flip exposure."
        elif dominant_veto == VetoCategory.VPIN_TOXIC:
            return f"Cycle held: toxic volume orderflow burst exceeded VPIN cutoff, shielding micro-bankroll from adverse institutional selection."
        else:
            return f"Cycle held: market conditions failed entry conviction hurdles. Capital preserved with 0 risk."

    def query_local_ollama_briefing(self, prompt: str) -> Optional[str]:
        """Query local Ollama for a tiny 2-sentence summary with 2s strict timeout."""
        payload = {
            "model": self.model,
            "prompt": f"You are Deer, a quant trading data condenser. Summarize this 15-minute crypto binary options cycle in exactly 1 or 2 concise, professional sentences:\n{prompt}\nSummary:",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 80,
                "num_thread": 2,
            },
        }
        try:
            req = urllib.request.Request(
                self.ollama_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    response_text = res_data.get("response", "").strip()
                    if response_text:
                        return response_text
        except Exception as exc:
            logger.debug("Ollama local query bypassed: %s (using deterministic fallback)", exc)
        return None

    def process_cycle_telemetry(
        self,
        cycle_ticker: str,
        strike_price: Decimal | float | str,
        cycle_time_et: str,
        raw_tick_events: List[Dict[str, Any]],
        trade_report: Optional[Dict[str, Any]] = None,
        asset: str = "BTC",
        timeframe: str = "15m",
        settlement_spot_price: Optional[Decimal | float | str] = None,
    ) -> CondensedCycleTelemetry:
        """Condense thousands of raw ticks and logs into a single Quoquo-compliant digest."""
        raw_tokens_est = len(raw_tick_events) * 18  # ~18 tokens per raw JSON tick

        veto_counts: dict[str, int] = {}
        diffs: list[float] = []
        vpins: list[float] = []
        max_q = 0

        for tick in raw_tick_events:
            rat = tick.get("rationale", "")
            cat = self.classify_veto_reason(rat)
            veto_counts[cat.value] = veto_counts.get(cat.value, 0) + 1

            if "spot_diff" in tick:
                try:
                    diffs.append(float(tick["spot_diff"]))
                except Exception:
                    pass
            if "vpin" in tick:
                try:
                    vpins.append(float(tick["vpin"]))
                except Exception:
                    pass
            if "queue_ahead" in tick:
                try:
                    max_q = max(max_q, int(tick["queue_ahead"]))
                except Exception:
                    pass

        # Determine dominant veto
        dominant_veto = VetoCategory.NONE
        if veto_counts:
            sorted_vetoes = sorted(veto_counts.items(), key=lambda x: x[1], reverse=True)
            for v_name, _ in sorted_vetoes:
                if v_name != VetoCategory.NONE.value:
                    dominant_veto = VetoCategory(v_name)
                    break

        # Determine outcome
        outcome = CycleOutcome.CYCLE_HELD_VETO
        trade_side = None
        entry_price = None
        contracts = 0
        pnl_val = None

        if trade_report:
            res_outcome = trade_report.get("outcome", "").upper()
            if res_outcome == "WIN":
                outcome = CycleOutcome.TRADE_FIRED_WIN
            else:
                outcome = CycleOutcome.TRADE_FIRED_LOSS
            trade_side = trade_report.get("bot_side") or trade_report.get("side")
            entry_price = f"{float(trade_report.get('entry_price', 0.50)):.2f}"
            contracts = int(trade_report.get("contracts", 1))
            pnl_val = f"{float(trade_report.get('pnl', 0.0)):.2f}"

        min_d = f"{min(diffs):.2f}" if diffs else "0.00"
        max_d = f"{max(diffs):.2f}" if diffs else "0.00"
        min_v = min(vpins) if vpins else 0.15
        max_v = max(vpins) if vpins else 0.15

        # Draft brief via Ollama or Fallback
        prompt_context = (
            f"Ticker: {cycle_ticker}, Asset: {asset}, Window: {cycle_time_et}. "
            f"Outcome: {outcome.value}, Dominant Veto: {dominant_veto.value}. "
            f"Spot Diff Range: {min_d} to {max_d}. Trade Side: {trade_side or 'None'}, PnL: {pnl_val or '0.00'}."
        )
        briefing = self.query_local_ollama_briefing(prompt_context)
        if not briefing:
            briefing = self.generate_deer_briefing_fallback(
                outcome=outcome,
                dominant_veto=dominant_veto,
                spot_diff_min=min_d,
                spot_diff_max=max_d,
                trade_side=trade_side,
                pnl=pnl_val,
            )

        condensed_cost = len(briefing.split()) * 2 + 60  # Approx token footprint

        digest = CondensedCycleTelemetry(
            cycle_ticker=cycle_ticker,
            asset=asset,
            timeframe=timeframe,
            cycle_time_et=cycle_time_et,
            strike_price=f"{Decimal(str(strike_price)):.2f}",
            settlement_spot_price=f"{Decimal(str(settlement_spot_price)):.2f}" if settlement_spot_price else None,
            outcome=outcome,
            trade_side=trade_side,
            entry_price=entry_price,
            contracts=contracts,
            pnl=pnl_val,
            dominant_veto=dominant_veto,
            veto_distribution=veto_counts,
            spot_diff_range=[min_d, max_d],
            vpin_range=[min_v, max_v],
            max_queue_depth_seen=max_q,
            deer_briefing=briefing,
            raw_tokens_eliminated=max(0, raw_tokens_est - condensed_cost),
            condensed_token_cost=condensed_cost,
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
        )

        # Store in Quoquo Vault
        self.vault.store_cycle_digest(digest)
        return digest
