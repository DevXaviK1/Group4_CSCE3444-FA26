"""UC-06 / FR-06: Planting Calendar Generator."""

from typing import Any, Dict, List, Optional
from app.models import SavedPlant


def _get_frost_dates(zip_code: str) -> Optional[Dict[str, str]]:
    """Retrieve last spring frost and first fall frost dates for the zip code.
    
    Returns None if unavailable so UC-06 Alternative Flow engages.
    """
    # NOAA climate normal endpoints can be plugged in here.
    return None


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