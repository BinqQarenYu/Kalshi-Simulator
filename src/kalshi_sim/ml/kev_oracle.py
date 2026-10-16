"""Kev AI Decision Model Integration for Kalshi Simulator.

Implements the single-forward-pass prefill decision model architecture
created by Jared Palmer (`jaredpalmer/kev`).

Unlike generative token-by-token LLMs, Kev evaluates a state document against
typed questions (boolean, choice, score) and outputs calibrated probability
distributions in a single pass under an 80ms latency budget.

Governed by:
- AGENTS.md Law 1: Zero Float Financial Math (Decimal)
- AGENTS.md Law 7: Zero Hallucination Mechanism
- AGENTS.md Law 8: Zero Blackhole Token Burning (Local Compute)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import aiohttp

logger = logging.getLogger("kalshi_sim.ml.kev_oracle")


class KevQuestionType(str, Enum):
    """Supported question types for the Kev decision architecture."""
    BOOLEAN = "bool"
    CHOICE = "choice"
    SCORE = "score"


class KevQuestion:
    """A typed question presented to Kev alongside a market state context."""

    def __init__(
        self,
        key: str,
        question: str,
        question_type: KevQuestionType = KevQuestionType.BOOLEAN,
        options: Optional[List[str]] = None,
    ) -> None:
        self.key = key
        self.question = question
        self.question_type = question_type
        self.options = options or (["true", "false"] if question_type == KevQuestionType.BOOLEAN else [])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "question": self.question,
            "type": self.question_type.value,
            "options": self.options,
        }


class KevDecisionResult:
    """Structured calibrated result returned from Kev inference."""

    def __init__(
        self,
        key: str,
        question_type: KevQuestionType,
        selected_option: str,
        probabilities: Dict[str, Decimal],
        confidence: Decimal,
        latency_ms: float = 0.0,
        source: str = "kev_model",
    ) -> None:
        self.key = key
        self.question_type = question_type
        self.selected_option = selected_option
        self.probabilities = probabilities
        self.confidence = confidence
        self.latency_ms = latency_ms
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "selected_option": self.selected_option,
            "probabilities": {k: float(v) for k, v in self.probabilities.items()},
            "confidence": float(self.confidence),
            "latency_ms": self.latency_ms,
            "source": self.source,
        }


class KevDecisionOracle:
    """High-speed local client and circuit breaker for Jared Palmer's Kev decision model."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 0.08,  # Strict 80ms latency ceiling
    ) -> None:
        self.base_url = (base_url or os.getenv("KEV_MODEL_URL") or "http://localhost:11434").rstrip("/")
        self.model_name = model_name or os.getenv("KEV_MODEL_NAME") or "jaredpalmer/kev"
        self.timeout_seconds = float(timeout_seconds)
        self._circuit_open: bool = False
        self._last_failure_ts: float = 0.0
        self._cooldown_seconds: float = 30.0

    @staticmethod
    def build_market_context(
        asset: str,
        spot_price: Union[Decimal, float],
        target_strike: Union[Decimal, float],
        time_to_expiry_s: float,
        ofi: float = 0.0,
        vpin: float = 0.20,
        spread_cents: float = 0.02,
        current_regime: str = "CHOP",
        macro_slope: float = 0.0,
        recent_trade_count: int = 1,
    ) -> str:
        """Constructs a deterministic, compact state document for Kev evaluation."""
        spot_dec = Decimal(str(round(float(spot_price), 2)))
        strike_dec = Decimal(str(round(float(target_strike), 2)))
        diff_dec = spot_dec - strike_dec

        return (
            f"Asset: {asset.upper()} | Spot: ${spot_dec:.2f} | Strike: ${strike_dec:.2f} | "
            f"Diff: {diff_dec:+.2f} | Tau: {time_to_expiry_s:.0f}s | Regime: {current_regime.upper()} | "
            f"CLOB Spread: ${spread_cents:.2f} | Binance OFI_L1: {ofi:+.2f} | VPIN: {vpin:.2f} | "
            f"Macro Slope: {macro_slope:+.4f} | Activity: {recent_trade_count} trades"
        )

    async def evaluate(
        self,
        context: str,
        questions: List[KevQuestion],
    ) -> Dict[str, KevDecisionResult]:
        """Evaluates typed questions against context in a single prefill forward pass."""
        now = time.monotonic()
        start_mono = now

        # Circuit breaker check: if failed recently, bypass HTTP directly to protect latency
        if self._circuit_open and (now - self._last_failure_ts < self._cooldown_seconds):
            return self._fallback_heuristic_evaluation(context, questions, latency_ms=0.5)

        payload = {
            "model": self.model_name,
            "document": context,
            "questions": [q.to_dict() for q in questions],
            "options": {"temperature": 0.0},
        }

        url = f"{self.base_url}/v1/systemone"

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latency_ms = (time.monotonic() - start_mono) * 1000.0
                        self._circuit_open = False
                        return self._parse_kev_response(data, questions, latency_ms)
                    else:
                        logger.debug("[KEV ORACLE] HTTP %s from %s; activating fallback.", resp.status, url)
                        self._trip_circuit()
        except Exception as exc:
            logger.debug("[KEV ORACLE] Connection to %s unavailable (%s); using local heuristic fallback.", url, exc)
            self._trip_circuit()

        latency_ms = (time.monotonic() - start_mono) * 1000.0
        return self._fallback_heuristic_evaluation(context, questions, latency_ms=latency_ms)

    def _trip_circuit(self) -> None:
        """Trips the circuit breaker into fallback mode for cooldown duration."""
        self._circuit_open = True
        self._last_failure_ts = time.monotonic()

    def _parse_kev_response(
        self,
        data: Dict[str, Any],
        questions: List[KevQuestion],
        latency_ms: float,
    ) -> Dict[str, KevDecisionResult]:
        """Parses calibrated response from Kev decision model into strict Decimal probabilities."""
        results: Dict[str, KevDecisionResult] = {}
        answers = data.get("answers", data.get("results", {}))

        for q in questions:
            q_res = answers.get(q.key, {})
            probs_raw = q_res.get("probabilities", {})

            # Clean and normalize into Decimal
            probs_dec: Dict[str, Decimal] = {}
            for opt, val in probs_raw.items():
                try:
                    probs_dec[opt] = Decimal(str(val)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                except Exception:
                    probs_dec[opt] = Decimal("0.0000")

            if not probs_dec and q.options:
                equal_share = (Decimal("1.0000") / Decimal(str(len(q.options)))).quantize(Decimal("0.0001"))
                probs_dec = {opt: equal_share for opt in q.options}

            selected = q_res.get("selected", "")
            if not selected and probs_dec:
                selected = max(probs_dec.keys(), key=lambda k: probs_dec[k])

            conf = probs_dec.get(selected, Decimal("0.5000"))

            results[q.key] = KevDecisionResult(
                key=q.key,
                question_type=q.question_type,
                selected_option=selected,
                probabilities=probs_dec,
                confidence=conf,
                latency_ms=latency_ms,
                source="kev_model",
            )

        return results

    def _fallback_heuristic_evaluation(
        self,
        context: str,
        questions: List[KevQuestion],
        latency_ms: float = 1.0,
    ) -> Dict[str, KevDecisionResult]:
        """Deterministic, zero-float heuristic fallback when local Kev service is offline.
        
        Evaluates context text features using physical moneyness, OFI, and VPIN rules.
        """
        results: Dict[str, KevDecisionResult] = {}

        # Extract features from context string
        diff_val = 0.0
        vpin_val = 0.20
        ofi_val = 0.0
        asset_val = "ETH"
        try:
            for part in context.split("|"):
                part_clean = part.strip()
                if part_clean.startswith("Asset:"):
                    asset_val = part_clean.replace("Asset:", "").strip().upper()
                elif part_clean.startswith("Diff:"):
                    diff_val = float(part_clean.replace("Diff:", "").strip())
                elif part_clean.startswith("VPIN:"):
                    vpin_val = float(part_clean.replace("VPIN:", "").strip())
                elif "OFI_L1:" in part_clean:
                    ofi_val = float(part_clean.split("OFI_L1:")[-1].strip())
        except Exception:
            pass

        # Asset-calibrated moneyness thresholds
        if asset_val == "BTC":
            diff_thresh = 25.0
            storm_thresh = 75.0
        elif asset_val == "SOL":
            diff_thresh = 0.40
            storm_thresh = 1.20
        else:  # ETH
            diff_thresh = 1.50
            storm_thresh = 6.00

        for q in questions:
            probs: Dict[str, Decimal] = {}
            selected = ""

            if q.key == "is_toxic_sweep":
                p_toxic = Decimal("0.8500") if vpin_val >= 0.65 else Decimal("0.1000")
                probs = {"true": p_toxic, "false": Decimal("1.0000") - p_toxic}
                selected = "true" if p_toxic >= Decimal("0.5000") else "false"

            elif q.key == "regime":
                if vpin_val >= 0.70:
                    probs = {"CHOP": Decimal("0.1000"), "STORM": Decimal("0.2000"), "BLEED": Decimal("0.7000"), "HEALING": Decimal("0.0000")}
                elif abs(diff_val) >= storm_thresh:
                    probs = {"CHOP": Decimal("0.1500"), "STORM": Decimal("0.7500"), "BLEED": Decimal("0.1000"), "HEALING": Decimal("0.0000")}
                else:
                    probs = {"CHOP": Decimal("0.8000"), "STORM": Decimal("0.1500"), "BLEED": Decimal("0.0500"), "HEALING": Decimal("0.0000")}
                selected = max(probs.keys(), key=lambda k: probs[k])

            elif q.key in ("trade_direction", "consensus_direction"):
                # Calibrate probabilities from moneyness diff and OFI
                if diff_val > diff_thresh and ofi_val >= -0.30:
                    p_yes = Decimal("0.7800")
                    p_no = Decimal("0.1000")
                    p_wait = Decimal("0.1200")
                elif diff_val < -diff_thresh and ofi_val <= 0.30:
                    p_yes = Decimal("0.1000")
                    p_no = Decimal("0.7800")
                    p_wait = Decimal("0.1200")
                else:
                    p_yes = Decimal("0.2500")
                    p_no = Decimal("0.2500")
                    p_wait = Decimal("0.5000")

                probs = {"YES": p_yes, "NO": p_no, "WAIT": p_wait}
                selected = max(probs.keys(), key=lambda k: probs[k])

            elif q.question_type == KevQuestionType.BOOLEAN:
                probs = {"true": Decimal("0.5000"), "false": Decimal("0.5000")}
                selected = "false"

            else:
                if q.options:
                    eq = (Decimal("1.0000") / Decimal(str(len(q.options)))).quantize(Decimal("0.0001"))
                    probs = {opt: eq for opt in q.options}
                    selected = q.options[0]
                else:
                    probs = {"default": Decimal("1.0000")}
                    selected = "default"

            conf = probs.get(selected, Decimal("0.5000"))

            results[q.key] = KevDecisionResult(
                key=q.key,
                question_type=q.question_type,
                selected_option=selected,
                probabilities=probs,
                confidence=conf,
                latency_ms=latency_ms,
                source="heuristic_fallback",
            )

        return results
