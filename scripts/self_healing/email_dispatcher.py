"""
email_dispatcher.py — Google SMTP Email Dispatcher for Sentinel Alerts
Dispatches clean, formatted HTML & Text alerts when fatal flaws are isolated.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)


def send_sentinel_email_alert(
    file_path: str,
    line_no: int,
    category: str,
    explanation: str,
    proposed_fix: str,
    is_fatal: bool = True,
    agent_role: str = "Lead Deer (Backend Self-Healer)",
) -> bool:
    """
    Sends an instant email notification via Google SMTP (Port 587 TLS).
    """
    sender = os.getenv("ALERT_EMAIL_SENDER")
    password = os.getenv("ALERT_EMAIL_PASSWORD")
    recipient = os.getenv("ALERT_EMAIL_RECIPIENT")

    if not sender or not password or not recipient:
        print("[!] Email credentials missing in .env. Skipping dispatch.")
        return False

    status_prefix = "🚨 [FATAL FLAW ISOLATED]" if is_fatal else "🎨 [UI/UX ERGONOMIC POLISH]" if "Architect" in agent_role else "⚠️ [SUSPECT CODE FLAGGED]"
    subject = f"{status_prefix} {Path(file_path).name}:{line_no} [{agent_role.split(' ')[0]}]"

    # Strip whitespace from app password just in case
    clean_password = password.replace(" ", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Kalshi Sentinel <{sender}>"
    msg["To"] = recipient

    plain_text = f"""
{status_prefix}
Target: {file_path}:{line_no}
Category: {category}

Lead Deer Diagnosis:
{explanation}

Proposed Surgical Cure:
{proposed_fix}

Circuit Breaker Status: Live Sanctuary Mutex Active (Port 8000 Flat)
Action: Autonomous ASVL verification gate commencing in 60 seconds...
"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px;">
        <div style="max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 12px; border: 1px solid #334155; padding: 24px;">
            <div style="display: flex; align-items: center; margin-bottom: 16px;">
                <span style="font-size: 24px; margin-right: 8px;">🚨</span>
                <h2 style="margin: 0; color: #f43f5e; font-size: 18px; text-transform: uppercase; letter-spacing: 0.05em;">
                    Fatal Flaw Isolated — Pending Cure
                </h2>
            </div>
            
            <div style="background: #0f172a; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; font-family: monospace; font-size: 13px;">
                <p style="margin: 4px 0;"><span style="color: #94a3b8;">Target Module:</span> <b style="color: #38bdf8;">{file_path}:{line_no}</b></p>
                <p style="margin: 4px 0;"><span style="color: #94a3b8;">Category:</span> <b style="color: #fbbf24;">{category}</b></p>
            </div>

            <div style="margin-bottom: 16px;">
                <h3 style="font-size: 14px; color: #cbd5e1; margin-bottom: 6px;">{agent_role} Diagnosis:</h3>
                <p style="margin: 0; color: #e2e8f0; font-size: 14px; line-height: 1.5; background: #182234; padding: 12px; border-left: 4px solid #f43f5e; border-radius: 4px;">
                    {explanation}
                </p>
            </div>

            <div style="margin-bottom: 20px;">
                <h3 style="font-size: 14px; color: #cbd5e1; margin-bottom: 6px;">Proposed Surgical Cure (Codeflow):</h3>
                <pre style="background: #020617; color: #4ade80; padding: 14px; border-radius: 6px; font-size: 12px; overflow-x: auto; border: 1px solid #1e293b;">{proposed_fix}</pre>
            </div>

            <div style="border-top: 1px solid #334155; padding-top: 12px; font-size: 12px; color: #94a3b8;">
                <p style="margin: 2px 0;">🛡️ <b>Live Sanctuary:</b> Active on Port 8000 (Protected from CPU & trading interference)</p>
                <p style="margin: 2px 0;">⏱️ <b>ASVL Verification:</b> Commencing deterministic Pytest run in 60 seconds.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10.0) as server:
            server.starttls()
            server.login(sender, clean_password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"[+] Direct email alert sent successfully to {recipient}")
        return True
    except Exception as exc:
        print(f"[-] Failed to send email alert via Google SMTP: {exc}")
        return False


if __name__ == "__main__":
    print("[*] Testing Google SMTP Email Dispatcher...")
    send_sentinel_email_alert(
        file_path="src/kalshi_sim/agent_guardrails.py",
        line_no=297,
        category="IEEE_754_FLOAT_CAST_LEAK",
        explanation="Naked float(est_price) risks sub-cent IEEE-754 precision drift, triggering HTTP 400 rejection during order execution.",
        proposed_fix='- return False, msg, 0, {"price": float(est_price)}\n+ return False, msg, 0, {"price": str(est_price.quantize(Decimal("0.01")))}',
        is_fatal=True
    )
