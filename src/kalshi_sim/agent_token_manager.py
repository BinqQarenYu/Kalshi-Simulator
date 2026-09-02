"""AgentTokenManager — Agent Token & Gemini Credit Management Guardian.

Optimizes, governs, and tracks LLM token usage and Gemini credit consumption across all agents:
1. Deduplicates and caches prompt/response pairs using SHA256 context hashing (Redundancy Elimination).
2. Adaptive Market Delta Gating: Skips redundant LLM evaluations if market state delta is negligible.
3. Budget & Quota Circuit Breaker: Enforces daily/hourly token and credit budgets (Normal, Warning, Throttle, Hard Block).
4. Smart Model Routing: Dynamically routes requests between lightweight models (gemini-2.5-flash / local ONNX) and heavy reasoning models (gemini-2.5-pro).
5. Context Compression: Strips redundant JSON keys and formats floating-point numbers to minimize token consumption.
6. Real-time Telemetry: Tracks prompt tokens, completion tokens, credits used, tokens saved, and cache hit rate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple

logger = logging.getLogger("kalshi_sim.agent_token_manager")


@dataclass
class ModelPricingConfig:
    """Pricing and credit point conversion rules for a given AI/LLM model."""
    model_id: str
    prompt_token_cost_per_1k: float  # USD cost per 1,000 prompt tokens
    completion_token_cost_per_1k: float  # USD cost per 1,000 completion tokens
    credits_per_1k_tokens: float  # Gemini / platform credit points per 1,000 tokens
    description: str


# Pre-configured model pricing & credit rules
MODEL_REGISTRY: Dict[str, ModelPricingConfig] = {
    "gemini-2.5-flash": ModelPricingConfig(
        model_id="gemini-2.5-flash",
        prompt_token_cost_per_1k=0.000075,
        completion_token_cost_per_1k=0.00030,
        credits_per_1k_tokens=1.0,
        description="Fast & lightweight multimodal model for routine market scans",
    ),
    "gemini-2.5-pro": ModelPricingConfig(
        model_id="gemini-2.5-pro",
        prompt_token_cost_per_1k=0.00125,
        completion_token_cost_per_1k=0.00500,
        credits_per_1k_tokens=10.0,
        description="Deep reasoning model for high-conviction quantitative analysis",
    ),
    "gemini-1.5-flash": ModelPricingConfig(
        model_id="gemini-1.5-flash",
        prompt_token_cost_per_1k=0.000075,
        completion_token_cost_per_1k=0.00030,
        credits_per_1k_tokens=1.0,
        description="Legacy fast model",
    ),
    "onnx_microstructure_local": ModelPricingConfig(
        model_id="onnx_microstructure_local",
        prompt_token_cost_per_1k=0.0,
        completion_token_cost_per_1k=0.0,
        credits_per_1k_tokens=0.0,
        description="Zero-cost local ONNX CPU neural net inference",
    ),
    "3_step_domination_local": ModelPricingConfig(
        model_id="3_step_domination_local",
        prompt_token_cost_per_1k=0.0,
        completion_token_cost_per_1k=0.0,
        credits_per_1k_tokens=0.0,
        description="Zero-cost local quantitative playbook engine",
    ),
}


@dataclass
class TokenUsageMetrics:
    """Sliding-window token and credit consumption metrics."""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_credits_consumed: float = 0.0
    total_cost_dollars: float = 0.0

    # Redundancy & Cache Savings
    total_cached_requests: int = 0
    total_uncached_requests: int = 0
    tokens_saved: int = 0
    credits_saved: float = 0.0
    cost_saved_dollars: float = 0.0

    # Sliding window velocity (last 60s)
    tokens_last_minute: int = 0
    credits_last_minute: float = 0.0
    requests_last_minute: int = 0


class AgentTokenManager:
    """Agent Token & Gemini Credit Management Guardian."""

    def __init__(
        self,
        daily_token_budget: int = 1_000_000,
        daily_credit_budget: float = 500.0,
        tpm_limit: int = 60_000,  # Tokens Per Minute
        rpm_limit: int = 120,     # Requests Per Minute
        cache_max_entries: int = 500,
        default_cache_ttl_seconds: float = 60.0,
        min_market_price_delta: float = 1.00,  # $1.00 BTC spot delta required to trigger fresh LLM eval
    ) -> None:
        self.daily_token_budget = daily_token_budget
        self.daily_credit_budget = daily_credit_budget
        self.tpm_limit = tpm_limit
        self.rpm_limit = rpm_limit
        self.cache_max_entries = cache_max_entries
        self.default_cache_ttl_seconds = default_cache_ttl_seconds
        self.min_market_price_delta = min_market_price_delta

        # Usage accounting
        self.metrics = TokenUsageMetrics()
        self.usage_by_model: Dict[str, Dict[str, Any]] = {}
        self.usage_by_agent: Dict[str, Dict[str, Any]] = {}

        # Prompt & Context Cache (LRU: SHA256 Hash -> (response, expiry_mono, token_cost_saved))
        self._prompt_cache: OrderedDict[str, Tuple[Any, float, int, float]] = OrderedDict()

        # Market Delta Gating State (ticker -> last_eval_dict)
        self._last_market_evals: Dict[str, Dict[str, Any]] = {}

        # Sliding window timestamps ((timestamp_mono, tokens, credits))
        self._sliding_window: List[Tuple[float, int, float]] = []

        # Budget state
        self._start_time_utc = datetime.now(timezone.utc).isoformat()
        self._budget_status: Literal["NORMAL", "WARNING", "THROTTLE", "HARD_BLOCK"] = "NORMAL"

    # -------------------------------------------------------------------------
    # 1. Redundancy Elimination & Prompt / Context Caching
    # -------------------------------------------------------------------------

    def compute_context_hash(self, context_or_prompt: Any) -> str:
        """Generate deterministic SHA256 hash for input context or prompt text."""
        if isinstance(context_or_prompt, str):
            raw_str = context_or_prompt
        elif isinstance(context_or_prompt, dict):
            # Sort keys for deterministic JSON string representation
            raw_str = json.dumps(context_or_prompt, sort_keys=True, default=str)
        else:
            raw_str = str(context_or_prompt)

        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def get_cached_response(self, context_or_prompt: Any) -> Optional[Dict[str, Any]]:
        """Fetch cached AI response if context matches a recent evaluation within TTL."""
        cache_key = self.compute_context_hash(context_or_prompt)
        now_mono = time.monotonic()

        if cache_key in self._prompt_cache:
            response, expiry_mono, saved_tokens, saved_credits = self._prompt_cache[cache_key]
            if now_mono <= expiry_mono:
                # Move key to end (LRU)
                self._prompt_cache.move_to_end(cache_key)

                # Record cache hit savings
                self.metrics.total_cached_requests += 1
                self.metrics.tokens_saved += saved_tokens
                self.metrics.credits_saved += saved_credits
                self.metrics.cost_saved_dollars += (saved_tokens / 1000.0) * 0.0001

                logger.debug(
                    "🎯 [TOKEN MANAGER CACHE HIT] Saved %d tokens (%.2f credits) via SHA256 context deduplication.",
                    saved_tokens, saved_credits
                )
                return {
                    "data": response,
                    "is_cached": True,
                    "saved_tokens": saved_tokens,
                    "saved_credits": saved_credits,
                }
            else:
                # Expired entry
                del self._prompt_cache[cache_key]

        return None

    def cache_response(
        self,
        context_or_prompt: Any,
        response_data: Any,
        estimated_tokens: int = 500,
        model_id: str = "gemini-2.5-flash",
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """Store prompt response in LRU cache to eliminate duplicate future API requests."""
        cache_key = self.compute_context_hash(context_or_prompt)
        now_mono = time.monotonic()
        ttl = ttl_seconds if ttl_seconds is not None else self.default_cache_ttl_seconds
        expiry_mono = now_mono + ttl

        pricing = MODEL_REGISTRY.get(model_id, MODEL_REGISTRY["gemini-2.5-flash"])
        saved_credits = (estimated_tokens / 1000.0) * pricing.credits_per_1k_tokens

        # Enforce LRU capacity limit
        if len(self._prompt_cache) >= self.cache_max_entries:
            self._prompt_cache.popitem(last=False)

        self._prompt_cache[cache_key] = (response_data, expiry_mono, estimated_tokens, saved_credits)

    # -------------------------------------------------------------------------
    # 2. Adaptive Market Delta Gating (State Change Filtering)
    # -------------------------------------------------------------------------

    def should_evaluate_market_state(
        self,
        ticker: str,
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        force_eval: bool = False,
    ) -> Tuple[bool, str]:
        """Determine if a market state change is significant enough to justify an AI call.

        If price movement is < min_market_price_delta and expiry hasn't crossed a threshold,
        returns False to prevent redundant credit/token consumption.
        """
        if force_eval:
            return True, "FORCE_EVALUATION"

        # If budget status is in HARD_BLOCK or THROTTLE, apply stricter delta gating
        required_delta = self.min_market_price_delta
        if self._budget_status == "THROTTLE":
            required_delta *= 2.0  # Require $2.00 price move when throttled
        elif self._budget_status == "HARD_BLOCK":
            return False, "HARD_BLOCK_CIRCUIT_BREAKER_ACTIVE"

        if ticker not in self._last_market_evals:
            self._last_market_evals[ticker] = {
                "spot_price": spot_price,
                "target_strike": target_strike,
                "time_to_expiry_s": time_to_expiry_s,
                "last_eval_mono": time.monotonic(),
            }
            return True, "INITIAL_MARKET_EVALUATION"

        last = self._last_market_evals[ticker]
        price_diff = abs(spot_price - last["spot_price"])
        expiry_diff = abs(last["time_to_expiry_s"] - time_to_expiry_s)
        time_elapsed = time.monotonic() - last["last_eval_mono"]

        # Trigger conditions for fresh evaluation:
        # 1. Price moved beyond delta threshold ($1.00)
        # 2. Market entering final 2 minutes before expiry (gamma regime)
        # 3. More than 45 seconds elapsed since last evaluation
        if price_diff >= required_delta:
            reason = f"PRICE_DELTA_EXCEEDED (Spot moved ${price_diff:.2f} >= ${required_delta:.2f})"
            should_eval = True
        elif time_to_expiry_s <= 120.0 and last["time_to_expiry_s"] > 120.0:
            reason = "EXPIRY_GAMMA_WINDOW_ENTRY (<= 120s remaining)"
            should_eval = True
        elif time_elapsed >= 45.0:
            reason = f"TIME_THROTTLE_ELAPSED ({time_elapsed:.1f}s >= 45s)"
            should_eval = True
        else:
            reason = f"NEGLIGIBLE_MARKET_DELTA (Price move ${price_diff:.2f} < ${required_delta:.2f}, elapsed {time_elapsed:.1f}s)"
            should_eval = False

        if should_eval:
            self._last_market_evals[ticker] = {
                "spot_price": spot_price,
                "target_strike": target_strike,
                "time_to_expiry_s": time_to_expiry_s,
                "last_eval_mono": time.monotonic(),
            }

        return should_eval, reason

    # -------------------------------------------------------------------------
    # 3. Token & Gemini Credit Accounting & Budget Circuit Breaker
    # -------------------------------------------------------------------------

    def record_usage(
        self,
        agent_id: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        is_cached: bool = False,
    ) -> Dict[str, Any]:
        """Record token consumption, compute credit cost, and update sliding-window velocity."""
        pricing = MODEL_REGISTRY.get(model_id, MODEL_REGISTRY["gemini-2.5-flash"])
        total_tokens = prompt_tokens + completion_tokens

        # Compute cost and Gemini credit points
        cost = (
            (prompt_tokens / 1000.0) * pricing.prompt_token_cost_per_1k
            + (completion_tokens / 1000.0) * pricing.completion_token_cost_per_1k
        )
        credits_used = (total_tokens / 1000.0) * pricing.credits_per_1k_tokens

        now_mono = time.monotonic()

        if is_cached:
            self.metrics.total_cached_requests += 1
            self.metrics.tokens_saved += total_tokens
            self.metrics.credits_saved += credits_used
            self.metrics.cost_saved_dollars += cost
        else:
            self.metrics.total_uncached_requests += 1
            self.metrics.total_prompt_tokens += prompt_tokens
            self.metrics.total_completion_tokens += completion_tokens
            self.metrics.total_tokens += total_tokens
            self.metrics.total_credits_consumed += credits_used
            self.metrics.total_cost_dollars += cost

            # Append to sliding window for TPM / RPM calculation
            self._sliding_window.append((now_mono, total_tokens, credits_used))

            # Model breakdown
            if model_id not in self.usage_by_model:
                self.usage_by_model[model_id] = {"tokens": 0, "credits": 0.0, "cost": 0.0, "calls": 0}
            m_stat = self.usage_by_model[model_id]
            m_stat["tokens"] += total_tokens
            m_stat["credits"] += credits_used
            m_stat["cost"] += cost
            m_stat["calls"] += 1

            # Agent breakdown
            if agent_id not in self.usage_by_agent:
                self.usage_by_agent[agent_id] = {"tokens": 0, "credits": 0.0, "cost": 0.0, "calls": 0}
            a_stat = self.usage_by_agent[agent_id]
            a_stat["tokens"] += total_tokens
            a_stat["credits"] += credits_used
            a_stat["cost"] += cost
            a_stat["calls"] += 1

        # Prune sliding window (keep last 60 seconds)
        self._prune_sliding_window(now_mono)

        # Update budget status
        self._evaluate_budget_circuit_breaker()

        return {
            "agent_id": agent_id,
            "model_id": model_id,
            "total_tokens": total_tokens,
            "credits_used": round(credits_used, 4),
            "cost_dollars": round(cost, 6),
            "is_cached": is_cached,
            "budget_status": self._budget_status,
        }

    def _prune_sliding_window(self, now_mono: float) -> None:
        """Prune requests older than 60 seconds from the sliding window velocity tracker."""
        cutoff = now_mono - 60.0
        self._sliding_window = [item for item in self._sliding_window if item[0] >= cutoff]

        self.metrics.requests_last_minute = len(self._sliding_window)
        self.metrics.tokens_last_minute = sum(item[1] for item in self._sliding_window)
        self.metrics.credits_last_minute = sum(item[2] for item in self._sliding_window)

    def _evaluate_budget_circuit_breaker(self) -> None:
        """Evaluate daily and TPM quota limits to trip circuit breaker thresholds."""
        token_pct = (self.metrics.total_tokens / self.daily_token_budget) * 100.0 if self.daily_token_budget > 0 else 0.0
        credit_pct = (self.metrics.total_credits_consumed / self.daily_credit_budget) * 100.0 if self.daily_credit_budget > 0 else 0.0
        max_pct = max(token_pct, credit_pct)

        if max_pct >= 100.0 or self.metrics.tokens_last_minute >= self.tpm_limit:
            if self._budget_status != "HARD_BLOCK":
                logger.warning(
                    "🚨 [AGENT TOKEN CIRCUIT BREAKER] Hard budget limit reached (%.1f%% of daily budget / TPM %d). Blocking redundant AI calls.",
                    max_pct, self.metrics.tokens_last_minute
                )
            self._budget_status = "HARD_BLOCK"
        elif max_pct >= 95.0 or self.metrics.tokens_last_minute >= int(self.tpm_limit * 0.9):
            self._budget_status = "THROTTLE"
        elif max_pct >= 80.0 or self.metrics.tokens_last_minute >= int(self.tpm_limit * 0.8):
            self._budget_status = "WARNING"
        else:
            self._budget_status = "NORMAL"

    # -------------------------------------------------------------------------
    # 4. Smart Model Routing & Prompt Context Compression
    # -------------------------------------------------------------------------

    def route_model(
        self,
        task_type: str = "routine_scan",
        complexity_score: float = 0.5,
    ) -> str:
        """Dynamically route AI requests to the optimal model based on budget status and complexity.

        - If budget status is THROTTLE or HARD_BLOCK: routes to zero-cost local models ('onnx_microstructure_local').
        - If task is routine or complexity < 0.8: routes to lightweight 'gemini-2.5-flash'.
        - If task is high-conviction & complexity >= 0.8 and budget NORMAL: routes to 'gemini-2.5-pro'.
        """
        if self._budget_status in ("THROTTLE", "HARD_BLOCK"):
            logger.info("Token budget %s: Routing request to local zero-cost ONNX model.", self._budget_status)
            return "onnx_microstructure_local"

        if task_type == "deep_reasoning" and complexity_score >= 0.8 and self._budget_status == "NORMAL":
            return "gemini-2.5-pro"

        return "gemini-2.5-flash"

    def compress_context(self, context_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Compress context dictionary to minimize token consumption before formatting prompt.

        Strips None values, rounds floats to 3 decimal places, and caps string lengths.
        """
        compressed: Dict[str, Any] = {}
        for key, val in context_dict.items():
            if val is None:
                continue
            elif isinstance(val, float):
                compressed[key] = round(val, 3)
            elif isinstance(val, Decimal):
                compressed[key] = round(float(val), 3)
            elif isinstance(val, str) and len(val) > 200:
                compressed[key] = val[:200] + "..."
            elif isinstance(val, dict):
                compressed[key] = self.compress_context(val)
            else:
                compressed[key] = val
        return compressed

    # -------------------------------------------------------------------------
    # 5. Status & Telemetry
    # -------------------------------------------------------------------------

    def reset_usage_counters(self) -> None:
        """Reset usage metrics and clear cache."""
        self.metrics = TokenUsageMetrics()
        self._prompt_cache.clear()
        self._sliding_window.clear()
        self._last_market_evals.clear()
        self.usage_by_model.clear()
        self.usage_by_agent.clear()
        self._budget_status = "NORMAL"
        logger.info("Agent token usage counters and SHA256 cache reset.")

    def get_status_report(self) -> Dict[str, Any]:
        """Return comprehensive token usage, Gemini credits, and efficiency report."""
        now_mono = time.monotonic()
        self._prune_sliding_window(now_mono)
        self._evaluate_budget_circuit_breaker()

        total_reqs = self.metrics.total_cached_requests + self.metrics.total_uncached_requests
        cache_hit_rate_pct = (self.metrics.total_cached_requests / total_reqs * 100.0) if total_reqs > 0 else 0.0

        token_budget_used_pct = round((self.metrics.total_tokens / self.daily_token_budget * 100.0), 1) if self.daily_token_budget > 0 else 0.0
        credit_budget_used_pct = round((self.metrics.total_credits_consumed / self.daily_credit_budget * 100.0), 1) if self.daily_credit_budget > 0 else 0.0

        return {
            "budget_status": self._budget_status,
            "start_time_utc": self._start_time_utc,
            "budgets": {
                "daily_token_budget": self.daily_token_budget,
                "daily_credit_budget": self.daily_credit_budget,
                "tpm_limit": self.tpm_limit,
                "rpm_limit": self.rpm_limit,
                "token_budget_used_pct": token_budget_used_pct,
                "credit_budget_used_pct": credit_budget_used_pct,
            },
            "consumption": {
                "total_prompt_tokens": self.metrics.total_prompt_tokens,
                "total_completion_tokens": self.metrics.total_completion_tokens,
                "total_tokens": self.metrics.total_tokens,
                "total_credits_consumed": round(self.metrics.total_credits_consumed, 2),
                "total_cost_dollars": round(self.metrics.total_cost_dollars, 4),
            },
            "efficiency_and_savings": {
                "total_cached_requests": self.metrics.total_cached_requests,
                "total_uncached_requests": self.metrics.total_uncached_requests,
                "cache_hit_rate_pct": round(cache_hit_rate_pct, 1),
                "tokens_saved": self.metrics.tokens_saved,
                "credits_saved": round(self.metrics.credits_saved, 2),
                "cost_saved_dollars": round(self.metrics.cost_saved_dollars, 4),
                "active_cache_entries": len(self._prompt_cache),
            },
            "sliding_window_60s": {
                "requests_last_minute": self.metrics.requests_last_minute,
                "tokens_last_minute": self.metrics.tokens_last_minute,
                "credits_last_minute": round(self.metrics.credits_last_minute, 2),
            },
            "usage_by_model": dict(self.usage_by_model),
            "usage_by_agent": dict(self.usage_by_agent),
        }


# Singleton accessor
_token_manager_instance: Optional[AgentTokenManager] = None

def get_agent_token_manager() -> AgentTokenManager:
    """Return the global AgentTokenManager singleton."""
    global _token_manager_instance
    if _token_manager_instance is None:
        _token_manager_instance = AgentTokenManager()
    return _token_manager_instance
