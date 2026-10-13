"""Utility for sending alert emails about model staleness.

This wrapper re‑uses the existing ``aws_email_mailer.send_assessment_email``
function which already knows how to dispatch SMTP/SES messages based on
environment variables.  It provides a thin ``send_alert`` API that returns a
boolean indicating success.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def send_alert(subject: str, body: str, recipient: Optional[str] = None) -> bool:
    """Send an alert email.

    Args:
        subject: Email subject line.
        body: Plain‑text body of the message.
        recipient: Optional custom recipient address; falls back to the
            ``ALERT_EMAIL_RECIPIENT`` environment variable used by the
            underlying mailer.

    Returns:
        ``True`` if the email was sent successfully, ``False`` otherwise.
    """
    try:
        # Re‑use the existing assessment mailer – it handles SMTP/SES config.
        from .aws_email_mailer import send_assessment_email
        return send_assessment_email(subject, body, recipient)
    except Exception as exc:  # pragma: no cover – defensive fallback
        logger.error("[email_alert] Failed to send alert email: %s", exc)
        return False
