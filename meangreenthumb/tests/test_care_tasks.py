"""Tests for UC-09 care task checklist. Fixtures live in conftest.py."""
from datetime import date, timedelta

from app import db
from app.models import CareTask, SavedPlant
from helpers import login


def add_plant(client, plant_id=1, planting_date=None):
    data = {"planting_date": planting_date} if planting_date else {}
    client.post(f"/my-plants/add/{plant_id}", data=data)


def entry_for(user_id, plant_id=1):
    return SavedPlant.query.filter_by(user_id=user_id, plant_id=plant_id).one()


def open_checklist(client, user_id=1, plant_id=1):
    sp = entry_for(user_id, plant_id)
    return client.get(f"/my-plants/{sp.saved_plant_id}/tasks")


def test_first_open_creates_default_tasks_offset_from_planting_date(client):
    login(client, 1)
    add_plant(client, planting_date="2026-04-01")
    assert CareTask.query.count() == 0  # nothing until the checklist is opened

    resp = open_checklist(client)
    assert resp.status_code == 200

    tasks = CareTask.query.order_by(CareTask.due_date).all()
    assert len(tasks) == 5
    assert tasks[0].due_date == date(2026, 4, 1)
    assert tasks[-1].due_date == date(2026, 4, 1) + timedelta(days=28)
    assert all(t.completed is False for t in tasks)


def test_opening_twice_does_not_duplicate_tasks(client):
    login(client, 1)
    add_plant(client)
    open_checklist(client)
    open_checklist(client)
    assert CareTask.query.count() == 5


def test_checklist_page_shows_tasks_and_progress(client):
    login(client, 1)
    add_plant(client)
    html = open_checklist(client).get_data(as_text=True)
    assert "Tomato" in html
    assert "Apply fertilizer" in html
    assert "0 of 5 done" in html


def test_mark_task_complete_and_undo(client):
    login(client, 1)
    add_plant(client)
    open_checklist(client)
    task = CareTask.query.first()

    resp = client.post(f"/my-plants/tasks/{task.task_id}/complete", data={"completed": "1"})
    assert resp.status_code == 302
    assert db.session.get(CareTask, task.task_id).completed is True
    assert "1 of 5 done" in open_checklist(client).get_data(as_text=True)

    client.post(f"/my-plants/tasks/{task.task_id}/complete", data={"completed": "0"})
    assert db.session.get(CareTask, task.task_id).completed is False


def test_complete_rejects_missing_or_bad_value(client):
    login(client, 1)
    add_plant(client)
    open_checklist(client)
    task = CareTask.query.first()
    assert client.post(f"/my-plants/tasks/{task.task_id}/complete").status_code == 400
    assert client.post(
        f"/my-plants/tasks/{task.task_id}/complete", data={"completed": "yes"}
    ).status_code == 400
    assert db.session.get(CareTask, task.task_id).completed is False


def test_past_due_incomplete_tasks_are_marked_overdue(client):
    login(client, 1)
    add_plant(client, planting_date="2020-01-01")
    html = open_checklist(client).get_data(as_text=True)
    assert html.count("(Overdue)") == 5


def test_completed_task_is_no_longer_overdue(client):
    login(client, 1)
    add_plant(client, planting_date="2020-01-01")
    open_checklist(client)
    for task in CareTask.query.all():
        client.post(f"/my-plants/tasks/{task.task_id}/complete", data={"completed": "1"})
    html = open_checklist(client).get_data(as_text=True)
    assert "(Overdue)" not in html
    assert "5 of 5 done" in html


def test_tasks_planted_today_are_not_overdue(client):
    login(client, 1)
    add_plant(client)  # defaults to today
    assert "(Overdue)" not in open_checklist(client).get_data(as_text=True)


def test_cannot_open_another_users_checklist(client):
    login(client, 1)
    add_plant(client)
    sp_id = entry_for(1).saved_plant_id
    login(client, 2)
    assert client.get(f"/my-plants/{sp_id}/tasks").status_code == 404


def test_cannot_complete_another_users_task(client):
    login(client, 1)
    add_plant(client)
    open_checklist(client)
    task = CareTask.query.first()
    login(client, 2)
    resp = client.post(f"/my-plants/tasks/{task.task_id}/complete", data={"completed": "1"})
    assert resp.status_code == 404
    assert db.session.get(CareTask, task.task_id).completed is False


def test_unknown_ids_are_404(client):
    login(client, 1)
    assert client.get("/my-plants/999/tasks").status_code == 404
    assert client.post("/my-plants/tasks/999/complete", data={"completed": "1"}).status_code == 404


def test_anonymous_gets_401(client):
    assert client.get("/my-plants/1/tasks").status_code == 401
    assert client.post("/my-plants/tasks/1/complete", data={"completed": "1"}).status_code == 401


def test_complete_is_post_only(client):
    login(client, 1)
    assert client.get("/my-plants/tasks/1/complete").status_code == 405


def test_removing_a_plant_deletes_its_tasks(client):
    login(client, 1)
    add_plant(client)
    open_checklist(client)
    assert CareTask.query.count() == 5
    client.post(f"/my-plants/{entry_for(1).saved_plant_id}/remove")
    assert CareTask.query.count() == 0


def test_my_plants_list_links_to_checklist(client):
    login(client, 1)
    add_plant(client)
    sp_id = entry_for(1).saved_plant_id
    html = client.get("/my-plants/").get_data(as_text=True)
    assert f"/my-plants/{sp_id}/tasks" in html
