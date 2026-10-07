"""
FR-05: Receive Severe Weather Alert.

Runs every 3 hours. Checks each zone that has at least one user with
notifications_enabled=True, rather than checking per-user -- this keeps
the number of weather lookups proportional to the number of distinct
zones in use, not the number of users (important at ~500 users).

Alerts on a NEW Freeze Watch (24-48 hrs lead) or Freeze Warning /
Frost Advisory (12-24 hrs lead) for a zone. Watch is what gets users
to the 24-hour notice goal -- don't wait for Warning to alert.

Does NOT re-send the same alert every cycle while a Watch/Warning is
still active: ZoneWeatherStatus tracks the last status seen per zone,
and a new email only goes out when that status changes (none -> watch,
watch -> warning, or warning/watch -> none, which just resets state
quietly so a later re-escalation alerts again).
"""
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app import db
from app.models import GrowingZone, User, ZoneWeatherStatus, WeatherAlert
from app.services.weather import get_freeze_status
from app.services.notifier import send_alert_email

_ALERT_MESSAGES = {
    "watch": "Freeze Watch for your area in the next 24-48 hours. Keep an eye "
             "on conditions and plan to protect sensitive plants.",
    "warning": "Freeze Warning / Frost Advisory for your area in the next "
               "12-24 hours. Protect your plants soon.",
}


def run_weather_check():
    """One scheduled check across all zones with opted-in users."""
    zones_with_subscribers = (
        db.session.query(GrowingZone)
        .join(User, User.zone_id == GrowingZone.zone_id)
        .filter(User.notifications_enabled.is_(True))
        .distinct()
        .all()
    )

    for zone in zones_with_subscribers:
        new_status = get_freeze_status(zone.zone_code)

        state = db.session.get(ZoneWeatherStatus, zone.zone_id)
        if state is None:
            state = ZoneWeatherStatus(zone_id=zone.zone_id, status="none")
            db.session.add(state)

        status_changed = new_status != state.status
        is_alertable = new_status in ("watch", "warning")

        if status_changed and is_alertable:
            message = _ALERT_MESSAGES[new_status]
            subscribers = User.query.filter_by(
                zone_id=zone.zone_id, notifications_enabled=True
            ).all()
            for user in subscribers:
                db.session.add(WeatherAlert(user_id=user.user_id, message=message))
                send_alert_email(user.email, message)

        state.status = new_status
        state.last_checked_at = datetime.utcnow()

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
