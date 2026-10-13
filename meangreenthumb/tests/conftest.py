"""Shared fixtures. Builds a small Flask app (stub base.html, in-memory SQLite)
so tests don't depend on the rest of the team's routes or templates."""
from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

import app as app_pkg
from app import db
from app.models import GrowingZone, Plant, User
from app.routes.my_plants import my_plants_bp

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

    test_app.register_blueprint(my_plants_bp)

    with test_app.app_context():
        db.create_all()
        zone = GrowingZone(zone_code="8a")
        db.session.add(zone)
        db.session.flush()
        db.session.add_all(
            [
                User(user_id=1, email="a@test.com", password_hash="x", zone_id=zone.zone_id),
                User(user_id=2, email="b@test.com", password_hash="x", zone_id=zone.zone_id),
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
