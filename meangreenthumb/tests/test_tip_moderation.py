"""Tests for UC-10 / FR-10: admin tip moderation. Fixtures live in conftest.py."""
from datetime import datetime, timedelta

import pytest

from app import db
from app.models import GrowingZone, Tip, User
from app.routes.admin import admin_bp
from helpers import flashes, login

ADMIN_ID = 10
NOW = datetime(2026, 11, 2, 12, 0, 0)


@pytest.fixture()
def mod_app(flask_app):
    """The shared test app plus the admin blueprint, an admin account and tips."""
    flask_app.register_blueprint(admin_bp)
    flask_app.add_url_rule("/", endpoint="main.home", view_func=lambda: "home")

    with flask_app.app_context():
        zone_8a = GrowingZone.query.filter_by(zone_code="8a").one()
        zone_9b = GrowingZone.query.filter_by(zone_code="9b").one()
        db.session.add(
            User(
                user_id=ADMIN_ID,
                email="admin@test.com",
                password_hash="x",
                zone_id=zone_8a.zone_id,
                is_admin=True,
            )
        )
        db.session.add_all(
            [
                Tip(tip_id=1, user_id=1, zone_id=zone_8a.zone_id, text="Oldest tip", timestamp=NOW - timedelta(days=2)),
                Tip(tip_id=2, user_id=2, zone_id=zone_9b.zone_id, text="Middle tip", timestamp=NOW - timedelta(days=1)),
                Tip(tip_id=3, user_id=1, zone_id=zone_8a.zone_id, text="Newest tip", timestamp=NOW),
            ]
        )
        db.session.commit()
    return flask_app


@pytest.fixture()
def mclient(mod_app):
    return mod_app.test_client()


def page(client, url="/admin/tips"):
    return client.get(url).get_data(as_text=True)


def test_guest_cannot_open_moderation_or_remove(mclient):
    assert mclient.get("/admin/tips").status_code == 401
    assert mclient.post("/admin/tips/1/remove").status_code == 401
    assert Tip.query.count() == 3


def test_non_admin_is_turned_away_and_cannot_remove(mclient):
    login(mclient, 1)
    resp = mclient.get("/admin/tips")
    assert resp.status_code == 302
    assert any("Unauthorized" in msg for _, msg in flashes(mclient))
    assert mclient.get("/admin/tips/1/remove").status_code == 302
    assert mclient.post("/admin/tips/1/remove").status_code == 302
    assert Tip.query.count() == 3


def test_admin_sees_all_tips_newest_first_with_author_and_zone(mclient):
    login(mclient, ADMIN_ID)
    html = page(mclient)
    assert html.index("Newest tip") < html.index("Middle tip") < html.index("Oldest tip")
    assert "a@test.com" in html and "b@test.com" in html
    assert "Zone 8a" in html and "Zone 9b" in html


def test_empty_list_shows_no_tips_message(mod_app):
    with mod_app.app_context():
        Tip.query.delete()
        db.session.commit()
    client = mod_app.test_client()
    login(client, ADMIN_ID)
    assert "No tips to moderate" in page(client)


def test_filter_by_zone(mclient):
    login(mclient, ADMIN_ID)
    html = page(mclient, "/admin/tips?zone=9b")
    assert "Middle tip" in html
    assert "Newest tip" not in html and "Oldest tip" not in html


def test_filter_by_author(mclient):
    login(mclient, ADMIN_ID)
    html = page(mclient, "/admin/tips?author=a@test")
    assert "Newest tip" in html and "Oldest tip" in html
    assert "Middle tip" not in html


def test_filter_with_no_matches_says_so(mclient):
    login(mclient, ADMIN_ID)
    assert "No tips match those filters" in page(mclient, "/admin/tips?author=nobody")


def test_confirmation_page_shows_tip_and_deletes_nothing(mclient):
    login(mclient, ADMIN_ID)
    resp = mclient.get("/admin/tips/2/remove")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Middle tip" in html and "Remove tip" in html and "Cancel" in html
    assert Tip.query.count() == 3


def test_cancel_leaves_the_tip_in_place(mclient):
    login(mclient, ADMIN_ID)
    html = page(mclient, "/admin/tips/2/remove")
    assert 'href="/admin/tips"' in html  # the Cancel link goes back to the list
    assert "Middle tip" in page(mclient, "/admin/tips")
    assert Tip.query.count() == 3


def test_admin_confirms_removal_and_tip_leaves_the_community_feed(mclient):
    login(mclient, 1)
    assert "Middle tip" in page(mclient, "/tips/")

    login(mclient, ADMIN_ID)
    resp = mclient.post("/admin/tips/2/remove")
    assert resp.status_code == 302
    assert db.session.get(Tip, 2) is None
    assert Tip.query.count() == 2
    assert ("success", "Tip removed.") in flashes(mclient)

    login(mclient, 1)
    feed = page(mclient, "/tips/")
    assert "Middle tip" not in feed
    assert "Newest tip" in feed and "Oldest tip" in feed


def test_removing_a_missing_tip_returns_404(mclient):
    login(mclient, ADMIN_ID)
    assert mclient.get("/admin/tips/999/remove").status_code == 404
    assert mclient.post("/admin/tips/999/remove").status_code == 404
