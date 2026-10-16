"""Automated tests for Sudip's features:
- F-04: Zip Code to Growing Zone Lookup (FR-01 / UC-01)
- F-05: Plant Suggestion List (FR-02 / UC-02)
- F-06: User Registration, Log In, and Session Timeout (FR-03 / UC-03)
- F-07: Plant Catalog Management — Admin (FR-11 / UC-11)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import GrowingZone, Plant, SavedPlant, User
from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.plants import plants_bp
from app.services.zone_lookup import lookup_zone_code
from helpers import flashes, login


@pytest.fixture()
def full_app(flask_app):
    """Extend the shared test app with auth, plants, admin, and main blueprints."""
    if "auth" not in flask_app.blueprints:
        flask_app.register_blueprint(auth_bp)
    if "plants" not in flask_app.blueprints:
        flask_app.register_blueprint(plants_bp)
    if "admin" not in flask_app.blueprints:
        flask_app.register_blueprint(admin_bp)

    from app.routes.main import home as home_view, weather_forecast as weather_view
    flask_app.view_functions["main.home"] = home_view
    flask_app.add_url_rule("/", endpoint="main.home", view_func=home_view, methods=["GET", "POST"])
    flask_app.add_url_rule("/weather", endpoint="main.weather_forecast", view_func=weather_view, methods=["GET"])

    with flask_app.app_context():
        zone_8a = GrowingZone.query.filter_by(zone_code="8a").one()
        zone_9b = GrowingZone.query.filter_by(zone_code="9b").one()

        tomato = db.session.get(Plant, 1)
        tomato.description = "Warm-season fruit"
        tomato.recommended_planting_time = "March - May, August - September"
        tomato.zones = [zone_8a, zone_9b]

        basil = db.session.get(Plant, 2)
        basil.description = "Aromatic culinary herb"
        basil.recommended_planting_time = "April - June"
        basil.zones = [zone_8a]

        spinach = Plant(
            plant_id=3,
            name="Spinach",
            description="Cool-season leafy green",
            recommended_planting_time="October - November",
        )
        spinach.zones = [zone_8a]

        admin_user = User(
            user_id=10,
            email="admin@test.com",
            password_hash=generate_password_hash("adminpass"),
            zip_code="76201",
            zone_id=zone_8a.zone_id,
            is_admin=True,
        )
        db.session.add_all([spinach, admin_user])
        db.session.commit()

    return flask_app


@pytest.fixture()
def full_client(full_app):
    return full_app.test_client()


# ==============================================================================
# F-04 / FR-01 / UC-01: Zip Code to Growing Zone Lookup (9 tests)
# ==============================================================================

def test_lookup_zone_valid_known_zip():
    assert lookup_zone_code("76201") == "8a"
    assert lookup_zone_code("90210") == "10b"
    assert lookup_zone_code("10001") == "7b"


@pytest.mark.parametrize("bad_zip", ["", "123", "123456", "abcde", "7620a", None])
def test_lookup_zone_rejects_invalid_format(bad_zip):
    assert lookup_zone_code(bad_zip) is None


def test_lookup_zone_unmapped_reserved_zip_returns_none():
    assert lookup_zone_code("00000") is None
    assert lookup_zone_code("99999") is None


def test_lookup_zone_queries_usda_api_when_not_in_local_cache():
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"zone": "7a"}
    with patch("app.services.zone_lookup.requests.get", return_value=mock_resp) as m_get:
        assert lookup_zone_code("22030") == "7a"
        m_get.assert_called_once()


def test_lookup_zone_handles_usda_api_failure_gracefully():
    import requests
    with patch("app.services.zone_lookup.requests.get", side_effect=requests.RequestException("down")):
        assert lookup_zone_code("43210") is None


def test_home_get_renders_zip_form(full_client):
    resp = full_client.get("/")
    assert resp.status_code == 200
    assert "Enter your zip code" in resp.get_data(as_text=True)


def test_home_post_valid_zip_shows_zone_and_suggestions_link(full_client):
    resp = full_client.post("/", data={"zip_code": "76201"})
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "8a" in html
    assert "/suggestions?zone=8a" in html


def test_home_post_invalid_zip_flashes_error(full_client):
    resp = full_client.post("/", data={"zip_code": "abc"})
    assert resp.status_code == 200
    assert any("valid 5-digit zip code" in msg for _, msg in flashes(full_client))


def test_home_post_saves_zip_and_zone_to_logged_in_user_profile(full_client):
    login(full_client, 3)  # User 3 has no zip_code or zone_id initially
    full_client.post("/", data={"zip_code": "90210"})
    user3 = db.session.get(User, 3)
    assert user3.zip_code == "90210"
    assert user3.growing_zone.zone_code == "10b"


# ==============================================================================
# F-05 / FR-02 / UC-02: Plant Suggestion List (9 tests)
# ==============================================================================

def test_suggestions_redirects_home_when_no_zone_set(full_client):
    resp = full_client.get("/suggestions")
    assert resp.status_code == 302
    assert any("look up your growing zone" in msg for _, msg in flashes(full_client))


def test_suggestions_filters_by_zone_and_selected_date(full_client):
    resp = full_client.get("/suggestions?zone=8a&date=2026-04-15")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Tomato" in html
    assert "Basil" in html
    assert "Spinach" not in html


def test_suggestions_date_with_no_matching_plants_shows_message(full_client):
    resp = full_client.get("/suggestions?zone=9b&date=2026-01-15")
    html = resp.get_data(as_text=True)
    assert "No plants match Zone 9b" in html


def test_suggestions_search_by_plant_name(full_client):
    resp = full_client.get("/suggestions?zone=8a&date=2026-04-15&search=basil")
    html = resp.get_data(as_text=True)
    assert "Basil" in html
    assert "Tomato" not in html


def test_suggestions_search_no_results_keeps_search_field_intact(full_client):
    resp = full_client.get("/suggestions?zone=8a&date=2026-04-15&search=orchid")
    html = resp.get_data(as_text=True)
    assert 'No results found for "orchid"' in html
    assert 'value="orchid"' in html


def test_suggestions_sort_by_name_and_planting_time(full_client):
    html_name = full_client.get("/suggestions?zone=8a&date=2026-04-15&sort=name").get_data(as_text=True)
    assert html_name.index("Basil") < html_name.index("Tomato")

    html_time = full_client.get("/suggestions?zone=8a&date=2026-04-15&sort=planting_time").get_data(as_text=True)
    assert html_time.index("April - June") < html_time.index("March - May")


def test_suggestions_uses_logged_in_users_zone_automatically(full_client):
    login(full_client, 1)  # User 1 is in zone 8a
    resp = full_client.get("/suggestions?date=2026-10-15")
    html = resp.get_data(as_text=True)
    assert "Zone 8a" in html
    assert "Spinach" in html


def test_suggestions_shows_add_to_my_plants_button_for_logged_in_user(full_client):
    login(full_client, 1)
    html = full_client.get("/suggestions?zone=8a&date=2026-04-15").get_data(as_text=True)
    assert "/my-plants/add/1" in html
    assert "Add to My Plants" in html


def test_suggestions_invalid_date_falls_back_to_today(full_client):
    resp = full_client.get("/suggestions?zone=8a&date=not-a-date")
    assert resp.status_code == 200
    assert any("Invalid date format" in msg for _, msg in flashes(full_client))


# ==============================================================================
# F-06 / FR-03 / UC-03: User Registration, Log In, & Timeout (9 tests)
# ==============================================================================

def test_register_creates_hashed_user_with_zone_and_logs_in(full_client):
    resp = full_client.post(
        "/register",
        data={"email": "newgardener@test.com", "password": "secretpassword", "zip_code": "76201"},
    )
    assert resp.status_code == 302
    user = User.query.filter_by(email="newgardener@test.com").one()
    assert user.zip_code == "76201"
    assert user.growing_zone.zone_code == "8a"
    assert user.password_hash != "secretpassword"
    assert check_password_hash(user.password_hash, "secretpassword")


def test_register_rejects_missing_fields(full_client):
    full_client.post("/register", data={"email": "", "password": "secretpassword", "zip_code": "76201"})
    assert any("All fields are required" in msg for _, msg in flashes(full_client))


def test_register_rejects_short_password(full_client):
    full_client.post("/register", data={"email": "short@test.com", "password": "123", "zip_code": "76201"})
    assert User.query.filter_by(email="short@test.com").first() is None
    assert any("at least 6 characters" in msg for _, msg in flashes(full_client))


def test_register_rejects_duplicate_email(full_client):
    full_client.post("/register", data={"email": "a@test.com", "password": "secretpassword", "zip_code": "76201"})
    assert any("already registered" in msg for _, msg in flashes(full_client))


def test_register_rejects_invalid_zip_code(full_client):
    full_client.post("/register", data={"email": "badzip@test.com", "password": "secretpassword", "zip_code": "00000"})
    assert User.query.filter_by(email="badzip@test.com").first() is None
    assert any("couldn't find a growing zone" in msg for _, msg in flashes(full_client))


def test_login_valid_credentials_and_logout(full_client):
    u = db.session.get(User, 1)
    u.password_hash = generate_password_hash("mypassword")
    db.session.commit()

    resp = full_client.post("/login", data={"email": "a@test.com", "password": "mypassword"})
    assert resp.status_code == 302

    out = full_client.get("/logout")
    assert out.status_code == 302


def test_login_rejects_wrong_password(full_client):
    u = db.session.get(User, 1)
    u.password_hash = generate_password_hash("mypassword")
    db.session.commit()

    full_client.post("/login", data={"email": "a@test.com", "password": "wrongpassword"})
    assert any("Incorrect email or password" in msg for _, msg in flashes(full_client))


def test_login_blocks_suspended_user(full_client):
    u = db.session.get(User, 1)
    u.password_hash = generate_password_hash("mypassword")
    u.is_suspended = True
    db.session.commit()

    full_client.post("/login", data={"email": "a@test.com", "password": "mypassword"})
    assert any("suspended" in msg for _, msg in flashes(full_client))


def test_session_expires_after_30_minutes_of_inactivity(full_client):
    login(full_client, 1)
    expired_ts = (datetime.now(timezone.utc) - timedelta(minutes=31)).timestamp()
    with full_client.session_transaction() as sess:
        sess["last_active"] = expired_ts

    resp = full_client.get("/my-plants/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert any("session has expired" in msg for _, msg in flashes(full_client))


# ==============================================================================
# F-07 / FR-11 / UC-11: Plant Catalog Management — Admin (8 tests)
# ==============================================================================

def test_non_admin_cannot_access_plant_catalog(full_client):
    login(full_client, 1)  # Regular user
    resp = full_client.get("/admin/plants")
    assert resp.status_code == 302
    assert any("Administrator access required" in msg for _, msg in flashes(full_client))


def test_admin_can_view_plant_catalog(full_client):
    login(full_client, 10)  # Admin user
    resp = full_client.get("/admin/plants")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Plant Catalog Management" in html
    assert "Tomato" in html


def test_admin_can_add_plant_with_zones(full_client):
    login(full_client, 10)
    resp = full_client.post(
        "/admin/plants/add",
        data={
            "name": "Cucumber",
            "description": "Crisp climbing vine vegetable",
            "recommended_planting_time": "April - June",
            "zones": ["8a", "9b"],
        },
    )
    assert resp.status_code == 302
    cucumber = Plant.query.filter_by(name="Cucumber").one()
    assert {z.zone_code for z in cucumber.zones} == {"8a", "9b"}


def test_admin_add_plant_rejects_blank_fields_or_missing_zones(full_client):
    login(full_client, 10)
    full_client.post(
        "/admin/plants/add",
        data={"name": "incomplete", "description": "desc", "recommended_planting_time": "May", "zones": []},
    )
    assert Plant.query.filter_by(name="incomplete").first() is None
    assert any("All fields" in msg for _, msg in flashes(full_client))


def test_admin_add_plant_rejects_duplicate_name(full_client):
    login(full_client, 10)
    full_client.post(
        "/admin/plants/add",
        data={
            "name": "tomato",
            "description": "Duplicate",
            "recommended_planting_time": "April",
            "zones": ["8a"],
        },
    )
    assert Plant.query.filter(db.func.lower(Plant.name) == "tomato").count() == 1
    assert any("already exists" in msg for _, msg in flashes(full_client))


def test_admin_can_edit_existing_plant_and_zones(full_client):
    login(full_client, 10)
    resp = full_client.post(
        "/admin/plants/2/edit",
        data={
            "name": "Sweet Basil",
            "description": "Updated basil description",
            "recommended_planting_time": "March - July",
            "zones": ["8a", "9b"],
        },
    )
    assert resp.status_code == 302
    basil = db.session.get(Plant, 2)
    assert basil.name == "Sweet Basil"
    assert basil.description == "Updated basil description"
    assert {z.zone_code for z in basil.zones} == {"8a", "9b"}


def test_admin_can_remove_unsaved_plant(full_client):
    login(full_client, 10)
    resp = full_client.post("/admin/plants/3/remove")  # Spinach is not saved by anyone
    assert resp.status_code == 302
    assert db.session.get(Plant, 3) is None


def test_admin_cannot_remove_plant_saved_in_users_my_plants(full_client):
    login(full_client, 1)
    full_client.post("/my-plants/add/1")
    assert SavedPlant.query.filter_by(plant_id=1).count() == 1

    login(full_client, 10)
    resp = full_client.post("/admin/plants/1/remove")
    assert resp.status_code == 302
    assert db.session.get(Plant, 1) is not None
    assert any("currently saved in one or more users' My Plants" in msg for _, msg in flashes(full_client))
