"""Demo data for rehearsals and the final demo.

    flask --app run seed-demo            # add the demo accounts and data
    flask --app run seed-demo --reset    # wipe the database first

This is a command-line tool only. There is no web route for it, so nobody can
become an administrator through the web interface (SRS 6.2).

The demo password comes from the DEMO_PASSWORD environment variable and
defaults to a simple local value. On Render (where the RENDER variable is set)
the command refuses to run with that default, because the repository is public
and the live site must never have a guessable admin password.
"""
import os
from datetime import date

import click
from flask import current_app
from werkzeug.security import generate_password_hash

from app import db
from app.models import GrowingZone, SavedPlant, Tip, User

ADMIN_EMAIL = "admin@test.com"
USER_EMAIL = "user@test.com"
DEFAULT_PASSWORD = "12345678"  # local demos only; see the module docstring
DEMO_ZIP = "76226"
DEMO_ZONE = "8a"
DEMO_PLANT = "Garlic"

DEMO_TIPS = [
    "Mulch your beds before the first freeze; it keeps the soil temperature steady.",
    "Water early in the morning so leaves dry before the evening and stay disease free.",
    "Plant garlic in fall; it needs the winter chill to form full bulbs.",
]


def _get_or_create_user(email, password, is_admin, zone):
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(email=email, zip_code=DEMO_ZIP, zone_id=zone.zone_id)
        db.session.add(user)
    user.password_hash = generate_password_hash(password)
    user.is_admin = is_admin
    user.is_suspended = False
    user.zip_code = DEMO_ZIP
    user.zone_id = zone.zone_id
    db.session.flush()
    return user


def run_seed(password):
    """Create or refresh the demo data. Safe to run more than once."""
    from app.routes.care_tasks import ensure_default_tasks
    from app.routes.plants import ensure_seed_catalog

    ensure_seed_catalog()
    zone = GrowingZone.query.filter_by(zone_code=DEMO_ZONE).first()
    if zone is None:
        zone = GrowingZone(zone_code=DEMO_ZONE)
        db.session.add(zone)
        db.session.flush()

    _get_or_create_user(ADMIN_EMAIL, password, True, zone)
    user = _get_or_create_user(USER_EMAIL, password, False, zone)

    from app.models import Plant

    plant = Plant.query.filter_by(name=DEMO_PLANT).first()
    if plant is not None and not SavedPlant.query.filter_by(
        user_id=user.user_id, plant_id=plant.plant_id
    ).first():
        entry = SavedPlant(
            user_id=user.user_id, plant_id=plant.plant_id, planting_date=date.today()
        )
        db.session.add(entry)
        db.session.flush()
        ensure_default_tasks(entry)
        if entry.care_tasks:
            first = sorted(entry.care_tasks, key=lambda t: t.due_date)[0]
            first.completed = True

    for text in DEMO_TIPS:
        if not Tip.query.filter_by(text=text).first():
            db.session.add(Tip(user_id=user.user_id, zone_id=zone.zone_id, text=text))
    db.session.commit()


@click.command("seed-demo")
@click.option("--reset", is_flag=True, help="Delete all data first.")
def seed_demo(reset):
    """Load the demo accounts, plants, a saved plant and a few tips."""
    password = os.environ.get("DEMO_PASSWORD") or DEFAULT_PASSWORD
    if os.environ.get("RENDER") and password == DEFAULT_PASSWORD:
        raise click.ClickException(
            "Refusing to seed a hosted site with the default demo password. "
            "Set DEMO_PASSWORD to a private value first."
        )
    if reset:
        db.drop_all()
        db.create_all()
    run_seed(password)
    click.echo(f"Demo data ready. Admin: {ADMIN_EMAIL}   User: {USER_EMAIL}")
