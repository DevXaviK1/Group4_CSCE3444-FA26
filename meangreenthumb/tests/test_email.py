"""FR-05: alert email delivery, mail settings and the send-test-email command."""
import importlib

import pytest
from flask import Flask

from app.cli import send_test_email
from app.services.notifier import send_alert_email

MAIL_VARS = [
    "MAIL_SERVER", "MAIL_PORT", "MAIL_USE_TLS", "MAIL_USERNAME", "MAIL_PASSWORD",
    "MAIL_DEFAULT_SENDER", "APP_URL",
]


class FakeSMTP:
    """Stands in for smtplib.SMTP and records what the app does with it."""

    instances = []
    fail = False

    def __init__(self, server, port, timeout=None):
        if FakeSMTP.fail:
            raise OSError("connection refused")
        self.server, self.port = server, port
        self.tls = False
        self.login_args = None
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.fixture()
def smtp(monkeypatch):
    FakeSMTP.instances, FakeSMTP.fail = [], False
    monkeypatch.setattr("app.services.notifier.smtplib.SMTP", FakeSMTP)
    return FakeSMTP


@pytest.fixture()
def mail_app():
    app = Flask("mail_test")
    app.config.update(
        MAIL_SERVER="smtp.gmail.com",
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME="project@gmail.com",
        MAIL_PASSWORD="app-password",
        MAIL_DEFAULT_SENDER="project@gmail.com",
        APP_URL="https://example.onrender.com/",
    )
    app.cli.add_command(send_test_email)
    return app


def test_email_goes_through_gmail_settings_with_tls_and_login(mail_app, smtp):
    with mail_app.app_context():
        assert send_alert_email("gardener@test.com", "Freeze Warning for your area.") is True
    server = smtp.instances[0]
    assert (server.server, server.port) == ("smtp.gmail.com", 587)
    assert server.tls is True
    assert server.login_args == ("project@gmail.com", "app-password")
    assert len(server.sent) == 1


def test_email_has_recipient_sender_subject_and_a_link_to_the_app(mail_app, smtp):
    with mail_app.app_context():
        send_alert_email("gardener@test.com", "Freeze Warning for your area.")
    msg = smtp.instances[0].sent[0]
    body = msg.get_payload()[0].get_payload()
    assert msg["To"] == "gardener@test.com"
    assert msg["From"] == "project@gmail.com"
    assert msg["Subject"] == "Mean Green Thumb: Severe Weather Alert"
    assert "Freeze Warning for your area." in body
    assert "https://example.onrender.com/weather/alerts" in body  # no double slash


def test_unset_mail_server_only_logs_and_never_connects(mail_app, smtp):
    mail_app.config["MAIL_SERVER"] = None
    with mail_app.app_context():
        assert send_alert_email("gardener@test.com", "hello") is True
    assert smtp.instances == []


def test_delivery_failure_returns_false_instead_of_crashing(mail_app, smtp):
    smtp.fail = True
    with mail_app.app_context():
        assert send_alert_email("gardener@test.com", "hello") is False


def test_config_reads_mail_settings_from_the_environment(monkeypatch):
    import config

    for name in MAIL_VARS:
        monkeypatch.delenv(name, raising=False)
    try:
        importlib.reload(config)
        assert config.Config.MAIL_SERVER is None  # default: log only
        assert config.Config.MAIL_PORT == 587 and config.Config.MAIL_USE_TLS is True
        assert config.Config.MAIL_DEFAULT_SENDER == "alerts@meangreenthumb.com"

        monkeypatch.setenv("MAIL_SERVER", "smtp.gmail.com")
        monkeypatch.setenv("MAIL_PORT", "465")
        monkeypatch.setenv("MAIL_USE_TLS", "false")
        monkeypatch.setenv("MAIL_USERNAME", "project@gmail.com")
        monkeypatch.setenv("MAIL_PASSWORD", "secret")
        importlib.reload(config)
        assert config.Config.MAIL_SERVER == "smtp.gmail.com"
        assert config.Config.MAIL_PORT == 465 and config.Config.MAIL_USE_TLS is False
        assert config.Config.MAIL_PASSWORD == "secret"
        assert config.Config.MAIL_DEFAULT_SENDER == "project@gmail.com"  # falls back to the account
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def run(app, *args):
    return app.test_cli_runner().invoke(args=["send-test-email", *args])


def test_send_test_email_command_delivers_a_message(mail_app, smtp):
    result = run(mail_app, "me@test.com")
    assert result.exit_code == 0, result.output
    assert "Test email sent to me@test.com." in result.output
    assert smtp.instances[0].sent[0]["To"] == "me@test.com"


def test_send_test_email_explains_when_mail_is_not_configured(mail_app, smtp):
    mail_app.config["MAIL_SERVER"] = None
    result = run(mail_app, "me@test.com")
    assert result.exit_code != 0
    assert "MAIL_SERVER is not set" in result.output
    assert smtp.instances == []


def test_send_test_email_reports_a_failed_delivery(mail_app, smtp):
    smtp.fail = True
    result = run(mail_app, "me@test.com")
    assert result.exit_code != 0
    assert "could not be delivered" in result.output
