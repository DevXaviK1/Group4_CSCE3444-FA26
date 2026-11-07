"""UC-06 / FR-06: Planting Calendar Generator."""

from typing import Any, Dict, List, Optional
from app.models import SavedPlant
from app.services.zone_lookup import lookup_zone_code


# Average last spring frost and first fall frost for each USDA hardiness zone.
# These are general planning averages for the continental US, not local weather
# normals. Zones that rarely or never freeze (10b and above) are left out on
# purpose, so the calendar falls back to general seasonal guidance for them.
FROST_DATES_BY_ZONE: Dict[str, Dict[str, str]] = {
    "3a": {"last_spring_frost": "May 31", "first_fall_frost": "Sep 15"},
    "3b": {"last_spring_frost": "May 25", "first_fall_frost": "Sep 20"},
    "4a": {"last_spring_frost": "May 20", "first_fall_frost": "Sep 25"},
    "4b": {"last_spring_frost": "May 12", "first_fall_frost": "Oct 1"},
    "5a": {"last_spring_frost": "May 5", "first_fall_frost": "Oct 8"},
    "5b": {"last_spring_frost": "Apr 28", "first_fall_frost": "Oct 15"},
    "6a": {"last_spring_frost": "Apr 22", "first_fall_frost": "Oct 20"},
    "6b": {"last_spring_frost": "Apr 15", "first_fall_frost": "Oct 25"},
    "7a": {"last_spring_frost": "Apr 10", "first_fall_frost": "Oct 30"},
    "7b": {"last_spring_frost": "Apr 1", "first_fall_frost": "Nov 5"},
    "8a": {"last_spring_frost": "Mar 25", "first_fall_frost": "Nov 10"},
    "8b": {"last_spring_frost": "Mar 15", "first_fall_frost": "Nov 15"},
    "9a": {"last_spring_frost": "Feb 25", "first_fall_frost": "Nov 25"},
    "9b": {"last_spring_frost": "Feb 10", "first_fall_frost": "Dec 5"},
    "10a": {"last_spring_frost": "Jan 25", "first_fall_frost": "Dec 15"},
}


def _get_frost_dates(zip_code: str) -> Optional[Dict[str, str]]:
    """Return the average last spring frost and first fall frost dates for the
    zip code's USDA growing zone.

    Returns None if the zip code has no known zone, or the zone has no frost
    dates (frost-free zones), so UC-06 Alternative Flow engages.
    """
    zone_code = lookup_zone_code(zip_code)
    if zone_code is None:
        return None
    return FROST_DATES_BY_ZONE.get(zone_code.strip().lower())


def generate_planting_calendar(saved_plants: List[SavedPlant], zip_code: str) -> List[Dict[str, Any]]:
    """Calculates planting and care windows for saved plants."""
    frost_dates = _get_frost_dates(zip_code)
    calendar_entries = []

    for sp in saved_plants:
        plant = sp.plant
        if frost_dates:
            calendar_entries.append({
                "name": plant.name,
                "plant_by": f"After {frost_dates.get('last_spring_frost')}",
                "harvest": f"Before {frost_dates.get('first_fall_frost')}",
                "is_fallback": False,
            })
        else:
            # Alternative Flow 3a: general seasonal guidance fallback
            calendar_entries.append({
                "name": plant.name,
                "plant_by": plant.recommended_planting_time or "Spring (General Seasonal Guidance)",
                "harvest": "Mid Summer - Fall (General Seasonal Guidance)",
                "is_fallback": True,
            })

    return calendar_entries