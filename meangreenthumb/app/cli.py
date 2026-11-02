"""Command-line helpers.

    flask --app run send-test-email you@example.com

Sends one test message through the same code the freeze alerts use, so the mail
account can be checked before a demo without waiting for real freezing weather.
"""
import click
from flask import current_app
from flask.cli import with_appcontext

from app.services.notifier import send_alert_email


@click.command("send-test-email")
@click.argument("to_email")
@with_appcontext
def send_test_email(to_email):
    """Send a test alert email to TO_EMAIL."""
    if not current_app.config.get("MAIL_SERVER"):
        raise click.ClickException(
            "MAIL_SERVER is not set, so emails are only written to the log. "
            "Set the MAIL_* environment variables first."
        )
    ok = send_alert_email(
        to_email,
        "This is a test message from Mean Green Thumb. If you can read this, "
        "freeze alert emails are working.",
    )
    if not ok:
        raise click.ClickException("The email could not be delivered. See the error logged above.")
    click.echo(f"Test email sent to {to_email}.")
