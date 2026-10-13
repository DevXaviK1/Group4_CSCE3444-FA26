"""Tests for UC-07 community tips. Fixtures live in conftest.py."""
from datetime import datetime, timedelta

from app import db
from app.models import GrowingZone, Tip
from helpers import flashes, login


def zone_id(code):
    return GrowingZone.query.filter_by(zone_code=code).one().zone_id


def post_tip(client, text):
    return client.post("/tips/", data={"text": text})


def feed_html(client):
    return client.get("/tips/").get_data(as_text=True)


def test_anonymous_cannot_view_or_post(client):
    assert client.get("/tips/").status_code == 401
    assert client.post("/tips/", data={"text": "hi"}).status_code == 401
    assert Tip.query.count() == 0


def test_empty_feed_shows_message(client):
    login(client, 1)
    html = feed_html(client)
    assert "No tips yet" in html
    assert "<textarea" in html


def test_post_saves_tip_with_authors_zone(client):
    login(client, 1)
    resp = post_tip(client, "Mulch tomatoes after the soil warms up.")
    assert resp.status_code == 302
    tip = Tip.query.one()
    assert tip.user_id == 1
    assert tip.zone_id == zone_id("8a")
    assert tip.text == "Mulch tomatoes after the soil warms up."
    assert ("success", "Your tip was posted.") in flashes(client)
    assert "Mulch tomatoes" in feed_html(client)


def test_empty_and_whitespace_tips_are_rejected(client):
    login(client, 1)
    post_tip(client, "")
    post_tip(client, "   \n\t ")
    client.post("/tips/", data={})  # field missing entirely
    assert Tip.query.count() == 0
    assert ("error", "A tip can't be empty.") in flashes(client)


def test_tip_text_is_trimmed(client):
    login(client, 1)
    post_tip(client, "  Water early in the morning.  ")
    assert Tip.query.one().text == "Water early in the morning."


def test_length_limit(client):
    login(client, 1)
    post_tip(client, "x" * 501)
    assert Tip.query.count() == 0
    post_tip(client, "x" * 500)
    assert Tip.query.count() == 1


def test_user_without_zone_sees_prompt_and_cannot_post(client):
    login(client, 3)
    html = feed_html(client)
    assert "Set your growing zone first to post a tip" in html
    assert "<textarea" not in html
    resp = post_tip(client, "Can't post this")
    assert resp.status_code == 302
    assert Tip.query.count() == 0
    assert any(cat == "error" for cat, _ in flashes(client))


def test_feed_is_shared_across_all_zones(client):
    login(client, 1)
    post_tip(client, "Zone 8a tip from user 1")
    login(client, 4)
    post_tip(client, "Zone 9b tip from user 4")

    # Everyone sees every tip: same zone, a different zone, or no zone at all.
    for user_id in (1, 2, 3, 4):
        login(client, user_id)
        html = feed_html(client)
        assert "Zone 8a tip from user 1" in html
        assert "Zone 9b tip from user 4" in html


def test_each_tip_shows_the_zone_it_was_posted_from(client):
    login(client, 1)
    post_tip(client, "From 8a")
    login(client, 4)
    post_tip(client, "From 9b")
    html = feed_html(client)
    assert "Zone 8a" in html
    assert "Zone 9b" in html
    assert html.count("Zone 8a") == 1
    assert html.count("Zone 9b") == 1


def test_user_without_zone_can_still_read_tips(client):
    login(client, 1)
    post_tip(client, "Visible to everyone")
    login(client, 3)
    html = feed_html(client)
    assert "Visible to everyone" in html
    assert "<textarea" not in html


def test_feed_is_newest_first(client):
    login(client, 1)
    now = datetime(2026, 5, 1, 12, 0)
    for i, label in enumerate(["oldest", "middle", "newest"]):
        db.session.add(
            Tip(user_id=1, zone_id=zone_id("8a"), text=label, timestamp=now + timedelta(hours=i))
        )
    db.session.commit()
    html = feed_html(client)
    assert html.index("newest") < html.index("middle") < html.index("oldest")


def test_feed_shows_at_most_50_tips(client):
    login(client, 1)
    base = datetime(2026, 5, 1)
    for i in range(55):
        db.session.add(
            Tip(user_id=1, zone_id=zone_id("8a"), text=f"tip {i}", timestamp=base + timedelta(minutes=i))
        )
    db.session.commit()
    html = feed_html(client)
    assert html.count('class="tip"') == 50
    assert "tip 54" in html
    assert "tip 4<" not in html  # the oldest five are cut off


def test_tip_text_is_html_escaped(client):
    login(client, 1)
    post_tip(client, "<script>alert(1)</script>")
    html = feed_html(client)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_feed_does_not_expose_author_email(client):
    login(client, 1)
    post_tip(client, "Anything")
    html = feed_html(client)
    assert "a@test.com" not in html
    assert "Gardener #1" in html
