from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.customer_catalog_dedupe_ext  # noqa: F401
import backend.customer_catalog_visibility_ext as visibility_module
import backend.order_portal_ext as order_module


def add_item(conn, business_id: int, name: str, sku: str, rate: float) -> int:
    now = app_module.now_iso()
    return int(
        conn.execute(
            """
            INSERT INTO items(
                business_id,name,sku,barcode,category,unit,size,hsn,gst_rate,
                purchase_price,sale_price,mrp,stock,min_stock,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                business_id,
                name,
                sku,
                "",
                "Test",
                "kg",
                "",
                "",
                0,
                0,
                rate,
                0,
                10,
                0,
                now,
                now,
            ),
        ).lastrowid
    )


def test_only_owner_allowed_products_are_visible_and_orderable(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "customer-catalog-visibility.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    visibility_module.ensure_catalog_visibility_schema()
    client = TestClient(app_module.app)

    setup = client.post(
        "/api/setup",
        json={
            "business_name": "Darbar Home Pack",
            "owner_name": "Ayush",
            "phone": "9981082113",
            "username": "visibility-owner",
            "password": "1234",
        },
    )
    assert setup.status_code == 200, setup.text
    owner_headers = {"Authorization": f"Bearer {setup.json()['token']}"}

    now = app_module.now_iso()
    with app_module.db() as conn:
        business_id = int(conn.execute("SELECT id FROM businesses LIMIT 1").fetchone()["id"])
        party_id = int(
            conn.execute(
                """
                INSERT INTO parties(
                    business_id,name,type,phone,gstin,address,opening_balance,balance,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (business_id, "Ayush", "customer", "9981082113", "", "", 0, 0, now, now),
            ).lastrowid
        )
        allowed_item_id = add_item(conn, business_id, "Kabuli Chana", "KAB-1", 80)
        hidden_item_id = add_item(conn, business_id, "Ajwain", "AJW-1", 170)
        account_id = int(
            conn.execute(
                """
                INSERT INTO customer_accounts(
                    business_id,party_id,phone,password_hash,is_active,created_at,updated_at
                ) VALUES(?,?,?,?,1,?,?)
                """,
                (
                    business_id,
                    party_id,
                    "9981082113",
                    app_module.hash_password("5678"),
                    now,
                    now,
                ),
            ).lastrowid
        )
        customer_token = "catalog-visibility-customer-token"
        expires = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
        conn.execute(
            "INSERT INTO customer_sessions(token,customer_account_id,expires_at,created_at) VALUES(?,?,?,?)",
            (customer_token, account_id, expires, now),
        )

    customer_headers = {"Authorization": f"Bearer {customer_token}"}

    empty_catalog = client.get("/api/customer/catalog", headers=customer_headers)
    assert empty_catalog.status_code == 200, empty_catalog.text
    assert empty_catalog.json() == []

    manage = client.get("/api/customer-catalog/manage", headers=owner_headers)
    assert manage.status_code == 200, manage.text
    products = manage.json()["products"]
    assert len(products) == 2
    assert manage.json()["visible"] == 0

    allowed_product = next(row for row in products if row["name"] == "Kabuli Chana")
    allow = client.put(
        "/api/customer-catalog/visibility",
        headers=owner_headers,
        json={"catalog_key": allowed_product["catalog_key"], "is_visible": True},
    )
    assert allow.status_code == 200, allow.text

    catalog = client.get("/api/customer/catalog", headers=customer_headers)
    assert catalog.status_code == 200, catalog.text
    assert [row["name"] for row in catalog.json()] == ["Kabuli Chana"]
    assert catalog.json()[0]["id"] == allowed_item_id

    blocked = client.post(
        "/api/customer/orders",
        headers=customer_headers,
        json={"items": [{"item_id": hidden_item_id, "qty": 1}]},
    )
    assert blocked.status_code == 403, blocked.text
    assert "allowed nahi" in blocked.json()["detail"]

    order = client.post(
        "/api/customer/orders",
        headers=customer_headers,
        json={"items": [{"item_id": allowed_item_id, "qty": 2}]},
    )
    assert order.status_code == 200, order.text
    assert order.json()["items"][0]["item_id"] == allowed_item_id
    assert order.json()["total"] == 160

    show_all = client.post(
        "/api/customer-catalog/visibility/bulk",
        headers=owner_headers,
        json={"action": "show_all"},
    )
    assert show_all.status_code == 200, show_all.text
    assert show_all.json()["visible"] == 2

    full_catalog = client.get("/api/customer/catalog", headers=customer_headers)
    assert {row["name"] for row in full_catalog.json()} == {"Kabuli Chana", "Ajwain"}
