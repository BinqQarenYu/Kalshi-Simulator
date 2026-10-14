"""Utility for sending alert emails about model staleness.

This wrapper re‑uses the existing ``aws_email_mailer.send_assessment_email``
function which already knows how to dispatch SMTP/SES messages based on
environment variables.  It provides a thin ``send_alert`` API that returns a
boolean indicating success.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def send_alert(
    subject: str,
    body: str,
    recipient: Optional[str] = None,
    topic: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Send an alert email with anti-burst throttling and topic deduplication.

    Args:
        subject: Email subject line.
        body: Plain‑text body of the message.
        recipient: Optional custom recipient address.
        topic: Optional topic classification for deduplication.
        force: If True, bypasses throttling.

    Returns:
        ``True`` if the email was sent successfully, ``False`` otherwise.
    """
    try:
        from kalshi_sim.aws_email_mailer import send_assessment_email
        return send_assessment_email(
            subject=subject,
            body_markdown=body,
            recipient=recipient,
            topic=topic or "system_alert",
            force=force,
        )
    except Exception as exc:  # pragma: no cover – defensive fallback
        logger.error("[email_alert] Failed to send alert email: %s", exc)
        return False
