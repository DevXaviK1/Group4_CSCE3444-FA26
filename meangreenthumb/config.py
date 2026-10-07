import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "meangreenthumb.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Set to False in tests so the background scheduler doesn't start
    # (APScheduler + an in-memory test DB don't play well together).
    ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"
