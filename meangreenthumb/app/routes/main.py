from flask import Blueprint, render_template, request, flash

from app.models import GrowingZone
from app.services.zone_lookup import lookup_zone_code

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET", "POST"])
def home():
    """UC-01: Look Up Growing Zone. Works for guests and registered users."""
    zone_code = None

    if request.method == "POST":
        zip_code = request.form.get("zip_code", "").strip()
        zone_code = lookup_zone_code(zip_code)

        if zone_code is None:
            flash("Please enter a valid 5-digit zip code with a matching growing zone.")

    return render_template("home.html", zone_code=zone_code)


# --- Placeholders for the rest of the team to build out ---
# Sudip: plant suggestions route (UC-02) goes here or in its own blueprint
# Xavier: weather dashboard + planting calendar routes (UC-04/05/06)
# Pete: community tips, My Plants, care tasks (UC-07/08/09) -- see TODO.md
