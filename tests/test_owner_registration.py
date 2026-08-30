from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.owner_session_ext as owner_session
import backend.saas_ext as saas_module


def prepare(tmp_path: Path) -> TestClient:
    app_module.DB_PATH = tmp_path / "owner-registration.db"
    app_module.init_db()
    saas_module.ensure_saas_schema()
    return TestClient(app_module.app)


def test_owner_login_shows_new_registration_option(tmp_path: Path):
    client = prepare(tmp_path)

    response = client.get("/owner-login")

    assert response.status_code == 200
    assert 'href="/owner-register"' in response.text
    assert "New Registration" in response.text


def test_new_owner_registration_creates_shop_and_secure_session(tmp_path: Path):
    client = prepare(tmp_path)

    form = client.get("/owner-register")
    assert form.status_code == 200
    assert 'action="/owner/session-register"' in form.text
    assert "Create your shop account" in form.text

    response = client.post(
        "/owner/session-register",
        data={
            "business_name": "Darbar Home Pack",
            "owner_name": "Ayush",
            "phone": "9999999999",
            "address": "Indore",
            "gstin": "",
            "username": "darbar-owner",
            "password": "1234",
            "confirm_password": "1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/?handoff=")
    assert owner_session.COOKIE_NAME in response.cookies

    with app_module.db() as conn:
        owner = conn.execute(
            """
            SELECT u.username,b.name
            FROM users u JOIN businesses b ON b.id=u.business_id
            WHERE u.username=?
            """,
            ("darbar-owner",),
        ).fetchone()
    assert owner is not None
    assert owner["name"] == "Darbar Home Pack"


def test_registration_rejects_mismatched_pin_without_creating_owner(tmp_path: Path):
    client = prepare(tmp_path)

    response = client.post(
        "/owner/session-register",
        data={
            "business_name": "Wrong PIN Shop",
            "owner_name": "Owner",
            "phone": "9999999998",
            "username": "wrong-pin-owner",
            "password": "1234",
            "confirm_password": "4321",
        },
    )

    assert response.status_code == 400
    assert "Both PIN / Password entries must match." in response.text
    with app_module.db() as conn:
        assert conn.execute(
            "SELECT 1 FROM users WHERE username=?", ("wrong-pin-owner",)
        ).fetchone() is None
