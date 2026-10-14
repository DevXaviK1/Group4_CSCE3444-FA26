"""UC-12 / FR-12: Account Suspension and Reactivation."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app import db
from app.models import Tip, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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