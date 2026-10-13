"""Community tips (FR-07 / UC-07).

Register next to the other blueprints in create_app():

    from app.routes.tips import tips_bp
    app.register_blueprint(tips_bp)
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import GrowingZone, Tip

tips_bp = Blueprint("tips", __name__, url_prefix="/tips")

MAX_TIP_LENGTH = 500
FEED_LIMIT = 50


@tips_bp.route("/")
@login_required
def feed():
    # The feed is platform-wide: every registered user sees the latest tips from
    # all zones. Each tip shows the zone it was posted from.
    tips = (
        Tip.query.order_by(Tip.timestamp.desc(), Tip.tip_id.desc())
        .limit(FEED_LIMIT)
        .all()
    )
    zone_codes = {z.zone_id: z.zone_code for z in GrowingZone.query.all()}
    return render_template(
        "tips.html",
        zone=current_user.growing_zone,
        tips=tips,
        zone_codes=zone_codes,
        max_length=MAX_TIP_LENGTH,
    )


@tips_bp.route("/", methods=["POST"])
@login_required
def create():
    # A tip is tagged with the poster's own growing zone. Everyone can read it.
    if current_user.zone_id is None:
        flash("Set your growing zone before posting a tip.", "error")
        return redirect(url_for("tips.feed"))

    text = (request.form.get("text") or "").strip()
    if not text:  # UC-07: empty tips are rejected
        flash("A tip can't be empty.", "error")
        return redirect(url_for("tips.feed"))
    if len(text) > MAX_TIP_LENGTH:
        flash(f"Tips can be at most {MAX_TIP_LENGTH} characters.", "error")
        return redirect(url_for("tips.feed"))

    db.session.add(
        Tip(user_id=current_user.user_id, zone_id=current_user.zone_id, text=text)
    )
    db.session.commit()
    flash("Your tip was posted.", "success")
    return redirect(url_for("tips.feed"))
