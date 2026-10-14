from flask import g


def login(client, user_id):
    # The fixture keeps one app context open for the whole test, so Flask-Login's
    # cached user in `g` would leak between requests. Clear it when switching users.
    g.pop("_login_user", None)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def flashes(client):
    with client.session_transaction() as sess:
        return [(cat, msg) for cat, msg in sess.get("_flashes", [])]
