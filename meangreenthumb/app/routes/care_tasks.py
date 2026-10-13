"""Care task checklist (FR-09 / UC-09).

Register next to the other blueprints in create_app():

    from app.routes.care_tasks import care_tasks_bp
    app.register_blueprint(care_tasks_bp)
"""
from datetime import date, timedelta

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import CareTask, SavedPlant

care_tasks_bp = Blueprint("care_tasks", __name__, url_prefix="/my-plants")

# (description, days after the planting date). Generic starter tasks: Plant has no
# per-species care schedule yet, so every plant gets the same set.
DEFAULT_TASKS = [
    ("Water thoroughly after planting", 0),
    ("Check soil moisture; water if the top inch is dry", 3),
    ("Inspect leaves for pests and disease", 7),
    ("Apply fertilizer", 14),
    ("Prune, thin, or stake as needed", 28),
]


def ensure_default_tasks(saved_plant):
    """Create the starter checklist the first time a plant's checklist is opened.

    Returns True if tasks were created. Does nothing if the plant already has tasks.
    """
    if saved_plant.care_tasks:
        return False
    start = saved_plant.planting_date or date.today()
    for description, offset_days in DEFAULT_TASKS:
        saved_plant.care_tasks.append(
            CareTask(
                task_description=description,
                due_date=start + timedelta(days=offset_days),
            )
        )
    db.session.commit()
    return True


@care_tasks_bp.route("/<int:saved_plant_id>/tasks")
@login_required
def checklist(saved_plant_id):
    # Filtering on user_id means you can only open your own plants (404 otherwise).
    entry = SavedPlant.query.filter_by(
        saved_plant_id=saved_plant_id, user_id=current_user.user_id
    ).first_or_404()
    ensure_default_tasks(entry)

    tasks = sorted(
        entry.care_tasks,
        key=lambda t: (t.due_date is None, t.due_date, t.task_id),
    )
    return render_template(
        "care_tasks.html",
        entry=entry,
        tasks=tasks,
        done=sum(1 for t in tasks if t.completed),
        today=date.today(),
    )


@care_tasks_bp.route("/tasks/<int:task_id>/complete", methods=["POST"])
@login_required
def set_complete(task_id):
    task = (
        CareTask.query.join(SavedPlant)
        .filter(
            CareTask.task_id == task_id,
            SavedPlant.user_id == current_user.user_id,
        )
        .first_or_404()
    )
    value = request.form.get("completed")
    if value not in ("0", "1"):
        abort(400)
    task.completed = value == "1"
    db.session.commit()
    return redirect(url_for("care_tasks.checklist", saved_plant_id=task.saved_plant_id))
