"""
FR-05 / UC-05: Receive Severe Weather Alert.

Runs every 3 hours. Checks each 5-digit ZIP code that has at least one
non-suspended user with notifications_enabled=True, rather than checking per-user.
This keeps the number of weather lookups proportional to the number of distinct
ZIP codes in use (~500 users sharing a handful of ZIPs).

Alerts on a NEW Freeze Watch (24-48 hrs lead) or Freeze Warning / Frost Advisory
(12-24 hrs lead), or when an active alert escalates (watch -> warning).

Does NOT re-send the same alert every cycle while status is unchanged:
ZipWeatherStatus tracks the last status seen per ZIP code, and an email only
goes out on a new alert or escalation.
"""

import logging
import os
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

from app import db
from app.models import User, ZipWeatherStatus, WeatherAlert
from app.services.weather import get_freeze_status
from app.services.notifier import send_alert_email

logger = logging.getLogger(__name__)

_ALERT_MESSAGES = {
    "watch": (
        "Freeze Watch for your area in the next 24-48 hours. Keep an eye "
        "on conditions and plan to protect sensitive plants."
    ),
    "warning": (
        "Freeze Warning / Frost Advisory for your area in the next "
        "12-24 hours. Protect your plants soon."
    ),
}


def run_weather_check():
    """One scheduled check across all unique ZIP codes with opted-in, active users."""
    # Find all distinct ZIP codes that have at least one active, non-suspended subscriber
    active_zips = (
        db.session.query(User.zip_code)
        .filter(
            User.notifications_enabled.is_(True),
            User.is_suspended.is_(False),
            User.zip_code.isnot(None),
        )
        .distinct()
        .all()
    )

    zip_codes = [z[0] for z in active_zips if z[0]]

    for zip_code in zip_codes:
        new_status = get_freeze_status(zip_code)

        # None means NOAA/geocoding failed: skip and retry next cycle
        if new_status is None:
            logger.warning("Could not determine freeze status for %s; skipping cycle.", zip_code)
            continue

        state = db.session.get(ZipWeatherStatus, zip_code)
        if state is None:
            state = ZipWeatherStatus(zip_code=zip_code, status="none")
            db.session.add(state)

        # Alert if it's a new alert (none -> watch/warning) or an escalation (watch -> warning)
        is_new_alert = state.status == "none" and new_status in ("watch", "warning")
        is_escalation = state.has_escalated(new_status)

        if is_new_alert or is_escalation:
            message = _ALERT_MESSAGES[new_status]
            
            subscribers = User.query.filter_by(
                zip_code=zip_code,
                notifications_enabled=True,
                is_suspended=False,
            ).all()

            for user in subscribers:
                db.session.add(WeatherAlert(user_id=user.user_id, message=message))
                send_alert_email(user.email, message)

        # Update last known status and check timestamp
        state.update_status(new_status)

    db.session.commit()


def setup_scheduler(app):
    """Start the background scheduler, guarding against duplicate starts
    from Flask's debug-mode reloader (which runs app setup code twice)."""
    if not app.config.get("ENABLE_SCHEDULER", True):
        return

    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        # In the reloader's parent process -- the child process (where
        # WERKZEUG_RUN_MAIN == "true") is the one that should actually run it.
        return

    def _job():
        with app.app_context():
            run_weather_check()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_job, "interval", hours=3, id="weather_check", replace_existing=True)
    scheduler.start()