"""tests/test_email_mailer_throttle.py — Unit Tests for Email Throttle & Anti-Burst Governor.

Tests compliance with:
- Rule 1: Once per assessment (Batch deduplication)
- Rule 2: Once per topic (Topic cooldown throttling)
- Rule 3: Anti-burst rate limiting (min interval between any emails)
- Rule 4: Persistent state across restarts (disk registry load/save)
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from kalshi_sim.aws_email_mailer import (
    EmailThrottleGovernor,
    send_assessment_email,
    reset_email_throttle_governor,
)


@pytest.fixture(autouse=True)
def clean_governor():
    reset_email_throttle_governor()
    yield
    reset_email_throttle_governor()


def test_once_per_assessment_batch_dedup(tmp_path):
    reg_file = tmp_path / "sent_email_registry.json"
    gov = EmailThrottleGovernor(
        registry_path=reg_file,
        min_interval_seconds=300.0,
        topic_cooldown_seconds=1800.0,
    )

    t0 = 1000.0
    # 1. First send of Batch #123 should be allowed
    allowed, reason = gov.should_allow_email("Batch #123 Report", batch_num=123, now=t0)
    assert allowed is True
    assert reason == "ALLOWED"

    # Record it
    gov.record_email_sent("Batch #123 Report", batch_num=123, now=t0)

    # 2. Second send of Batch #123 should be suppressed even much later
    allowed_again, reason_again = gov.should_allow_email("Batch #123 Report", batch_num=123, now=t0 + 10000.0)
    assert allowed_again is False
    assert "already sent" in reason_again.lower()
    assert "123" in reason_again


def test_anti_burst_global_cooldown(tmp_path):
    reg_file = tmp_path / "sent_email_registry.json"
    gov = EmailThrottleGovernor(
        registry_path=reg_file,
        min_interval_seconds=300.0,
        topic_cooldown_seconds=1800.0,
    )

    t0 = 2000.0
    # Dispatch email 1
    allowed, _ = gov.should_allow_email("Batch #100", batch_num=100, now=t0)
    assert allowed is True
    gov.record_email_sent("Batch #100", batch_num=100, now=t0)

    # Dispatch email 2 (different topic) only 60s later (< 300s) -> should be suppressed
    t1 = t0 + 60.0
    allowed2, reason2 = gov.should_allow_email("[ALERT] Risk Limit Reached", topic="risk_alert", now=t1)
    assert allowed2 is False
    assert "anti-burst" in reason2.lower()

    # Dispatch email 2 after 301s (> 300s) -> should be allowed
    t2 = t0 + 301.0
    allowed3, reason3 = gov.should_allow_email("[ALERT] Risk Limit Reached", topic="risk_alert", now=t2)
    assert allowed3 is True
    assert reason3 == "ALLOWED"


def test_topic_cooldown(tmp_path):
    reg_file = tmp_path / "sent_email_registry.json"
    gov = EmailThrottleGovernor(
        registry_path=reg_file,
        min_interval_seconds=60.0,
        topic_cooldown_seconds=1800.0,
    )

    t0 = 5000.0
    # Send topic "model_stale"
    allowed, _ = gov.should_allow_email("[ALERT] ONNX model stale", topic="model_stale", now=t0)
    assert allowed is True
    gov.record_email_sent("[ALERT] ONNX model stale", topic="model_stale", now=t0)

    # 100s later (passes anti-burst of 60s, but fails topic cooldown of 1800s)
    t1 = t0 + 100.0
    allowed_subsequent, reason_sub = gov.should_allow_email("[ALERT] ONNX model stale", topic="model_stale", now=t1)
    assert allowed_subsequent is False
    assert "topic 'model_stale' throttled" in reason_sub.lower()

    # 1850s later (> 1800s) -> allowed
    t2 = t0 + 1850.0
    allowed_later, reason_later = gov.should_allow_email("[ALERT] ONNX model stale", topic="model_stale", now=t2)
    assert allowed_later is True
    assert reason_later == "ALLOWED"


def test_registry_disk_persistence(tmp_path):
    reg_file = tmp_path / "sent_email_registry.json"
    gov1 = EmailThrottleGovernor(
        registry_path=reg_file,
        min_interval_seconds=300.0,
        topic_cooldown_seconds=1800.0,
    )

    t0 = 10000.0
    gov1.record_email_sent("Batch #200", batch_num=200, topic="batch_assessment_200", now=t0)

    # Verify file written to disk
    assert reg_file.exists()
    disk_data = json.loads(reg_file.read_text(encoding="utf-8"))
    assert 200 in disk_data["sent_batches"]
    assert disk_data["last_email_sent_ts"] == t0

    # Instantiate brand new governor pointing to same disk file (simulating server/daemon restart)
    gov2 = EmailThrottleGovernor(
        registry_path=reg_file,
        min_interval_seconds=300.0,
        topic_cooldown_seconds=1800.0,
    )

    # Should immediately recognize Batch #200 as already sent
    allowed, reason = gov2.should_allow_email("Batch #200", batch_num=200, now=t0 + 50000.0)
    assert allowed is False
    assert "already sent" in reason.lower()


def test_force_flag_bypasses_anti_burst(tmp_path):
    reg_file = tmp_path / "sent_email_registry.json"
    gov = EmailThrottleGovernor(
        registry_path=reg_file,
        min_interval_seconds=300.0,
        topic_cooldown_seconds=1800.0,
    )

    t0 = 1000.0
    gov.record_email_sent("Normal Alert", topic="general_notification", now=t0)

    # Immediate dispatch 10s later normally blocked
    allowed, _ = gov.should_allow_email("Emergency Notice", topic="emergency", now=t0 + 10.0, force=False)
    assert allowed is False

    # With force=True, permitted
    allowed_force, _ = gov.should_allow_email("Emergency Notice", topic="emergency", now=t0 + 10.0, force=True)
    assert allowed_force is True


def test_send_assessment_email_end_to_end_dedup(tmp_path, monkeypatch):
    reg_file = tmp_path / "sent_email_registry.json"
    gov = EmailThrottleGovernor(registry_path=reg_file, min_interval_seconds=300.0)

    monkeypatch.setenv("ALERT_EMAIL_PASSWORD", "mock_password")
    monkeypatch.setenv("ALERT_EMAIL_SENDER", "test@example.com")
    monkeypatch.setenv("ALERT_EMAIL_RECIPIENT", "test@example.com")

    mock_smtp = MagicMock()
    with patch("smtplib.SMTP_SSL", return_value=mock_smtp):
        # 1. First send Batch #125 -> Success
        success1 = send_assessment_email(
            subject="📊 [Quant Council] 6-Trade Batch Report #125 | Condition: CHOPPY",
            body_markdown="# Assessment Report 125",
            market_condition="CHOPPY",
            batch_num=125,
            governor=gov,
        )
        assert success1 is True
        assert mock_smtp.__enter__.return_value.send_message.call_count == 1

        # 2. Second send of Batch #125 -> Blocked by governor before contacting SMTP
        success2 = send_assessment_email(
            subject="📊 [Quant Council] 6-Trade Batch Report #125 | Condition: CHOPPY",
            body_markdown="# Assessment Report 125",
            market_condition="CHOPPY",
            batch_num=125,
            governor=gov,
        )
        assert success2 is False
        # Call count should still be 1 (SMTP not called!)
        assert mock_smtp.__enter__.return_value.send_message.call_count == 1
