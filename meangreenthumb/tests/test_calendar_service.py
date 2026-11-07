"""Tests for the frost-date based planting calendar (FR-06 / UC-06)."""
from types import SimpleNamespace

import pytest

from app.services import calendar_service
from app.services.calendar_service import (
    FROST_DATES_BY_ZONE,
    _get_frost_dates,
    generate_planting_calendar,
)


def _saved(name="Tomato", planting_time=None):
    plant = SimpleNamespace(name=name, recommended_planting_time=planting_time)
    return SimpleNamespace(plant=plant)


def test_known_zip_returns_frost_dates_for_its_zone():
    # 76201 (Denton, TX) is zone 8a in the local zone table.
    assert _get_frost_dates("76201") == {
        "last_spring_frost": "Mar 25",
        "first_fall_frost": "Nov 10",
    }


@pytest.mark.parametrize("zip_code", ["", "abc", "1234", "00012", None])
def test_invalid_zip_returns_none(zip_code):
    assert _get_frost_dates(zip_code) is None


def test_frost_free_zone_returns_none():
    # 33101 (Miami) is zone 11a, which has no frost dates.
    assert _get_frost_dates("33101") is None


def test_every_zone_has_both_dates():
    for zone, dates in FROST_DATES_BY_ZONE.items():
        assert set(dates) == {"last_spring_frost", "first_fall_frost"}, zone


def test_calendar_uses_frost_dates_when_available():
    entries = generate_planting_calendar([_saved("Tomato"), _saved("Basil")], "76201")
    assert [e["name"] for e in entries] == ["Tomato", "Basil"]
    for entry in entries:
        assert entry["plant_by"] == "After Mar 25"
        assert entry["harvest"] == "Before Nov 10"
        assert entry["is_fallback"] is False


def test_calendar_falls_back_when_no_frost_dates():
    entries = generate_planting_calendar([_saved("Aloe", "Year round")], "33101")
    assert entries[0]["is_fallback"] is True
    assert entries[0]["plant_by"] == "Year round"
    assert "General Seasonal Guidance" in entries[0]["harvest"]


def test_calendar_fallback_uses_default_text_without_planting_time():
    entries = generate_planting_calendar([_saved("Aloe")], "33101")
    assert entries[0]["plant_by"] == "Spring (General Seasonal Guidance)"


def test_calendar_with_no_plants_is_empty():
    assert generate_planting_calendar([], "76201") == []


def test_zone_lookup_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(calendar_service, "lookup_zone_code", lambda z: "8A")
    assert _get_frost_dates("76201")["last_spring_frost"] == "Mar 25"
