from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.payment_link_ext as payment_ext


def build_client(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "test-payment-link.db"
    app_module.init_db()
    payment_ext.init_payment_linking()
    client = TestClient(app_module.app)
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
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    client.get("/api/accounts", headers=headers)
    return client, headers


def create_item(client, headers):
    response = client.post(
        "/api/items",
        headers=headers,
        json={
            "name": "Test Item",
            "sku": "TEST-1",
            "unit": "pcs",
            "stock": 100,
            "sale_price": 100,
            "purchase_price": 80,
            "gst_rate": 0,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_party(client, headers, name, party_type):
    response = client.post(
        "/api/parties",
        headers=headers,
        json={
            "name": name,
            "type": party_type,
            "phone": "9999999999",
            "opening_balance": 0,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_payment_in_lists_sale_bill_and_updates_invoice_due(tmp_path):
    client, headers = build_client(tmp_path)
    item = create_item(client, headers)
    customer = create_party(client, headers, "Customer A", "customer")

    sale_response = client.post(
        "/api/sales",
        headers=headers,
        json={
            "party_id": customer["id"],
            "invoice_date": "2026-07-24",
            "paid": 0,
            "payment_mode": "credit",
            "items": [{"item_id": item["id"], "qty": 1, "rate": 100, "gst_rate": 0}],
        },
    )
    assert sale_response.status_code == 200, sale_response.text
    sale = sale_response.json()
    assert sale["due"] == 100

    open_response = client.get(
        f"/api/parties/{customer['id']}/open-bills?payment_type=received",
        headers=headers,
    )
    assert open_response.status_code == 200, open_response.text
    open_data = open_response.json()
    assert open_data["bill_count"] == 1
    assert open_data["bills"][0]["invoice_no"] == sale["invoice_no"]
    assert open_data["bills"][0]["due"] == 100

    payment_response = client.post(
        "/api/payments/linked",
        headers=headers,
        json={
            "payment_type": "received",
            "party_id": customer["id"],
            "payment_date": "2026-07-24",
            "amount": 40,
            "mode": "cash",
            "note": "Part payment",
            "allocations": [
                {"reference_type": "sale", "reference_id": sale["id"], "amount": 40}
            ],
        },
    )
    assert payment_response.status_code == 200, payment_response.text
    payment = payment_response.json()
    assert payment["allocated_amount"] == 40
    assert payment["unallocated_amount"] == 0
    assert payment["allocations"][0]["balance_after"] == 60

    updated_sale = client.get(f"/api/sales/{sale['id']}", headers=headers).json()
    assert updated_sale["paid"] == 40
    assert updated_sale["due"] == 60

    updated_party = next(
        row for row in client.get("/api/parties", headers=headers).json()
        if row["id"] == customer["id"]
    )
    assert updated_party["balance"] == 60
    cash_account = next(
        row for row in client.get("/api/accounts", headers=headers).json()
        if row["account_type"] == "cash"
    )
    assert cash_account["balance"] == 40


def test_payment_out_links_purchase_bill_and_reduces_payable(tmp_path):
    client, headers = build_client(tmp_path)
    item = create_item(client, headers)
    supplier = create_party(client, headers, "Supplier A", "supplier")

    purchase_response = client.post(
        "/api/purchases",
        headers=headers,
        json={
            "invoice_no": "SUP-1",
            "party_id": supplier["id"],
            "invoice_date": "2026-07-23",
            "paid": 0,
            "payment_mode": "credit",
            "items": [{"item_id": item["id"], "qty": 1, "rate": 80, "gst_rate": 0}],
        },
    )
    assert purchase_response.status_code == 200, purchase_response.text
    purchase = purchase_response.json()

    open_response = client.get(
        f"/api/parties/{supplier['id']}/open-bills?payment_type=paid",
        headers=headers,
    )
    assert open_response.status_code == 200, open_response.text
    assert open_response.json()["bills"][0]["invoice_no"] == "SUP-1"

    payment_response = client.post(
        "/api/payments/linked",
        headers=headers,
        json={
            "payment_type": "paid",
            "party_id": supplier["id"],
            "payment_date": "2026-07-24",
            "amount": 80,
            "mode": "cash",
            "allocations": [
                {"reference_type": "purchase", "reference_id": purchase["id"], "amount": 80}
            ],
        },
    )
    assert payment_response.status_code == 200, payment_response.text

    updated_purchase = client.get(f"/api/purchases/{purchase['id']}", headers=headers).json()
    assert updated_purchase["paid"] == 80
    assert updated_purchase["due"] == 0
    updated_party = next(
        row for row in client.get("/api/parties", headers=headers).json()
        if row["id"] == supplier["id"]
    )
    assert updated_party["balance"] == 0
    cash_account = next(
        row for row in client.get("/api/accounts", headers=headers).json()
        if row["account_type"] == "cash"
    )
    assert cash_account["balance"] == -80
