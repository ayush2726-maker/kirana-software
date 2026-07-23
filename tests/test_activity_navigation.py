from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.settings_ext  # noqa: F401
import backend.activity_navigation_ext  # noqa: F401


def build_client(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "activity.db"
    app_module.init_db()
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
    return client, headers


def test_same_date_sales_and_purchases_are_interleaved(tmp_path):
    client, headers = build_client(tmp_path)
    item = client.post(
        "/api/items",
        headers=headers,
        json={"name": "Test Item", "sku": "TEST", "stock": 100, "sale_price": 10, "purchase_price": 8},
    ).json()

    for invoice in ("S-1", "S-2"):
        response = client.post(
            "/api/sales",
            headers=headers,
            json={
                "invoice_no": invoice,
                "invoice_date": "2026-07-23",
                "items": [{"item_id": item["id"], "item_name": "Test Item", "qty": 1, "rate": 10}],
            },
        )
        assert response.status_code == 200, response.text

    for invoice in ("P-1", "P-2"):
        response = client.post(
            "/api/purchases",
            headers=headers,
            json={
                "invoice_no": invoice,
                "invoice_date": "2026-07-23",
                "items": [{"item_id": item["id"], "item_name": "Test Item", "qty": 1, "rate": 8}],
            },
        )
        assert response.status_code == 200, response.text

    rows = client.get("/api/activity?limit=10", headers=headers).json()
    assert [row["kind"] for row in rows[:4]] == ["sale", "purchase", "sale", "purchase"]
    assert all(row["entry_date"] == "2026-07-23" for row in rows[:4])


def test_root_includes_settings_and_navigation_assets(tmp_path):
    client, _ = build_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "/settings-v2.js?v=042" in response.text
    assert "/activity-navigation.js?v=043" in response.text
