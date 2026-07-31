from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.customer_self_register_ext as register_module
import backend.order_portal_ext as order_module


def setup_owner(client: TestClient) -> str:
    response = client.post(
        "/api/setup",
        json={
            "business_name": "Kishore Traders",
            "owner_name": "Ayush",
            "username": "admin",
            "password": "1234",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_existing_customer_can_register_with_saved_mobile_and_auto_login(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "customer-register.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    client = TestClient(app_module.app)
    owner_token = setup_owner(client)
    headers = {"Authorization": f"Bearer {owner_token}"}

    party = client.post(
        "/api/parties",
        headers=headers,
        json={
            "name": "Ram Stores",
            "type": "customer",
            "phone": "+91 98765-43210",
            "opening_balance": 1200,
        },
    )
    assert party.status_code == 200, party.text

    registration = client.post(
        "/api/customer/register",
        json={
            "phone": "9876543210",
            "pin": "5678",
            "confirm_pin": "5678",
        },
    )
    assert registration.status_code == 200, registration.text
    result = registration.json()
    assert result["registered"] is True
    assert result["customer"]["party_name"] == "Ram Stores"

    customer_headers = {"Authorization": f"Bearer {result['token']}"}
    me = client.get("/api/customer/me", headers=customer_headers)
    assert me.status_code == 200, me.text
    assert me.json()["party_name"] == "Ram Stores"
    assert me.json()["balance"] == 1200

    login = client.post(
        "/api/customer/login",
        json={"phone": "98765 43210", "pin": "5678"},
    )
    assert login.status_code == 200, login.text

    duplicate = client.post(
        "/api/customer/register",
        json={
            "phone": "9876543210",
            "pin": "9999",
            "confirm_pin": "9999",
        },
    )
    assert duplicate.status_code == 409
    assert "pehle se registered" in duplicate.json()["detail"]


def test_registration_rejects_unknown_and_duplicate_customer_phone(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "customer-register-errors.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    client = TestClient(app_module.app)
    owner_token = setup_owner(client)
    headers = {"Authorization": f"Bearer {owner_token}"}

    unknown = client.post(
        "/api/customer/register",
        json={"phone": "9999999999", "pin": "5678", "confirm_pin": "5678"},
    )
    assert unknown.status_code == 404

    for name in ("Ram Stores", "Ram Stores Old"):
        response = client.post(
            "/api/parties",
            headers=headers,
            json={
                "name": name,
                "type": "customer",
                "phone": "9876543210",
                "opening_balance": 0,
            },
        )
        assert response.status_code == 200, response.text

    duplicate_party = client.post(
        "/api/customer/register",
        json={"phone": "9876543210", "pin": "5678", "confirm_pin": "5678"},
    )
    assert duplicate_party.status_code == 409
    assert "ek se zyada customer" in duplicate_party.json()["detail"]


def test_registration_page_contains_login_and_register_modes(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "customer-register-page.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    client = TestClient(app_module.app)

    response = client.get("/customer")
    assert response.status_code == 200
    assert 'id="customer-show-register"' in response.text
    assert 'id="customer-register-form"' in response.text
    assert "/customer-self-register.js?v=061" in response.text
