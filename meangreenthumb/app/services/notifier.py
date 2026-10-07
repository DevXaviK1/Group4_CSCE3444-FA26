"""
Outbound email for weather alerts.

TODO (whoever picks up real delivery): replace the print() below with an
actual email send (Flask-Mail, SendGrid, SES, etc.). Keep the function
signature the same so the scheduler doesn't need to change.
"""


def send_alert_email(to_email: str, message: str) -> None:
    # Stub: log instead of sending, so the scheduler is fully testable
    # and demoable before real email credentials exist.
    print(f"[EMAIL STUB] To: {to_email} | {message}")
