"""Tests for UC-08 My Plants. Fixtures live in conftest.py. Run with: python -m pytest"""
from datetime import date

import pytest

from app.models import SavedPlant
from helpers import flashes, login


def saved_for(user_id):
    return SavedPlant.query.filter_by(user_id=user_id).all()


def test_add_creates_entry_defaulting_to_today(client):
    login(client, 1)
    resp = client.post("/my-plants/add/1")
    assert resp.status_code == 302
    entries = saved_for(1)
    assert len(entries) == 1
    assert entries[0].plant_id == 1
    assert entries[0].planting_date == date.today()
    assert ("success", "Tomato added to My Plants.") in flashes(client)


def test_add_accepts_explicit_planting_date(client):
    login(client, 1)
    client.post("/my-plants/add/1", data={"planting_date": "2026-04-15"})
    assert saved_for(1)[0].planting_date == date(2026, 4, 15)


def test_add_invalid_date_creates_nothing(client):
    login(client, 1)
    client.post("/my-plants/add/1", data={"planting_date": "04/15/2026"})
    assert saved_for(1) == []
    assert any(cat == "error" for cat, _ in flashes(client))


def test_add_duplicate_is_rejected_with_notice(client):
    login(client, 1)
    client.post("/my-plants/add/1")
    client.post("/my-plants/add/1")
    assert len(saved_for(1)) == 1
    assert ("info", "Tomato is already in My Plants.") in flashes(client)


def test_two_users_can_save_the_same_plant(client):
    login(client, 1)
    client.post("/my-plants/add/1")
    login(client, 2)
    client.post("/my-plants/add/1")
    assert len(saved_for(1)) == 1
    assert len(saved_for(2)) == 1


def test_add_unknown_plant_is_404(client):
    login(client, 1)
    assert client.post("/my-plants/add/999").status_code == 404


def test_anonymous_cannot_add_or_view(client):
    assert client.post("/my-plants/add/1").status_code == 401
    assert client.get("/my-plants/").status_code == 401
    assert SavedPlant.query.count() == 0


def test_add_is_post_only(client):
    login(client, 1)
    assert client.get("/my-plants/add/1").status_code == 405


def test_index_lists_only_own_plants(client):
    login(client, 1)
    client.post("/my-plants/add/1")  # Tomato
    login(client, 2)
    client.post("/my-plants/add/2")  # Basil
    login(client, 1)
    html = client.get("/my-plants/").get_data(as_text=True)
    assert "Tomato" in html
    assert "Basil" not in html


def test_index_empty_state(client):
    login(client, 1)
    html = client.get("/my-plants/").get_data(as_text=True)
    assert "haven't added any plants" in html


def test_remove_own_entry(client):
    login(client, 1)
    client.post("/my-plants/add/1")
    entry_id = saved_for(1)[0].saved_plant_id
    resp = client.post(f"/my-plants/{entry_id}/remove")
    assert resp.status_code == 302
    assert saved_for(1) == []


def test_cannot_remove_another_users_entry(client):
    login(client, 1)
    client.post("/my-plants/add/1")
    entry_id = saved_for(1)[0].saved_plant_id
    login(client, 2)
    assert client.post(f"/my-plants/{entry_id}/remove").status_code == 404
    assert len(saved_for(1)) == 1


def test_next_redirects_to_local_path(client):
    login(client, 1)
    resp = client.post("/my-plants/add/1", data={"next": "/suggestions"})
    assert resp.headers["Location"].endswith("/suggestions")


@pytest.mark.parametrize("bad", ["//evil.com", "https://evil.com", "/\\evil.com"])
def test_next_rejects_offsite_redirects(client, bad):
    login(client, 1)
    resp = client.post("/my-plants/add/2", data={"next": bad})
    assert resp.headers["Location"].endswith("/my-plants/")


def test_calendar_link_shown_only_when_plants_saved(client):
    login(client, 1)
    assert b"View planting calendar" not in client.get("/my-plants/").data
    client.post("/my-plants/add/1")
    assert b'href="/calendar"' in client.get("/my-plants/").data
