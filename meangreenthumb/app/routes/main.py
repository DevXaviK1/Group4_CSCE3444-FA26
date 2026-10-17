from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import current_user, login_required

from app import db
from app.models import GrowingZone
from app.services.zone_lookup import lookup_zone_code
from app.services.weather import (
    get_forecast,
    get_alert_details,
    get_freeze_status,
    WeatherUnavailable,
)
from app.services.calendar_service import generate_planting_calendar

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET", "POST"])
def home():
    """UC-01: Look Up Growing Zone. Works for guests and registered users."""
    zone_code = None
    zip_code = None

    if request.method == "POST":
        zip_code = request.form.get("zip_code", "").strip()
        zone_code = lookup_zone_code(zip_code)

        if zone_code is None:
            flash("Please enter a valid 5-digit zip code with a matching growing zone.", "error")
        else:
            session["zone_code"] = zone_code
            session["zip_code"] = zip_code

            # UC-01 Postcondition: If user is logged in, save zip code & zone to their profile
            if current_user.is_authenticated:
                zone = GrowingZone.query.filter_by(zone_code=zone_code).first()
                if zone is None:
                    zone = GrowingZone(zone_code=zone_code)
                    db.session.add(zone)
                    db.session.flush()
                current_user.zip_code = zip_code
                current_user.zone_id = zone.zone_id
                db.session.commit()

    return render_template("home.html", zone_code=zone_code, zip_code=zip_code)


@main_bp.route("/weather", methods=["GET"])
def weather_forecast():
    """UC-04: View Weather Forecast (Figure 7).
    
    Shows current conditions, 5-day forecast, and cache fallback.
    """
    zip_code = None
    if current_user.is_authenticated and current_user.zip_code:
        zip_code = current_user.zip_code
    else:
        zip_code = request.args.get("zip_code") or session.get("zip_code")

    if not zip_code:
        flash("Please enter a zip code to view weather.", "warning")
        return redirect(url_for("main.home"))

    try:
        forecast = get_forecast(zip_code)
    except WeatherUnavailable:
        flash("Weather data is currently unavailable.", "danger")
        return render_template("weather.html", zip_code=zip_code, forecast=None, active_alert=False)

    freeze_status = get_freeze_status(zip_code)
    active_alert = freeze_status in ("watch", "warning")

    return render_template(
        "weather.html",
        zip_code=zip_code,
        forecast=forecast,
        active_alert=active_alert,
        freeze_status=freeze_status,
    )


@main_bp.route("/weather/alerts", methods=["GET"])
@login_required
def alert_details():
    """UC-05: Severe Weather Alert Details Screen (Figure 8). Registered users only."""
    zip_code = current_user.zip_code or request.args.get("zip_code")

    if not zip_code:
        return redirect(url_for("main.weather_forecast"))

    alerts = get_alert_details(zip_code)
    return render_template("alert_details.html", zip_code=zip_code, alerts=alerts)


@main_bp.route("/calendar", methods=["GET"])
@login_required
def planting_calendar():
    """UC-06: Planting Calendar Screen (Figure 9).
    
    Generates planting and harvest windows using frost dates or general guidance.
    """
    if not current_user.saved_plants:
        flash("Add at least one plant to My Plants to generate a planting calendar.", "info")
        return redirect(url_for("main.home"))

    calendar = generate_planting_calendar(current_user.saved_plants, current_user.zip_code)
    return render_template("planting_calendar.html", calendar=calendar)
