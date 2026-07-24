from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.password_change_ext  # noqa: F401


def test_change_password_keeps_current_session_and_revokes_other_sessions(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "password-change.db"
    app_module.init_db()
    client = TestClient(app_module.app)

    setup = client.post(
        "/api/setup",
        json={
            "business_name": "Kishore Traders",
            "owner_name": "Ayush",
            "username": "admin",
            "password": "1234",
        },
    )
    assert setup.status_code == 200, setup.text
    current_token = setup.json()["token"]

    second_login = client.post("/api/login", json={"username": "admin", "password": "1234"})
    assert second_login.status_code == 200, second_login.text
    second_token = second_login.json()["token"]

    response = client.post(
        "/api/account/change-password",
        headers={"Authorization": f"Bearer {current_token}"},
        json={
            "current_password": "1234",
            "new_password": "5678",
            "confirm_password": "5678",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["other_sessions_logged_out"] == 1

    # Current phone/browser stays signed in.
    assert client.get("/api/me", headers={"Authorization": f"Bearer {current_token}"}).status_code == 200
    # Other phone/browser session is revoked.
    assert client.get("/api/me", headers={"Authorization": f"Bearer {second_token}"}).status_code == 401
    # Old password no longer works; new one does.
    assert client.post("/api/login", json={"username": "admin", "password": "1234"}).status_code == 401
    assert client.post("/api/login", json={"username": "admin", "password": "5678"}).status_code == 200


def test_change_password_rejects_wrong_current_password(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "password-change-wrong.db"
    app_module.init_db()
    client = TestClient(app_module.app)
    setup = client.post(
        "/api/setup",
        json={
            "business_name": "Kishore Traders",
            "owner_name": "Ayush",
            "username": "admin",
            "password": "1234",
        },
    )
    token = setup.json()["token"]

    response = client.post(
        "/api/account/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "0000",
            "new_password": "5678",
            "confirm_password": "5678",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"
