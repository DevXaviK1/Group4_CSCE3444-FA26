"""Admin routes:
- UC-11 / FR-11: Plant Catalog Management (Sudip)
- UC-12 / FR-12: Account Suspension and Reactivation (Xavier)
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app import db
from app.models import GrowingZone, Plant, SavedPlant, Tip, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

STANDARD_ZONES = [
    "3a", "3b", "4a", "4b", "5a", "5b", "6a", "6b",
    "7a", "7b", "8a", "8b", "9a", "9b", "10a", "10b", "11a", "11b",
]


def _ensure_standard_zones():
    existing = {z.zone_code: z for z in GrowingZone.query.all()}
    for code in STANDARD_ZONES:
        if code not in existing:
            z = GrowingZone(zone_code=code)
            db.session.add(z)
            existing[code] = z
    db.session.commit()
    return GrowingZone.query.order_by(GrowingZone.zone_code).all()


# --------------------------------------------------------- UC-11 / FR-11 ----
@admin_bp.route("/plants", methods=["GET"])
@login_required
def plant_catalog():
    if not current_user.is_admin:
        flash("Unauthorized: Administrator access required.", "danger")
        return redirect(url_for("main.home"))

    all_zones = _ensure_standard_zones()
    plants = Plant.query.order_by(Plant.name).all()
    edit_id = request.args.get("edit", type=int)
    edit_plant = db.session.get(Plant, edit_id) if edit_id else None

    return render_template(
        "admin_plants.html",
        plants=plants,
        all_zones=all_zones,
        edit_plant=edit_plant,
    )


@admin_bp.route("/plants/add", methods=["POST"])
@login_required
def add_plant():
    if not current_user.is_admin:
        flash("Unauthorized: Administrator access required.", "danger")
        return redirect(url_for("main.home"))

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    planting_time = (request.form.get("recommended_planting_time") or "").strip()
    zone_codes = [z.strip() for z in request.form.getlist("zones") if z.strip()]

    # UC-11 Alt Flow 5a: required fields and at least one growing zone
    if not name or not description or not planting_time or not zone_codes:
        flash("All fields (name, description, planting time, and at least one growing zone) are required.", "danger")
        return redirect(url_for("admin.plant_catalog"))

    # UC-11 Alt Flow 5b: duplicate plant name check (case-insensitive)
    existing = Plant.query.filter(db.func.lower(Plant.name) == name.lower()).first()
    if existing:
        flash(f"A plant named '{name}' already exists in the catalog.", "danger")
        return redirect(url_for("admin.plant_catalog"))

    plant = Plant(
        name=name,
        description=description,
        recommended_planting_time=planting_time,
    )
    db.session.add(plant)
    for code in zone_codes:
        zone = GrowingZone.query.filter_by(zone_code=code).first()
        if zone is None:
            zone = GrowingZone(zone_code=code)
            db.session.add(zone)
            db.session.flush()
        plant.zones.append(zone)
    db.session.commit()
    flash(f"Plant '{plant.name}' added to the catalog.", "success")
    return redirect(url_for("admin.plant_catalog"))


@admin_bp.route("/plants/<int:plant_id>/edit", methods=["POST"])
@login_required
def edit_plant(plant_id: int):
    if not current_user.is_admin:
        flash("Unauthorized: Administrator access required.", "danger")
        return redirect(url_for("main.home"))

    plant = db.session.get(Plant, plant_id)
    if plant is None:
        abort(404)

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    planting_time = (request.form.get("recommended_planting_time") or "").strip()
    zone_codes = [z.strip() for z in request.form.getlist("zones") if z.strip()]

    # UC-11 Alt Flow 5a: required fields and at least one growing zone
    if not name or not description or not planting_time or not zone_codes:
        flash("All fields (name, description, planting time, and at least one growing zone) are required.", "danger")
        return redirect(url_for("admin.plant_catalog", edit=plant.plant_id))

    # UC-11 Alt Flow 5b: duplicate plant name check excluding current plant
    duplicate = (
        Plant.query.filter(
            db.func.lower(Plant.name) == name.lower(),
            Plant.plant_id != plant.plant_id,
        ).first()
    )
    if duplicate:
        flash(f"A plant named '{name}' already exists in the catalog.", "danger")
        return redirect(url_for("admin.plant_catalog", edit=plant.plant_id))

    plant.name = name
    plant.description = description
    plant.recommended_planting_time = planting_time

    new_zones = []
    for code in zone_codes:
        zone = GrowingZone.query.filter_by(zone_code=code).first()
        if zone is None:
            zone = GrowingZone(zone_code=code)
            db.session.add(zone)
            db.session.flush()
        new_zones.append(zone)
    plant.zones = new_zones

    db.session.commit()
    flash(f"Plant '{plant.name}' updated.", "success")
    return redirect(url_for("admin.plant_catalog"))


@admin_bp.route("/plants/<int:plant_id>/remove", methods=["POST"])
@login_required
def remove_plant(plant_id: int):
    if not current_user.is_admin:
        flash("Unauthorized: Administrator access required.", "danger")
        return redirect(url_for("main.home"))

    plant = db.session.get(Plant, plant_id)
    if plant is None:
        abort(404)

    # UC-11 Alt Flow 3a: Do not remove if saved in any user's My Plants list
    in_use = SavedPlant.query.filter_by(plant_id=plant.plant_id).first()
    if in_use is not None:
        flash(
            f"Cannot remove '{plant.name}' because it is currently saved in one or more users' My Plants lists.",
            "danger",
        )
        return redirect(url_for("admin.plant_catalog"))

    name = plant.name
    plant.zones = []
    db.session.delete(plant)
    db.session.commit()
    flash(f"Plant '{name}' removed from the catalog.", "success")
    return redirect(url_for("admin.plant_catalog"))


# --------------------------------------------------------- UC-12 / FR-12 ----
@admin_bp.route("/users", methods=["GET"])
@login_required
def user_management():
    if not current_user.is_admin:
        flash("Unauthorized: Administrator access required.", "danger")
        return redirect(url_for("main.weather_forecast"))

    search = request.args.get("search", "").strip()
    query = User.query
    if search:
        query = query.filter(User.email.ilike(f"%{search}%"))
    users = query.all()

    return render_template("user_management.html", users=users, search=search)


@admin_bp.route("/users/<int:user_id>/suspend", methods=["POST"])
@login_required
def suspend_user(user_id: int):
    if not current_user.is_admin:
        flash("Unauthorized: Administrator access required.", "danger")
        return redirect(url_for("main.weather_forecast"))

    target_user = db.session.get(User, user_id)
    if not target_user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.user_management"))

        # Alternative flow 3b: Cannot suspend own account or another administrator
    if target_user.user_id == current_user.user_id or target_user.is_admin:
        flash("Action rejected: Cannot suspend your own account or another administrator.", "danger")
        return redirect(url_for("admin.user_management"))

    remove_tips = request.form.get("remove_tips") == "yes"

    target_user.is_suspended = True

        # Main flow 4-6: Cascade delete tips if admin confirmed
    if remove_tips:
        Tip.query.filter_by(user_id=target_user.user_id).delete()

    db.session.commit()
    flash(f"Account {target_user.email} suspended.", "success")
    return redirect(url_for("admin.user_management"))


@admin_bp.route("/users/<int:user_id>/reactivate", methods=["POST"])
@login_required
def reactivate_user(user_id: int):
    if not current_user.is_admin:
        flash("Unauthorized: Administrator access required.", "danger")
        return redirect(url_for("main.weather_forecast"))

    target_user = db.session.get(User, user_id)
    if not target_user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.user_management"))

    target_user.is_suspended = False
    db.session.commit()
    flash(f"Account {target_user.email} reactivated.", "success")
    return redirect(url_for("admin.user_management"))
