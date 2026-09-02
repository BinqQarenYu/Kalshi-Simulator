"""Tests for AgentTokenManager — Token & Gemini credit accounting, budget circuit breakers,
SHA256 redundancy caching, adaptive market delta gating, and smart model routing.
"""

import time
import pytest

from kalshi_sim.agent_token_manager import AgentTokenManager, MODEL_REGISTRY


def test_token_and_credit_accounting() -> None:
    mgr = AgentTokenManager(daily_token_budget=1_000_000, daily_credit_budget=500.0)

    # Record usage for gemini-2.5-flash
    res = mgr.record_usage(
        agent_id="test_agent",
        model_id="gemini-2.5-flash",
        prompt_tokens=800,
        completion_tokens=200,
        is_cached=False,
    )

    assert res["agent_id"] == "test_agent"
    assert res["model_id"] == "gemini-2.5-flash"
    assert res["total_tokens"] == 1000
    # 1000 tokens = 1.0 credit for gemini-2.5-flash
    assert res["credits_used"] == 1.0
    assert res["budget_status"] == "NORMAL"

    report = mgr.get_status_report()
    assert report["consumption"]["total_tokens"] == 1000
    assert report["consumption"]["total_prompt_tokens"] == 800
    assert report["consumption"]["total_completion_tokens"] == 200
    assert report["consumption"]["total_credits_consumed"] == 1.0
    assert report["usage_by_agent"]["test_agent"]["calls"] == 1


def test_sha256_prompt_caching_and_savings() -> None:
    mgr = AgentTokenManager(cache_max_entries=10, default_cache_ttl_seconds=30.0)

    context = {
        "ticker": "KXBTC15M-T78650",
        "spot_price": 78640.5,
        "target_strike": 78650.0,
        "strategy": "3_step_domination_bot",
    }

    response_payload = {
        "recommended_side": "yes",
        "ai_prob": 0.78,
        "rationale": "High Inflow Velocity",
    }

    # 1. First lookup returns None
    cached = mgr.get_cached_response(context)
    assert cached is None

    # 2. Store response in cache
    mgr.cache_response(
        context_or_prompt=context,
        response_data=response_payload,
        estimated_tokens=300,
        model_id="gemini-2.5-flash",
        ttl_seconds=30.0,
    )

    # 3. Second lookup matches SHA256 context hash and returns cached result
    cached_hit = mgr.get_cached_response(context)
    assert cached_hit is not None
    assert cached_hit["is_cached"] is True
    assert cached_hit["data"]["recommended_side"] == "yes"
    assert cached_hit["saved_tokens"] == 300

    # Verify savings telemetry
    report = mgr.get_status_report()
    assert report["efficiency_and_savings"]["total_cached_requests"] == 1
    assert report["efficiency_and_savings"]["tokens_saved"] == 300
    assert report["efficiency_and_savings"]["credits_saved"] == 0.3
    assert report["efficiency_and_savings"]["cache_hit_rate_pct"] == 100.0


def test_adaptive_market_delta_gating() -> None:
    mgr = AgentTokenManager(min_market_price_delta=1.00)
    ticker = "KXBTC15M-T78650"

    # 1. Initial market evaluation -> True
    should, reason = mgr.should_evaluate_market_state(
        ticker=ticker,
        spot_price=78640.0,
        target_strike=78650.0,
        time_to_expiry_s=600.0,
    )
    assert should is True
    assert reason == "INITIAL_MARKET_EVALUATION"

    # 2. Negligible price move ($0.20 < $1.00 threshold) -> False (skips redundant evaluation)
    should2, reason2 = mgr.should_evaluate_market_state(
        ticker=ticker,
        spot_price=78640.20,
        target_strike=78650.0,
        time_to_expiry_s=595.0,
    )
    assert should2 is False
    assert "NEGLIGIBLE_MARKET_DELTA" in reason2

    # 3. Significant price move ($1.50 >= $1.00 threshold) -> True
    should3, reason3 = mgr.should_evaluate_market_state(
        ticker=ticker,
        spot_price=78641.70,
        target_strike=78650.0,
        time_to_expiry_s=585.0,
    )
    assert should3 is True
    assert "PRICE_DELTA_EXCEEDED" in reason3


def test_budget_circuit_breaker_thresholds() -> None:
    # Set small daily budget of 1,000 tokens for testing
    mgr = AgentTokenManager(daily_token_budget=1_000, daily_credit_budget=10.0, tpm_limit=5_000)
    assert mgr._budget_status == "NORMAL"

    # 80% usage -> WARNING
    mgr.record_usage("ag1", "gemini-2.5-flash", prompt_tokens=600, completion_tokens=200)
    assert mgr._budget_status == "WARNING"

    # 95% usage -> THROTTLE
    mgr.record_usage("ag1", "gemini-2.5-flash", prompt_tokens=100, completion_tokens=50)
    assert mgr._budget_status == "THROTTLE"

    # >= 100% usage -> HARD_BLOCK
    mgr.record_usage("ag1", "gemini-2.5-flash", prompt_tokens=50, completion_tokens=10)
    assert mgr._budget_status == "HARD_BLOCK"


def test_smart_model_routing() -> None:
    mgr = AgentTokenManager()

    # Routine task -> gemini-2.5-flash
    model = mgr.route_model(task_type="routine_scan", complexity_score=0.3)
    assert model == "gemini-2.5-flash"

    # Deep reasoning with high complexity -> gemini-2.5-pro
    model_pro = mgr.route_model(task_type="deep_reasoning", complexity_score=0.9)
    assert model_pro == "gemini-2.5-pro"

    # When budget is in THROTTLE or HARD_BLOCK -> routes to zero-cost local ONNX
    mgr._budget_status = "THROTTLE"
    model_throttled = mgr.route_model(task_type="deep_reasoning", complexity_score=0.9)
    assert model_throttled == "onnx_microstructure_local"


def test_context_compression() -> None:
    mgr = AgentTokenManager()
    raw = {
        "ticker": "KXBTC15M-T78650",
        "null_val": None,
        "exact_float": 78640.1234567,
        "long_text": "A" * 300,
        "nested": {"nested_float": 0.987654},
    }

    compressed = mgr.compress_context(raw)
    assert "null_val" not in compressed
    assert compressed["exact_float"] == 78640.123
    assert len(compressed["long_text"]) < 210
    assert compressed["nested"]["nested_float"] == 0.988


def test_reset_usage_counters() -> None:
    mgr = AgentTokenManager()
    mgr.record_usage("a1", "gemini-2.5-flash", 500, 100)
    assert mgr.metrics.total_tokens == 600

    mgr.reset_usage_counters()
    report = mgr.get_status_report()
    assert report["consumption"]["total_tokens"] == 0
    assert report["budget_status"] == "NORMAL"
    assert report["efficiency_and_savings"]["active_cache_entries"] == 0


def test_agent_management_api_endpoints() -> None:
    from fastapi.testclient import TestClient
    from kalshi_sim.server import app

    with TestClient(app) as client:
        # 1. GET /api/agent-management/status
        res = client.get("/api/agent-management/status")
        assert res.status_code == 200
        data = res.json()
        assert "budget_status" in data
        assert "consumption" in data
        assert "efficiency_and_savings" in data

        # 2. POST /api/agent-management/config
        config_res = client.post(
            "/api/agent-management/config",
            json={
                "daily_token_budget": 500_000,
                "daily_credit_budget": 250.0,
                "tpm_limit": 30_000,
                "min_market_price_delta": 2.0,
            },
        )
        assert config_res.status_code == 200
        config_data = config_res.json()
        assert config_data["success"] is True
        assert config_data["status"]["budgets"]["daily_token_budget"] == 500_000
        assert config_data["status"]["budgets"]["daily_credit_budget"] == 250.0

        # 3. POST /api/agent-management/reset-usage
        reset_res = client.post("/api/agent-management/reset-usage")
        assert reset_res.status_code == 200
        reset_data = reset_res.json()
        assert reset_data["success"] is True
        assert reset_data["status"]["consumption"]["total_tokens"] == 0
