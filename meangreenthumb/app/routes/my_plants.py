"""My Plants (FR-08 / UC-08): a registered user's personal garden list.

Register in the app factory / app/__init__.py:

    from app.my_plants import my_plants_bp
    app.register_blueprint(my_plants_bp)
"""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Plant, SavedPlant

my_plants_bp = Blueprint("my_plants", __name__, url_prefix="/my-plants")


def _redirect_back():
    """Go back to the page the form came from (hidden 'next' field).

    Only same-site relative paths are accepted, so the field can't be used as an
    open redirect. Falls back to the My Plants list.
    """
    nxt = request.form.get("next", "")
    if nxt.startswith("/") and not nxt.startswith("//") and "\\" not in nxt:
        return redirect(nxt)
    return redirect(url_for("my_plants.index"))


@my_plants_bp.route("/")
@login_required
def index():
    entries = (
        SavedPlant.query.filter_by(user_id=current_user.user_id)
        .join(Plant)
        .order_by(Plant.name)
        .all()
    )
    return render_template("my_plants.html", entries=entries)


@my_plants_bp.route("/add/<int:plant_id>", methods=["POST"])
@login_required
def add(plant_id):
    plant = db.session.get(Plant, plant_id)
    if plant is None:
        abort(404)

    # UC-08 alt flow 2a: already saved -> notify, don't duplicate.
    already = SavedPlant.query.filter_by(
        user_id=current_user.user_id, plant_id=plant.plant_id
    ).first()
    if already:
        flash(f"{plant.name} is already in My Plants.", "info")
        return _redirect_back()

    # Optional planting date (YYYY-MM-DD); defaults to today. UC-09 builds its
    # task timeline from this value.
    raw_date = (request.form.get("planting_date") or "").strip()
    if raw_date:
        try:
            planting_date = date.fromisoformat(raw_date)
        except ValueError:
            flash("Planting date must be in YYYY-MM-DD format.", "error")
            return _redirect_back()
    else:
        planting_date = date.today()

    db.session.add(
        SavedPlant(
            user_id=current_user.user_id,
            plant_id=plant.plant_id,
            planting_date=planting_date,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:  # two requests raced, or a unique constraint exists
        db.session.rollback()
        flash(f"{plant.name} is already in My Plants.", "info")
        return _redirect_back()

    flash(f"{plant.name} added to My Plants.", "success")
    return _redirect_back()


@my_plants_bp.route("/<int:saved_plant_id>/remove", methods=["POST"])
@login_required
def remove(saved_plant_id):
    # Filtering on user_id means you can only remove your own entries (404 otherwise).
    entry = SavedPlant.query.filter_by(
        saved_plant_id=saved_plant_id, user_id=current_user.user_id
    ).first_or_404()
    name = entry.plant.name
    db.session.delete(entry)  # cascades to its CareTasks
    db.session.commit()
    flash(f"{name} removed from My Plants.", "success")
    return redirect(url_for("my_plants.index"))
