from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.order_portal_ext as order_module


def owner_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def customer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def setup_business(client: TestClient) -> str:
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


def test_customer_order_uses_last_bill_then_fixed_rate_and_converts_to_sale(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "orders.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    client = TestClient(app_module.app)
    owner_token = setup_business(client)
    headers = owner_headers(owner_token)

    party_response = client.post(
        "/api/parties",
        headers=headers,
        json={
            "name": "Ram Stores",
            "type": "customer",
            "phone": "9876543210",
            "opening_balance": 0,
        },
    )
    assert party_response.status_code == 200, party_response.text
    party_id = party_response.json()["id"]

    item_response = client.post(
        "/api/items",
        headers=headers,
        json={
            "name": "Shakar Powder",
            "sku": "SUGAR-1",
            "unit": "kg",
            "sale_price": 45,
            "purchase_price": 35,
            "stock": 100,
            "gst_rate": 0,
        },
    )
    assert item_response.status_code == 200, item_response.text
    item_id = item_response.json()["id"]

    previous_sale = client.post(
        "/api/sales",
        headers=headers,
        json={
            "party_id": party_id,
            "paid": 42,
            "payment_mode": "cash",
            "items": [{"item_id": item_id, "qty": 1, "rate": 42, "gst_rate": 0}],
        },
    )
    assert previous_sale.status_code == 200, previous_sale.text

    access = client.post(
        "/api/customer-access",
        headers=headers,
        json={"party_id": party_id, "phone": "9876543210", "pin": "5678", "is_active": True},
    )
    assert access.status_code == 200, access.text

    login = client.post("/api/customer/login", json={"phone": "98765 43210", "pin": "5678"})
    assert login.status_code == 200, login.text
    customer_token = login.json()["token"]
    customer_auth = customer_headers(customer_token)

    catalog = client.get("/api/customer/catalog", headers=customer_auth)
    assert catalog.status_code == 200, catalog.text
    sugar = next(row for row in catalog.json() if row["id"] == item_id)
    assert sugar["rate"] == 42
    assert sugar["rate_source"] == "last_bill"

    customer_order = client.post(
        "/api/customer/orders",
        headers=customer_auth,
        json={"items": [{"item_id": item_id, "qty": 5, "rate": 1}]},
    )
    assert customer_order.status_code == 200, customer_order.text
    order = customer_order.json()
    assert order["source"] == "customer"
    assert order["items"][0]["rate"] == 42
    assert order["total"] == 210

    fixed = client.post(
        "/api/customer-prices",
        headers=headers,
        json={"party_id": party_id, "item_id": item_id, "rate": 40},
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["rate_source"] == "fixed"

    catalog_after_fixed = client.get("/api/customer/catalog", headers=customer_auth)
    sugar_after_fixed = next(row for row in catalog_after_fixed.json() if row["id"] == item_id)
    assert sugar_after_fixed["rate"] == 40
    assert sugar_after_fixed["rate_source"] == "fixed"

    second_order = client.post(
        "/api/orders",
        headers=headers,
        json={"party_id": party_id, "items": [{"item_id": item_id, "qty": 2}]},
    )
    assert second_order.status_code == 200, second_order.text
    second_order_id = second_order.json()["id"]
    assert second_order.json()["items"][0]["rate"] == 40

    conversion = client.post(f"/api/orders/{second_order_id}/convert-to-sale", headers=headers)
    assert conversion.status_code == 200, conversion.text
    converted = conversion.json()
    assert converted["order"]["status"] == "converted"
    assert converted["sale"]["party_id"] == party_id
    assert converted["sale"]["items"][0]["rate"] == 40

    duplicate_conversion = client.post(f"/api/orders/{second_order_id}/convert-to-sale", headers=headers)
    assert duplicate_conversion.status_code == 409
