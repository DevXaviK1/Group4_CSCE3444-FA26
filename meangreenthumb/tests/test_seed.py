"""Tests for the seed-demo command."""
import pytest
from flask import Flask
from werkzeug.security import check_password_hash

from app import db
from app.models import Plant, SavedPlant, Tip, User
from app.seed import ADMIN_EMAIL, DEFAULT_PASSWORD, USER_EMAIL, seed_demo


@pytest.fixture()
def seed_app():
    app = Flask("seed_test")
    app.config.update(TESTING=True, SECRET_KEY="t", SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(app)
    app.cli.add_command(seed_demo)
    with app.app_context():
        db.create_all()
        yield app


def run(app, *args):
    return app.test_cli_runner().invoke(args=["seed-demo", *args])


def test_seed_creates_admin_user_catalog_and_tips(seed_app, monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    result = run(seed_app)
    assert result.exit_code == 0, result.output
    admin = User.query.filter_by(email=ADMIN_EMAIL).first()
    user = User.query.filter_by(email=USER_EMAIL).first()
    assert admin.is_admin is True and user.is_admin is False
    assert user.notifications_enabled is True  # so the demo can show an alert
    assert check_password_hash(admin.password_hash, DEFAULT_PASSWORD)
    assert Plant.query.count() >= 5
    assert Tip.query.count() == 3
    saved = SavedPlant.query.filter_by(user_id=user.user_id).one()
    assert len(saved.care_tasks) == 5
    assert sum(1 for t in saved.care_tasks if t.completed) == 1


def test_seed_is_safe_to_run_twice(seed_app, monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    run(seed_app)
    run(seed_app)
    assert User.query.count() == 2
    assert Tip.query.count() == 3
    assert SavedPlant.query.count() == 1


def test_seed_refuses_default_password_on_render(seed_app, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    result = run(seed_app)
    assert result.exit_code != 0
    assert "Refusing" in result.output
    assert User.query.count() == 0


def test_seed_on_render_works_with_private_password(seed_app, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DEMO_PASSWORD", "a-private-value")
    result = run(seed_app)
    assert result.exit_code == 0, result.output
    admin = User.query.filter_by(email=ADMIN_EMAIL).first()
    assert check_password_hash(admin.password_hash, "a-private-value")
    assert not check_password_hash(admin.password_hash, DEFAULT_PASSWORD)


def test_reset_clears_existing_data(seed_app, monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    run(seed_app)
    db.session.add(Tip(user_id=1, zone_id=1, text="stray tip"))
    db.session.commit()
    result = run(seed_app, "--reset")
    assert result.exit_code == 0, result.output
    assert Tip.query.filter_by(text="stray tip").first() is None
    assert Tip.query.count() == 3
