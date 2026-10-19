"""Tests for the ML & Bot Asset Forge and AWS EC2 Cloud Bridge endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from kalshi_sim.server import app


def test_forge_overview_includes_aws_fleet() -> None:
    with TestClient(app) as client:
        res = client.get("/api/forge/overview")
        assert res.status_code == 200
        data = res.json()
        assert "fleet_bots" in data
        assert "onnx_assets" in data
        assert "hmm_assets" in data
        assert "aws_fleet" in data
        aws_fleet = data["aws_fleet"]
        assert aws_fleet["host"]
        assert len(aws_fleet["daemons"]) == 3
        units = {d["unit"] for d in aws_fleet["daemons"]}
        assert "kalshi-bot.service" in units
        assert "kalshi-btc-bot.service" in units
        assert "kalshi-eth-bot.service" in units


def test_aws_bridge_status_and_push_models() -> None:
    with TestClient(app) as client:
        res = client.get("/api/forge/aws/status")
        assert res.status_code == 200
        status_data = res.json()
        assert status_data["port"] == 8000

        push_res = client.post(
            "/api/forge/aws/push-models",
            json={
                "target_unit": "all",
                "onnx_asset_id": "btc_gold_32d",
                "hmm_asset_id": "hmm_btc_3state",
            },
        )
        assert push_res.status_code == 200
        push_json = push_res.json()
        assert push_json["status"] == "success"
        assert "systemctl restart kalshi-bot kalshi-btc-bot kalshi-eth-bot" in push_json["runbook_command"]


def test_aws_heartbeat_webhook() -> None:
    with TestClient(app) as client:
        hb_res = client.post(
            "/api/forge/aws/heartbeat",
            json={
                "host": "13.63.158.94",
                "unit": "kalshi-btc-bot.service",
                "status": "ACTIVE",
                "live_balance_dollars": "26.40",
                "active_positions_count": 1,
                "batch_trades_completed": 5,
            },
        )
        assert hb_res.status_code == 200
        assert hb_res.json()["status"] == "success"
