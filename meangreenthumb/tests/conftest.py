"""Shared fixtures. Builds a small Flask app (stub base.html, in-memory SQLite)
so tests don't depend on the rest of the team's routes or templates."""
from pathlib import Path

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

import app as app_pkg
from app import db
from app.models import GrowingZone, Plant, User
from app.routes.care_tasks import care_tasks_bp
from app.routes.my_plants import my_plants_bp
from app.routes.tips import tips_bp

TEMPLATES = Path(app_pkg.__file__).parent / "templates"


@pytest.fixture()
def flask_app():
    test_app = Flask("mean_green_thumb_test")
    test_app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI="sqlite://",
    )
    test_app.jinja_loader = ChoiceLoader(
        [
            DictLoader({"base.html": "{% block content %}{% endblock %}"}),
            FileSystemLoader(str(TEMPLATES)),
        ]
    )
    db.init_app(test_app)

    login_manager = LoginManager(test_app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Stand-in for Xavier's /calendar route so my_plants.html can build its link.
    stub_main = Blueprint("main", "stub_main")
    stub_main.add_url_rule("/calendar", "planting_calendar", lambda: "")
    test_app.register_blueprint(stub_main)

    test_app.register_blueprint(my_plants_bp)
    test_app.register_blueprint(care_tasks_bp)
    test_app.register_blueprint(tips_bp)

    with test_app.app_context():
        db.create_all()
        zone = GrowingZone(zone_code="8a")
        other_zone = GrowingZone(zone_code="9b")
        db.session.add_all([zone, other_zone])
        db.session.flush()
        db.session.add_all(
            [
                User(user_id=1, email="a@test.com", password_hash="x", zone_id=zone.zone_id),
                User(user_id=2, email="b@test.com", password_hash="x", zone_id=zone.zone_id),
                User(user_id=3, email="c@test.com", password_hash="x"),  # no zone set
                User(user_id=4, email="d@test.com", password_hash="x", zone_id=other_zone.zone_id),
                Plant(plant_id=1, name="Tomato"),
                Plant(plant_id=2, name="Basil"),
            ]
        )
        db.session.commit()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()
