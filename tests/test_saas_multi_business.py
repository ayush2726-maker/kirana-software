from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.order_portal_ext as order_module
import backend.saas_ext as saas_module


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signup(client: TestClient, name: str, username: str, phone: str) -> dict:
    response = client.post(
        "/api/saas/register-business",
        json={
            "business_name": name,
            "owner_name": f"{name} Owner",
            "phone": phone,
            "address": "Indore",
            "username": username,
            "password": "1234",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_two_businesses_have_isolated_data_and_unique_customer_links(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "saas-multi.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    saas_module.ensure_saas_schema()
    client = TestClient(app_module.app)

    first = signup(client, "Kishore Traders", "kishore-owner", "9999999991")
    second = signup(client, "Darbar Foods", "darbar-owner", "9999999992")

    assert first["business_id"] != second["business_id"]
    assert first["slug"] != second["slug"]
    assert first["customer_order_path"].endswith(first["slug"])
    assert second["customer_order_path"].endswith(second["slug"])
    assert first["trial_days"] == saas_module.TRIAL_DAYS

    first_headers = auth(first["token"])
    second_headers = auth(second["token"])

    first_item = client.post(
        "/api/items",
        headers=first_headers,
        json={"name": "Shakar Powder", "sku": "SUGAR-A", "sale_price": 42, "stock": 100},
    )
    second_item = client.post(
        "/api/items",
        headers=second_headers,
        json={"name": "Shakar Powder", "sku": "SUGAR-B", "sale_price": 50, "stock": 200},
    )
    assert first_item.status_code == 200, first_item.text
    assert second_item.status_code == 200, second_item.text

    first_items = client.get("/api/items", headers=first_headers)
    second_items = client.get("/api/items", headers=second_headers)
    assert [row["sku"] for row in first_items.json()] == ["SUGAR-A"]
    assert [row["sku"] for row in second_items.json()] == ["SUGAR-B"]

    shared_phone = "9876543210"
    first_party = client.post(
        "/api/parties",
        headers=first_headers,
        json={"name": "Ram First", "type": "customer", "phone": shared_phone},
    )
    second_party = client.post(
        "/api/parties",
        headers=second_headers,
        json={"name": "Ram Second", "type": "customer", "phone": shared_phone},
    )
    assert first_party.status_code == 200
    assert second_party.status_code == 200

    first_access = client.post(
        "/api/customer-access",
        headers=first_headers,
        json={"party_id": first_party.json()["id"], "phone": shared_phone, "pin": "1111", "is_active": True},
    )
    second_access = client.post(
        "/api/customer-access",
        headers=second_headers,
        json={"party_id": second_party.json()["id"], "phone": shared_phone, "pin": "2222", "is_active": True},
    )
    assert first_access.status_code == 200, first_access.text
    assert second_access.status_code == 200, second_access.text

    first_login = client.post(
        "/api/customer/login",
        json={"phone": shared_phone, "pin": "1111", "shop_slug": first["slug"]},
    )
    second_login = client.post(
        "/api/customer/login",
        json={"phone": shared_phone, "pin": "2222", "shop_slug": second["slug"]},
    )
    assert first_login.status_code == 200, first_login.text
    assert second_login.status_code == 200, second_login.text
    assert first_login.json()["business_name"] == "Kishore Traders"
    assert second_login.json()["business_name"] == "Darbar Foods"

    ambiguous = client.post(
        "/api/customer/login",
        json={"phone": shared_phone, "pin": "1111"},
    )
    assert ambiguous.status_code == 409


def test_business_signup_rejects_duplicate_username_and_exposes_trial_plan(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "saas-signup.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    saas_module.ensure_saas_schema()
    client = TestClient(app_module.app)

    first = signup(client, "Kishore Traders", "same-owner", "9999999991")
    duplicate = client.post(
        "/api/saas/register-business",
        json={
            "business_name": "Darbar Foods",
            "owner_name": "Owner",
            "phone": "9999999992",
            "username": "same-owner",
            "password": "1234",
        },
    )
    assert duplicate.status_code == 409

    plan = client.get("/api/saas/me", headers=auth(first["token"]))
    assert plan.status_code == 200, plan.text
    payload = plan.json()
    assert payload["subscription_status"] == "trial"
    assert payload["plan"] == "trial"
    assert payload["days_left"] in {saas_module.TRIAL_DAYS, saas_module.TRIAL_DAYS - 1}
