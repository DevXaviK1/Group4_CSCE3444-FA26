"""FR-05 / UC-05: the 3-hour freeze check. NOAA and email are replaced with fakes."""
import pytest

from app import db
from app.models import User, WeatherAlert, ZipWeatherStatus
from app.scheduler import run_weather_check

ZIP = "76201"


@pytest.fixture()
def alerts(flask_app, monkeypatch):
    """Returns a recorder; set .status to what NOAA 'says' before each run."""

    class Recorder:
        status = "none"
        checked = []
        emails = []

    rec = Recorder()
    rec.checked, rec.emails = [], []
    monkeypatch.setattr("app.scheduler.get_freeze_status", lambda z: (rec.checked.append(z), rec.status)[1])
    monkeypatch.setattr("app.scheduler.send_alert_email", lambda to, msg: rec.emails.append((to, msg)) or True)
    return rec


def subscribe(user_id, **fields):
    user = db.session.get(User, user_id)
    user.zip_code = ZIP
    user.notifications_enabled = True
    for key, value in fields.items():
        setattr(user, key, value)
    db.session.commit()


def status_row():
    return db.session.get(ZipWeatherStatus, ZIP)


def test_no_opted_in_users_means_no_noaa_calls(alerts):
    run_weather_check()
    assert alerts.checked == [] and alerts.emails == []


def test_new_watch_emails_the_subscriber_and_records_an_alert(alerts):
    subscribe(1)
    alerts.status = "watch"
    run_weather_check()
    assert [to for to, _ in alerts.emails] == ["a@test.com"]
    assert "Freeze Watch" in alerts.emails[0][1]
    assert WeatherAlert.query.filter_by(user_id=1).count() == 1
    assert status_row().status == "watch"


def test_unchanged_status_does_not_repeat_the_alert(alerts):
    subscribe(1)
    alerts.status = "watch"
    run_weather_check()
    run_weather_check()
    run_weather_check()
    assert len(alerts.emails) == 1
    assert WeatherAlert.query.count() == 1


def test_escalation_from_watch_to_warning_alerts_again(alerts):
    subscribe(1)
    alerts.status = "watch"
    run_weather_check()
    alerts.status = "warning"
    run_weather_check()
    assert len(alerts.emails) == 2
    assert "Freeze Warning" in alerts.emails[1][1]
    assert status_row().status == "warning"


def test_no_freeze_sends_nothing(alerts):
    subscribe(1)
    alerts.status = "none"
    run_weather_check()
    assert alerts.emails == []
    assert status_row().status == "none"


def test_unknown_noaa_result_is_skipped_and_retried_next_cycle(alerts):
    subscribe(1)
    alerts.status = None
    run_weather_check()
    assert alerts.emails == [] and status_row() is None
    alerts.status = "warning"
    run_weather_check()
    assert len(alerts.emails) == 1


def test_users_who_opted_out_or_are_suspended_are_not_emailed(alerts):
    subscribe(1)
    subscribe(2, notifications_enabled=False)
    alerts.status = "warning"
    run_weather_check()
    assert [to for to, _ in alerts.emails] == ["a@test.com"]

    subscribe(2, notifications_enabled=True, is_suspended=True)
    alerts.status = "none"
    run_weather_check()
    alerts.status = "warning"
    run_weather_check()
    assert "b@test.com" not in [to for to, _ in alerts.emails]


def test_each_zip_is_checked_once_and_every_subscriber_there_is_emailed(alerts):
    subscribe(1)
    subscribe(2)
    alerts.status = "watch"
    run_weather_check()
    assert alerts.checked == [ZIP]
    assert sorted(to for to, _ in alerts.emails) == ["a@test.com", "b@test.com"]
