from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.customer_catalog_dedupe_ext  # noqa: F401
import backend.order_portal_ext as order_module


def test_customer_catalog_merges_duplicate_items_and_hides_stock(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "customer-catalog-dedupe.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    client = TestClient(app_module.app)

    setup = client.post(
        "/api/setup",
        json={
            "business_name": "Darbar Home Pack",
            "owner_name": "Ayush",
            "phone": "9981082113",
            "username": "catalog-owner",
            "password": "1234",
        },
    )
    assert setup.status_code == 200, setup.text

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
        duplicate_one = int(
            conn.execute(
                """
                INSERT INTO items(
                    business_id,name,sku,barcode,category,unit,size,hsn,gst_rate,
                    purchase_price,sale_price,mrp,stock,min_stock,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    business_id,
                    "Kabuli Chana (काबलीचना)",
                    "KAB-OLD",
                    "",
                    "Dal",
                    "Kg",
                    "",
                    "",
                    0,
                    0,
                    70,
                    0,
                    -10288.47,
                    0,
                    now,
                    now,
                ),
            ).lastrowid
        )
        duplicate_two = int(
            conn.execute(
                """
                INSERT INTO items(
                    business_id,name,sku,barcode,category,unit,size,hsn,gst_rate,
                    purchase_price,sale_price,mrp,stock,min_stock,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    business_id,
                    "  Kabuli Chana  (काबलीचना) ",
                    "KAB-NEW",
                    "",
                    "Dal",
                    "kgs",
                    "",
                    "",
                    0,
                    0,
                    75,
                    0,
                    20,
                    0,
                    now,
                    now,
                ),
            ).lastrowid
        )
        conn.execute(
            """
            INSERT INTO items(
                business_id,name,sku,barcode,category,unit,size,hsn,gst_rate,
                purchase_price,sale_price,mrp,stock,min_stock,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                business_id,
                "Kabuli Chana (काबलीचना)",
                "KAB-500",
                "",
                "Dal",
                "packet",
                "500 gm",
                "",
                0,
                0,
                40,
                0,
                5,
                0,
                now,
                now,
            ),
        )
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
        token = "customer-catalog-token"
        expires = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
        conn.execute(
            "INSERT INTO customer_sessions(token,customer_account_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token, account_id, expires, now),
        )
        conn.execute(
            """
            INSERT INTO customer_prices(
                business_id,party_id,item_id,rate,created_at,updated_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (business_id, party_id, duplicate_one, 72, now, now),
        )

    response = client.get(
        "/api/customer/catalog",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    products = response.json()

    assert len(products) == 2
    assert all("stock" not in product for product in products)

    kg_product = next(product for product in products if not product["size"])
    assert kg_product["id"] == duplicate_one
    assert kg_product["rate"] == 72
    assert kg_product["rate_source"] == "fixed"
    assert kg_product["unit"] == "Kg"

    packet_product = next(product for product in products if product["size"] == "500 gm")
    assert packet_product["rate"] == 40
    assert packet_product["id"] not in {duplicate_one, duplicate_two}
