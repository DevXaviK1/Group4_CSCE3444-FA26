from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models import User, GrowingZone
from app.services.zone_lookup import lookup_zone_code

auth_bp = Blueprint("auth", __name__)

INACTIVITY_TIMEOUT_MINUTES = 30
MIN_PASSWORD_LENGTH = 6


@auth_bp.before_app_request
def enforce_session_timeout():
    """UC-03 Alt Flow 7a & NFR 6.2: Log out users after 30 minutes of inactivity."""
    if not current_user.is_authenticated:
        return None

    now_ts = datetime.now(timezone.utc).timestamp()
    last_active = session.get("last_active")

    if last_active is not None:
        elapsed_seconds = now_ts - float(last_active)
        if elapsed_seconds > INACTIVITY_TIMEOUT_MINUTES * 60:
            logout_user()
            session.pop("last_active", None)
            flash("Your session has expired due to 30 minutes of inactivity. Please log in again.", "warning")
            return redirect(url_for("auth.login"))

    session.permanent = True
    session["last_active"] = now_ts
    return None


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        zip_code = request.form.get("zip_code", "").strip()

        # UC-03 Alt Flow 4a: required fields, password requirements, valid zip code
        if not email or not password or not zip_code:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.", "error")
            return render_template("register.html")

        # UC-03 Alt Flow 4b: duplicate email check
        if User.query.filter_by(email=email).first():
            flash("That email is already registered. Try logging in instead.", "error")
            return render_template("register.html")

        zone_code = lookup_zone_code(zip_code)
        if zone_code is None:
            flash("We couldn't find a growing zone for that zip code.", "error")
            return render_template("register.html")

        zone = GrowingZone.query.filter_by(zone_code=zone_code).first()
        if zone is None:
            zone = GrowingZone(zone_code=zone_code)
            db.session.add(zone)
            db.session.flush()  # get zone.zone_id before commit

        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            zip_code=zip_code,
            zone_id=zone.zone_id,
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        session.permanent = True
        session["last_active"] = datetime.now(timezone.utc).timestamp()
        session["zone_code"] = zone_code
        session["zip_code"] = zip_code
        flash("Account created. Welcome!", "success")
        return redirect(url_for("main.home"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Incorrect email or password.", "error")
            return render_template("login.html")

        user = User.query.filter_by(email=email).first()
        if user is None or not check_password_hash(user.password_hash, password):
            flash("Incorrect email or password.", "error")
            return render_template("login.html")

        # Block login if the account has been suspended by an admin (FR-12 / UC-12)
        if user.is_suspended:
            flash(
                "Your account has been suspended. Please contact an administrator.",
                "error",
            )
            return render_template("login.html")

        login_user(user)
        session.permanent = True
        session["last_active"] = datetime.now(timezone.utc).timestamp()
        if user.growing_zone:
            session["zone_code"] = user.growing_zone.zone_code
        if user.zip_code:
            session["zip_code"] = user.zip_code
        return redirect(url_for("main.home"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("last_active", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))
