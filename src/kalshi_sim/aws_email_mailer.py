"""aws_email_mailer.py — Autonomous Email Dispatcher for Quant Council Assessments.

Dispatches assessment summaries and forensic reports directly to benjohncarino@gmail.com
whenever a 6-trade assessment or significant quant event is completed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aws_email_mailer")


def send_assessment_email(
    subject: str,
    body_markdown: str,
    recipient: Optional[str] = None
) -> bool:
    """Send an assessment report email using SMTP SSL."""
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

        # Simple HTML styling
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px;">
            <div style="max-width: 650px; margin: 0 auto; background: #1e293b; padding: 24px; border-radius: 8px; border: 1px solid #334155;">
                <h2 style="color: #38bdf8; border-bottom: 2px solid #334155; padding-bottom: 8px;">{subject}</h2>
                <pre style="white-space: pre-wrap; font-family: monospace; font-size: 13px; color: #e2e8f0; line-height: 1.5;">{body_markdown}</pre>
                <hr style="border: 0; border-top: 1px solid #334155; margin-top: 20px;">
                <p style="font-size: 11px; color: #94a3b8;">Kalshi 24/7 Autonomous Appliance • AWS EC2 Linux Microstructure Guard</p>
            </div>
        </body>
        </html>
        """
        part_html = MIMEText(html_content, "html")
        msg.attach(part_html)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(sender, password)
            server.send_message(msg)

        logger.info(f"[MAILER] Assessment email successfully sent to {target} (Subject: {subject})")
        return True
    except Exception as exc:
        logger.error(f"[MAILER] Failed to dispatch assessment email: {exc}")
        return False


async def async_send_assessment_email(subject: str, body_markdown: str, recipient: Optional[str] = None) -> bool:
    """Asynchronous wrapper for email dispatch."""
    return await asyncio.to_thread(send_assessment_email, subject, body_markdown, recipient)
