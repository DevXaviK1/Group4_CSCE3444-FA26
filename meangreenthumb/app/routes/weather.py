"""Weather, Alert Details, and Planting Calendar routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.services.calendar_service import generate_planting_calendar
from app.services.weather import (
    WeatherUnavailable,
    get_alert_details,
    get_forecast,
    get_freeze_status,
)

weather_bp = Blueprint("weather", __name__)


@weather_bp.route("/weather", methods=["GET"])
def forecast_view():
    """UC-04: View Weather Forecast (Figure 7)."""
    zip_code = None
    if current_user.is_authenticated and current_user.zip_code:
        zip_code = current_user.zip_code
    else:
        zip_code = request.args.get("zip_code")

    if not zip_code:
        flash("Please provide a zip code to view weather.", "warning")
        return redirect(url_for("main.index"))

    try:
        forecast = get_forecast(zip_code)
    except WeatherUnavailable:
        flash("Weather data currently unavailable.", "danger")
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


@weather_bp.route("/weather/alerts", methods=["GET"])
def alert_details_view():
    """UC-05: Alert Details Screen (Figure 8)."""
    zip_code = None
    if current_user.is_authenticated and current_user.zip_code:
        zip_code = current_user.zip_code
    else:
        zip_code = request.args.get("zip_code")

    if not zip_code:
        return redirect(url_for("weather.forecast_view"))

    alerts = get_alert_details(zip_code)
    return render_template("alert_details.html", zip_code=zip_code, alerts=alerts)


@weather_bp.route("/calendar", methods=["GET"])
@login_required
def planting_calendar_view():
    """UC-06: Planting Calendar Screen (Figure 9)."""
    if not current_user.saved_plants:
        flash("Add at least one plant to My Plants to generate a calendar.", "info")
        return redirect(url_for("plants.my_plants"))

    calendar = generate_planting_calendar(current_user.saved_plants, current_user.zip_code)
    return render_template("planting_calendar.html", calendar=calendar)