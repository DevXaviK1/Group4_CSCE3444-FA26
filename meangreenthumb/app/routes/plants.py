"""Plant Suggestions (FR-02 / UC-02)."""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app import db
from app.models import GrowingZone, Plant

plants_bp = Blueprint("plants", __name__)

_MONTH_NAMES = {
    1: ("jan", "january", "winter", "year-round", "all year"),
    2: ("feb", "february", "winter", "late winter", "early spring", "spring", "year-round"),
    3: ("mar", "march", "spring", "early spring", "year-round"),
    4: ("apr", "april", "spring", "mid spring", "late spring", "year-round"),
    5: ("may", "spring", "late spring", "early summer", "summer", "year-round"),
    6: ("jun", "june", "summer", "early summer", "year-round"),
    7: ("jul", "july", "summer", "mid summer", "year-round"),
    8: ("aug", "august", "summer", "late summer", "early fall", "fall", "year-round"),
    9: ("sep", "sept", "september", "fall", "early fall", "autumn", "year-round"),
    10: ("oct", "october", "fall", "mid fall", "late fall", "autumn", "year-round"),
    11: ("nov", "november", "fall", "late fall", "winter", "year-round"),
    12: ("dec", "december", "winter", "year-round"),
}

_MONTH_ABBR_TO_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

DEFAULT_CATALOG = [
    (
        "Tomato",
        "Warm-season fruiting plant that thrives in full sun and well-drained soil.",
        "March - May, August - September",
        ["6a", "6b", "7a", "7b", "8a", "8b", "9a", "9b", "10a", "10b"],
    ),
    (
        "Basil",
        "Fragrant culinary herb that grows fast in warm weather alongside tomatoes.",
        "March - June, August - September",
        ["5b", "6a", "6b", "7a", "7b", "8a", "8b", "9a", "9b", "10a", "10b", "11a"],
    ),
    (
        "Spinach",
        "Cool-season leafy green rich in nutrients; bolts in intense summer heat.",
        "February - April, September - November",
        ["4b", "5b", "6a", "6b", "7a", "7b", "8a", "8b", "9a", "9b"],
    ),
    (
        "Bell Pepper",
        "Sweet crisp pepper that loves warm soil and steady moisture.",
        "April - June, August - September",
        ["6a", "6b", "7a", "7b", "8a", "8b", "9a", "9b", "10a", "10b", "11a"],
    ),
    (
        "Carrot",
        "Hardy root vegetable that develops its best sweetness in cool fall and spring weather.",
        "February - April, August - November",
        ["4b", "5b", "6a", "6b", "7a", "7b", "8a", "8b", "9a", "9b", "10b"],
    ),
    (
        "Kale",
        "Frost-tolerant leafy green that grows through fall, winter, and early spring.",
        "January - April, September - December",
        ["4b", "5b", "6a", "6b", "7a", "7b", "8a", "8b", "9a", "9b", "10b"],
    ),
    (
        "Zucchini",
        "Productive summer squash that germinates quickly in warm soil.",
        "April - July",
        ["5b", "6a", "6b", "7a", "7b", "8a", "8b", "9a", "9b", "10b"],
    ),
    (
        "Garlic",
        "Easy-care bulb planted in autumn for a midsummer harvest.",
        "September - November",
        ["4b", "5b", "6a", "6b", "7a", "7b", "8a", "8b", "9a", "9b"],
    ),
]



def first_planting_month(recommended_time: str | None) -> int:
    """Return the month number (1-12) of the earliest month named in the
    planting-time text, or 13 if none is named (sorts those last)."""
    text = (recommended_time or "").lower()
    hits = [(text.find(abbr), num) for abbr, num in _MONTH_ABBR_TO_NUM.items() if abbr in text]
    return min(hits)[1] if hits else 13

def ensure_seed_catalog() -> None:
    """Seed the default plant catalog if the database has no plants at all."""
    if Plant.query.first() is not None:
        return

    zone_map: dict[str, GrowingZone] = {
        z.zone_code: z for z in GrowingZone.query.all()
    }
    for name, desc, planting_time, zone_codes in DEFAULT_CATALOG:
        plant = Plant(
            name=name,
            description=desc,
            recommended_planting_time=planting_time,
        )
        for zc in zone_codes:
            if zc not in zone_map:
                z_obj = GrowingZone(zone_code=zc)
                db.session.add(z_obj)
                db.session.flush()
                zone_map[zc] = z_obj
            plant.zones.append(zone_map[zc])
        db.session.add(plant)
    db.session.commit()


def is_plant_in_season(recommended_time: str | None, target_date: date) -> bool:
    """Check whether a plant's recommended_planting_time includes target_date's month."""
    if not recommended_time or not recommended_time.strip():
        return True

    text = recommended_time.lower()
    month = target_date.month

    for kw in _MONTH_NAMES.get(month, ()):
        if kw in text:
            return True

    segments = [seg.strip() for seg in text.replace(";", ",").split(",")]
    for seg in segments:
        if "-" in seg:
            parts = [p.strip() for p in seg.split("-", 1)]
            start_m = next((num for abbr, num in _MONTH_ABBR_TO_NUM.items() if abbr in parts[0]), None)
            end_m = next((num for abbr, num in _MONTH_ABBR_TO_NUM.items() if abbr in parts[1]), None)
            if start_m and end_m:
                if start_m <= end_m and start_m <= month <= end_m:
                    return True
                if start_m > end_m and (month >= start_m or month <= end_m):
                    return True

    return False


@plants_bp.route("/suggestions", methods=["GET"])
def suggestions():
    """UC-02 / FR-02: View Plant Suggestions for the user's growing zone and date."""
    ensure_seed_catalog()

    zone_code = (request.args.get("zone") or "").strip().lower()
    if not zone_code and current_user.is_authenticated and current_user.growing_zone:
        zone_code = current_user.growing_zone.zone_code
    if not zone_code:
        zone_code = (session.get("zone_code") or "").strip().lower()

    if not zone_code:
        flash("Please look up your growing zone first to view plant suggestions.", "warning")
        return redirect(url_for("main.home"))

    raw_date = (request.args.get("date") or "").strip()
    selected_date = date.today()
    if raw_date:
        try:
            selected_date = date.fromisoformat(raw_date)
        except ValueError:
            flash("Invalid date format; showing suggestions for today.", "warning")
            selected_date = date.today()

    search_query = (request.args.get("search") or "").strip()
    sort_by = (request.args.get("sort") or "name").strip().lower()
    if sort_by not in ("name", "planting_time"):
        sort_by = "name"

    zone = GrowingZone.query.filter_by(zone_code=zone_code).first()
    zone_plants = list(zone.plants) if zone else []

    seasonal_plants = [
        p for p in zone_plants if is_plant_in_season(p.recommended_planting_time, selected_date)
    ]

    no_date_matches = len(seasonal_plants) == 0

    if search_query:
        matched_plants = [
            p for p in seasonal_plants if search_query.lower() in p.name.lower()
        ]
    else:
        matched_plants = seasonal_plants

    no_search_matches = bool(search_query) and not no_date_matches and len(matched_plants) == 0

    if sort_by == "planting_time":
        matched_plants.sort(key=lambda p: (first_planting_month(p.recommended_planting_time), p.name.lower()))
    else:
        matched_plants.sort(key=lambda p: p.name.lower())

    saved_ids = set()
    if current_user.is_authenticated:
        saved_ids = {sp.plant_id for sp in current_user.saved_plants}

    return render_template(
        "suggestions.html",
        zone_code=zone_code,
        selected_date=selected_date.isoformat(),
        search_query=search_query,
        sort_by=sort_by,
        plants=matched_plants,
        no_date_matches=no_date_matches,
        no_search_matches=no_search_matches,
        saved_ids=saved_ids,
    )
