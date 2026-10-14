"""Outbound email service (Architecture Diagram: Outbound Email Service)."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app

logger = logging.getLogger(__name__)


def send_alert_email(to_email: str, message_body: str) -> bool:
    """Send severe freeze/frost warning email to a registered user."""
    # Read SMTP config from Flask app config, falling back gracefully
    smtp_server = current_app.config.get("MAIL_SERVER")
    smtp_port = current_app.config.get("MAIL_PORT", 587)
    smtp_user = current_app.config.get("MAIL_USERNAME")
    smtp_password = current_app.config.get("MAIL_PASSWORD")
    sender_email = current_app.config.get("MAIL_DEFAULT_SENDER", "alerts@meangreenthumb.com")

    # If SMTP is not configured (e.g., local development), log and return success
    if not smtp_server:
        logger.info("[MOCK EMAIL] To: %s | Message: %s", to_email, message_body)
        return True

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = "Mean Green Thumb: Severe Weather Alert"
    msg.attach(MIMEText(message_body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            if current_app.config.get("MAIL_USE_TLS", True):
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:
        logger.error("Failed to deliver alert email to %s: %s", to_email, exc)
        return False