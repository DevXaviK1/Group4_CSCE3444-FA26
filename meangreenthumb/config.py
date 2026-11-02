import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "meangreenthumb.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # Set to False in tests so the background scheduler doesn't start
    # (APScheduler + an in-memory test DB don't play well together).
    ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"

    # Alert emails (FR-05). Set these as environment variables; never commit them.
    # With MAIL_SERVER unset, emails are only written to the log (local development).
    MAIL_SERVER = os.environ.get("MAIL_SERVER")  # e.g. smtp.gmail.com
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")  # Gmail needs an app password
    MAIL_DEFAULT_SENDER = (
        os.environ.get("MAIL_DEFAULT_SENDER")
        or MAIL_USERNAME
        or "alerts@meangreenthumb.com"
    )
    # Used for the link in alert emails.
    APP_URL = os.environ.get("APP_URL", "https://mean-green-thumb.onrender.com")
