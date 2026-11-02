"""FR-05: users opt in to freeze alert emails at registration and can change it later."""
import pytest

from app import db
from app.models import User
from app.routes.auth import auth_bp
from helpers import flashes, login


@pytest.fixture()
def optin_app(flask_app):
    from app.routes.main import home, set_notifications, weather_forecast

    flask_app.register_blueprint(auth_bp)
    flask_app.add_url_rule("/", endpoint="main.home", view_func=home, methods=["GET", "POST"])
    flask_app.add_url_rule("/weather", endpoint="main.weather_forecast", view_func=weather_forecast)
    flask_app.add_url_rule(
        "/weather/notifications",
        endpoint="main.set_notifications",
        view_func=set_notifications,
        methods=["POST"],
    )
    return flask_app


@pytest.fixture()
def oclient(optin_app):
    return optin_app.test_client()


def register(client, **extra):
    data = {"email": "new@test.com", "password": "secretpassword", "zip_code": "76201", **extra}
    return client.post("/register", data=data)


def test_register_page_has_labelled_opt_in_checkbox(oclient):
    html = oclient.get("/register").get_data(as_text=True)
    assert 'name="notifications_enabled"' in html
    assert 'id="notifications_enabled"' in html
    assert 'for="notifications_enabled"' in html
    assert "checked" not in html.split('name="notifications_enabled"')[1].split(">")[0]


def test_registering_with_the_box_ticked_turns_alerts_on(oclient):
    assert register(oclient, notifications_enabled="1").status_code == 302
    assert User.query.filter_by(email="new@test.com").one().notifications_enabled is True


def test_registering_without_the_box_leaves_alerts_off(oclient):
    assert register(oclient).status_code == 302
    assert User.query.filter_by(email="new@test.com").one().notifications_enabled is False


def test_logged_in_user_can_turn_alerts_on_and_off(oclient):
    login(oclient, 1)
    resp = oclient.post("/weather/notifications", data={"enabled": "1"})
    assert resp.status_code == 302
    assert db.session.get(User, 1).notifications_enabled is True
    assert ("success", "Freeze alert emails are on.") in flashes(oclient)

    oclient.post("/weather/notifications", data={"enabled": "0"})
    assert db.session.get(User, 1).notifications_enabled is False
    assert ("success", "Freeze alert emails are off.") in flashes(oclient)


def test_toggle_changes_only_the_logged_in_user(oclient):
    login(oclient, 1)
    oclient.post("/weather/notifications", data={"enabled": "1"})
    assert db.session.get(User, 2).notifications_enabled in (False, None)


def test_missing_value_turns_alerts_off(oclient):
    login(oclient, 1)
    oclient.post("/weather/notifications", data={"enabled": "1"})
    oclient.post("/weather/notifications", data={})
    assert db.session.get(User, 1).notifications_enabled is False


def test_guest_cannot_change_the_setting(oclient):
    assert oclient.post("/weather/notifications", data={"enabled": "1"}).status_code == 401


def test_weather_page_shows_current_state_and_matching_button(oclient, monkeypatch):
    monkeypatch.setattr("app.routes.main.get_forecast", lambda zip_code: None)
    monkeypatch.setattr("app.routes.main.get_freeze_status", lambda zip_code: "none")
    with oclient.application.app_context():
        user = db.session.get(User, 1)
        user.zip_code = "76201"
        user.notifications_enabled = False
        db.session.commit()
    login(oclient, 1)

    html = oclient.get("/weather").get_data(as_text=True)
    assert "Freeze alert emails: <strong>Off</strong>" in html
    assert "Turn on" in html and 'name="enabled" value="1"' in html

    oclient.post("/weather/notifications", data={"enabled": "1"})
    html = oclient.get("/weather").get_data(as_text=True)
    assert "Freeze alert emails: <strong>On</strong>" in html
    assert "Turn off" in html and 'name="enabled" value="0"' in html
