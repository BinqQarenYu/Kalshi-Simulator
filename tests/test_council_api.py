"""Targeted API integration tests for Council router endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.kalshi_sim.routers.council import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_get_council_roster():
    response = client.get("/api/council/roster")
    assert response.status_code == 200
    data = response.json()
    assert "councilors" in data
    assert len(data["councilors"]) == 7
    assert any(c["id"] == "nash" for c in data["councilors"])
    assert any(c["id"] == "koko" for c in data["councilors"])
    assert len(data["invariants"]) == 4


def test_post_council_deliberate_approved():
    payload = {
        "raw_prompt": "Deploy passive maker limit order with Decimal math and 1-contract micro-bankroll",
        "target_asset": "BTC",
        "max_rounds": 2,
    }
    response = client.post("/api/council/deliberate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    state = data["state"]
    assert state["consensus_verdict"] == "APPROVED"
    assert len(state["task_contract"]) == 4
    assert len(state["council_votes"]) == 6


def test_post_council_deliberate_rejected():
    payload = {
        "raw_prompt": "Use float(price) and cross spread with no lock",
        "target_asset": "BTC",
        "max_rounds": 2,
    }
    response = client.post("/api/council/deliberate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    state = data["state"]
    assert state["consensus_verdict"] == "REJECTED"
    assert len(state["flaw_registry"]) > 0
