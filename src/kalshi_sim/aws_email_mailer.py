"""aws_email_mailer.py — Autonomous Email Dispatcher for Quant Council Assessments.

Dispatches assessment summaries and forensic reports directly to benjohncarino@gmail.com
whenever a 6-trade assessment or significant quant event is completed.

Enforces strict anti-spam & anti-burst throttle rules:
1. Once per assessment: Each batch number (e.g. Batch #123) is emailed strictly once.
2. Once per topic: Recurring alerts/topics cannot be sent within topic_cooldown_seconds (default 1800s / 30m).
3. Anti-burst limit: Global rate limit prevents any two emails from sending within min_interval_seconds (default 300s / 5m).
4. Persistent registry on disk (data/sent_email_registry.json) survives daemon and server restarts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import smtplib
import threading
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aws_email_mailer")


class EmailThrottleGovernor:
    """Manages anti-burst throttling, topic-level deduplication, and single-dispatch batch locks."""

    def __init__(
        self,
        registry_path: str | Path = "data/sent_email_registry.json",
        min_interval_seconds: float = 300.0,
        topic_cooldown_seconds: float = 1800.0,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.min_interval_seconds = float(
            os.getenv("EMAIL_MIN_INTERVAL_SECONDS", str(min_interval_seconds))
        )
        self.topic_cooldown_seconds = float(
            os.getenv("EMAIL_TOPIC_COOLDOWN_SECONDS", str(topic_cooldown_seconds))
        )
        self._lock = threading.Lock()
        self._sent_batches: set[int] = set()
        self._topic_last_sent: dict[str, float] = {}
        self._last_email_sent_ts: float = 0.0
        self._load_registry()

    def _load_registry(self) -> None:
        """Load persisted registry from disk if available."""
        if not self.registry_path.exists():
            return
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            self._sent_batches = set(int(b) for b in data.get("sent_batches", []))
            self._topic_last_sent = {str(k): float(v) for k, v in data.get("topic_last_sent", {}).items()}
            self._last_email_sent_ts = float(data.get("last_email_sent_ts", 0.0))
            logger.info(
                "[MAILER GOVERNOR] Loaded registry from %s: %d batches recorded, last email ts: %.1f",
                self.registry_path,
                len(self._sent_batches),
                self._last_email_sent_ts,
            )
        except Exception as exc:
            logger.warning("[MAILER GOVERNOR] Failed to load email registry: %s. Re-initializing empty.", exc)

    def _save_registry(self) -> None:
        """Persist registry atomically to disk."""
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "sent_batches": sorted(list(self._sent_batches)),
                "topic_last_sent": self._topic_last_sent,
                "last_email_sent_ts": self._last_email_sent_ts,
                "last_updated_utc": datetime.now(timezone.utc).isoformat(),
            }
            tmp_path = self.registry_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_path.replace(self.registry_path)
        except Exception as exc:
            logger.error("[MAILER GOVERNOR] Failed to persist registry to %s: %s", self.registry_path, exc)

    def _infer_batch_and_topic(
        self, subject: str, batch_num: Optional[int], topic: Optional[str]
    ) -> tuple[Optional[int], str]:
        """Infer batch number and topic string from parameters or subject line."""
        inferred_batch = batch_num
        if inferred_batch is None:
            m = re.search(r"Batch\s*#?(\d+)", subject, re.IGNORECASE)
            if not m:
                m = re.search(r"#(\d+)", subject)
            if m:
                try:
                    inferred_batch = int(m.group(1))
                except ValueError:
                    pass

        inferred_topic = topic
        if not inferred_topic:
            if inferred_batch is not None:
                inferred_topic = f"batch_assessment_{inferred_batch}"
            elif "[ALERT]" in subject.upper():
                inferred_topic = "system_alert"
            elif "STALE" in subject.upper():
                inferred_topic = "model_stale"
            else:
                clean_subj = re.sub(r"[^a-zA-Z0-9_]+", "_", subject[:40].lower()).strip("_")
                inferred_topic = clean_subj or "general_notification"

        return inferred_batch, inferred_topic

    def should_allow_email(
        self,
        subject: str,
        batch_num: Optional[int] = None,
        topic: Optional[str] = None,
        force: bool = False,
        now: Optional[float] = None,
    ) -> tuple[bool, str]:
        """Determine whether email dispatch should be permitted or suppressed."""
        if now is None:
            now = time.time()

        batch_id, topic_key = self._infer_batch_and_topic(subject, batch_num, topic)

        with self._lock:
            # Rule 1: Once per assessment (Batch deduplication)
            if batch_id is not None and batch_id in self._sent_batches and not force:
                reason = f"[MAILER DEDUP] Assessment email for Batch #{batch_id} already sent. Suppressing duplicate."
                logger.warning(reason)
                return False, reason

            # Rule 2: Topic deduplication / cooldown
            if topic_key in self._topic_last_sent and not force:
                last_time = self._topic_last_sent[topic_key]
                elapsed = now - last_time
                if elapsed < self.topic_cooldown_seconds:
                    rem = self.topic_cooldown_seconds - elapsed
                    reason = (
                        f"[MAILER TOPIC THROTTLE] Topic '{topic_key}' throttled. "
                        f"Last sent {elapsed:.1f}s ago ({rem:.0f}s cooldown remaining)."
                    )
                    logger.warning(reason)
                    return False, reason

            # Rule 3: Anti-burst global cooldown across all outgoing emails
            if self._last_email_sent_ts > 0.0 and not force:
                elapsed_global = now - self._last_email_sent_ts
                if elapsed_global < self.min_interval_seconds:
                    rem_global = self.min_interval_seconds - elapsed_global
                    reason = (
                        f"[MAILER ANTI-BURST] Suppressing burst email for topic '{topic_key}'. "
                        f"Last email sent {elapsed_global:.1f}s ago ({rem_global:.0f}s cooldown remaining)."
                    )
                    logger.warning(reason)
                    return False, reason

            return True, "ALLOWED"

    def record_email_sent(
        self,
        subject: str,
        batch_num: Optional[int] = None,
        topic: Optional[str] = None,
        now: Optional[float] = None,
    ) -> None:
        """Record successful email dispatch into state and save registry."""
        if now is None:
            now = time.time()

        batch_id, topic_key = self._infer_batch_and_topic(subject, batch_num, topic)

        with self._lock:
            self._last_email_sent_ts = now
            if topic_key:
                self._topic_last_sent[topic_key] = now
            if batch_id is not None:
                self._sent_batches.add(batch_id)
            self._save_registry()


_GLOBAL_GOVERNOR: Optional[EmailThrottleGovernor] = None
_GOVERNOR_LOCK = threading.Lock()


def get_email_throttle_governor(
    registry_path: str | Path = "data/sent_email_registry.json",
    min_interval_seconds: float = 300.0,
    topic_cooldown_seconds: float = 1800.0,
) -> EmailThrottleGovernor:
    """Return the global EmailThrottleGovernor singleton instance."""
    global _GLOBAL_GOVERNOR
    with _GOVERNOR_LOCK:
        if _GLOBAL_GOVERNOR is None:
            _GLOBAL_GOVERNOR = EmailThrottleGovernor(
                registry_path=registry_path,
                min_interval_seconds=min_interval_seconds,
                topic_cooldown_seconds=topic_cooldown_seconds,
            )
        return _GLOBAL_GOVERNOR


def reset_email_throttle_governor() -> None:
    """Reset the global singleton governor (primarily for testing)."""
    global _GLOBAL_GOVERNOR
    with _GOVERNOR_LOCK:
        _GLOBAL_GOVERNOR = None


def send_assessment_email(
    subject: str,
    body_markdown: str,
    recipient: Optional[str] = None,
    market_condition: Optional[str] = None,
    batch_num: Optional[int] = None,
    topic: Optional[str] = None,
    force: bool = False,
    governor: Optional[EmailThrottleGovernor] = None,
) -> bool:
    """Send an assessment report email using SMTP SSL with market condition badge and strict throttle rules."""
    gov = governor or get_email_throttle_governor()
    allowed, reason = gov.should_allow_email(
        subject=subject,
        batch_num=batch_num,
        topic=topic,
        force=force,
    )
    if not allowed:
        logger.info("[MAILER] Suppressed: %s", reason)
        return False

    sender = os.getenv("ALERT_EMAIL_SENDER", "benjohncarino@gmail.com")
    password = os.getenv("ALERT_EMAIL_PASSWORD")
    target = recipient or os.getenv("ALERT_EMAIL_RECIPIENT", "benjohncarino@gmail.com")

    if not password:
        logger.warning("[MAILER] ALERT_EMAIL_PASSWORD not set. Cannot send email.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Kalshi AWS Quant Sentinel <{sender}>"
        msg["To"] = target

        # Plain text
        part_text = MIMEText(body_markdown, "plain")
        msg.attach(part_text)

        # Market Condition Styling
        cond_tag = (market_condition or "CHOPPY").upper()
        if "STORM" in cond_tag:
            badge_bg = "#b45309"
            badge_border = "#f59e0b"
            badge_icon = "⚡"
        elif "BLEED" in cond_tag:
            badge_bg = "#b91c1c"
            badge_border = "#ef4444"
            badge_icon = "🛑"
        elif "HEAL" in cond_tag:
            badge_bg = "#047857"
            badge_border = "#10b981"
            badge_icon = "🌱"
        else:
            badge_bg = "#0369a1"
            badge_border = "#38bdf8"
            badge_icon = "🌊"

        # HTML styling with Market Condition Header
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px;">
            <div style="max-width: 680px; margin: 0 auto; background: #1e293b; padding: 24px; border-radius: 8px; border: 1px solid #334155;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <span style="display: inline-block; padding: 6px 14px; border-radius: 9999px; font-weight: bold; font-size: 13px; background-color: {badge_bg}; border: 1px solid {badge_border}; color: #ffffff;">
                        {badge_icon} MARKET CONDITION: {cond_tag}
                    </span>
                    <span style="font-size: 11px; color: #94a3b8;">Kalshi Autonomous Bot 1 V4 (Quolas)</span>
                </div>
                <h2 style="color: #38bdf8; border-bottom: 2px solid #334155; padding-bottom: 8px; margin-top: 0;">{subject}</h2>
                <pre style="white-space: pre-wrap; font-family: monospace; font-size: 13px; color: #e2e8f0; line-height: 1.5; background: #0b1120; padding: 16px; border-radius: 6px; border: 1px solid #1e293b;">{body_markdown}</pre>
                <hr style="border: 0; border-top: 1px solid #334155; margin-top: 20px;">
                <p style="font-size: 11px; color: #94a3b8; text-align: center;">Kalshi 24/7 Autonomous Appliance • AWS EC2 Linux Microstructure Guard • Cycle Evaluation Sentinel</p>
            </div>
        </body>
        </html>
        """
        part_html = MIMEText(html_content, "html")
        msg.attach(part_html)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(sender, password)
            server.send_message(msg)

        # Record successfully sent email
        gov.record_email_sent(
            subject=subject,
            batch_num=batch_num,
            topic=topic,
        )

        logger.info(f"[MAILER] Assessment email successfully sent to {target} (Subject: {subject})")
        return True
    except Exception as exc:
        logger.error(f"[MAILER] Failed to dispatch assessment email: {exc}")
        return False


async def async_send_assessment_email(
    subject: str,
    body_markdown: str,
    recipient: Optional[str] = None,
    market_condition: Optional[str] = None,
    batch_num: Optional[int] = None,
    topic: Optional[str] = None,
    force: bool = False,
    governor: Optional[EmailThrottleGovernor] = None,
) -> bool:
    """Asynchronous wrapper for email dispatch with governor throttling."""
    return await asyncio.to_thread(
        send_assessment_email,
        subject,
        body_markdown,
        recipient,
        market_condition,
        batch_num,
        topic,
        force,
        governor,
    )
