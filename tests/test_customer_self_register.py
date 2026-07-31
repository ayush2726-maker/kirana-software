from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.customer_self_register_ext as register_module
import backend.order_portal_ext as order_module
import backend.saas_ext as saas_module


def setup_owner(client: TestClient) -> str:
    response = client.post(
        "/api/setup",
        json={
            "business_name": "Kishore Traders",
            "owner_name": "Ayush",
            "phone": "9999999999",
            "username": "admin",
            "password": "1234",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def prepare(tmp_path: Path, name: str) -> tuple[TestClient, str, dict[str, str], str]:
    app_module.DB_PATH = tmp_path / name
    app_module.init_db()
    order_module.ensure_order_schema()
    saas_module.ensure_saas_schema()
    register_module.ensure_customer_otp_schema()
    client = TestClient(app_module.app)
    owner_token = setup_owner(client)
    headers = {"Authorization": f"Bearer {owner_token}"}
    shop = client.get("/api/saas/me", headers=headers)
    assert shop.status_code == 200, shop.text
    return client, owner_token, headers, shop.json()["slug"]


def test_existing_customer_registers_only_after_owner_sends_whatsapp_otp(tmp_path: Path):
    client, _, headers, slug = prepare(tmp_path, "customer-otp-register.db")
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

    request = client.post(
        "/api/customer/register/request-otp",
        json={"phone": "9876543210", "shop_slug": slug},
    )
    assert request.status_code == 200, request.text
    assert request.json()["masked_phone"] == "******3210"
    assert "WhatsApp" in request.json()["message"]

    pending = client.get("/api/customer/otp-requests", headers=headers)
    assert pending.status_code == 200, pending.text
    rows = pending.json()
    assert len(rows) == 1
    assert rows[0]["party_name"] == "Ram Stores"
    assert len(rows[0]["otp_code"]) == 6
    assert rows[0]["otp_code"].isdigit()
    assert rows[0]["whatsapp_url"].startswith("https://wa.me/919876543210")

    wrong = client.post(
        "/api/customer/register/verify-otp",
        json={
            "phone": "9876543210",
            "shop_slug": slug,
            "otp": "000000" if rows[0]["otp_code"] != "000000" else "111111",
            "pin": "5678",
            "confirm_pin": "5678",
        },
    )
    assert wrong.status_code == 400

    verify = client.post(
        "/api/customer/register/verify-otp",
        json={
            "phone": "9876543210",
            "shop_slug": slug,
            "otp": rows[0]["otp_code"],
            "pin": "5678",
            "confirm_pin": "5678",
        },
    )
    assert verify.status_code == 200, verify.text
    result = verify.json()
    assert result["registered"] is True
    assert result["customer"]["party_name"] == "Ram Stores"

    customer_headers = {"Authorization": f"Bearer {result['token']}"}
    me = client.get("/api/customer/me", headers=customer_headers)
    assert me.status_code == 200, me.text
    assert me.json()["party_name"] == "Ram Stores"
    assert me.json()["balance"] == 1200

    login = client.post(
        "/api/customer/login",
        json={"phone": "98765 43210", "pin": "5678", "shop_slug": slug},
    )
    assert login.status_code == 200, login.text

    duplicate = client.post(
        "/api/customer/register/request-otp",
        json={"phone": "9876543210", "shop_slug": slug},
    )
    assert duplicate.status_code == 409
    assert "pehle se registered" in duplicate.json()["detail"]


def test_otp_registration_rejects_unknown_duplicate_and_wrong_shop(tmp_path: Path):
    client, _, headers, slug = prepare(tmp_path, "customer-otp-errors.db")

    unknown = client.post(
        "/api/customer/register/request-otp",
        json={"phone": "8888888888", "shop_slug": slug},
    )
    assert unknown.status_code == 404

    wrong_shop = client.post(
        "/api/customer/register/request-otp",
        json={"phone": "8888888888", "shop_slug": "missing-shop"},
    )
    assert wrong_shop.status_code == 404

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
        "/api/customer/register/request-otp",
        json={"phone": "9876543210", "shop_slug": slug},
    )
    assert duplicate_party.status_code == 409
    assert "ek se zyada customer" in duplicate_party.json()["detail"]


def test_registration_page_contains_whatsapp_otp_steps(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "customer-otp-page.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    saas_module.ensure_saas_schema()
    register_module.ensure_customer_otp_schema()
    client = TestClient(app_module.app)

    response = client.get("/customer?shop=kishore-traders")
    assert response.status_code == 200
    assert 'id="customer-show-register"' in response.text
    assert 'id="customer-otp-request-form"' in response.text
    assert 'id="customer-otp-verify-form"' in response.text
    assert "/customer-self-register.js?v=062" in response.text
