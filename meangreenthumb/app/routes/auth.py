from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models import User, GrowingZone
from app.services.zone_lookup import lookup_zone_code

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        zip_code = request.form.get("zip_code", "").strip()

        # FR-03 validation: required fields + zip code format
        if not email or not password or not zip_code:
            flash("All fields are required.")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("That email is already registered. Try logging in instead.")
            return render_template("register.html")

        zone_code = lookup_zone_code(zip_code)
        if zone_code is None:
            flash("We couldn't find a growing zone for that zip code.")
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
        flash("Account created. Welcome!")
        return redirect(url_for("main.home"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user is None or not check_password_hash(user.password_hash, password):
            flash("Incorrect email or password.")
            return render_template("login.html")

        login_user(user)
        return redirect(url_for("main.home"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.home"))
