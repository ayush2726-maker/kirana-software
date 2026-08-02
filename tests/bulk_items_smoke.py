from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import requests


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")
DB_PATH = Path(os.environ["KIRANA_DB_PATH"])


def main() -> None:
    login = requests.post(
        f"{BASE_URL}/api/login",
        json={"username": "admin", "password": "1234"},
        timeout=20,
    )
    login.raise_for_status()
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    now = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        business_id = conn.execute("SELECT id FROM businesses ORDER BY id LIMIT 1").fetchone()[0]
        existing = conn.execute(
            "SELECT COUNT(*) FROM items WHERE business_id=? AND sku LIKE 'BULK-SMOKE-%'",
            (business_id,),
        ).fetchone()[0]
        if existing < 501:
            conn.executemany(
                """
                INSERT OR IGNORE INTO items(
                    business_id,name,sku,unit,size,gst_rate,purchase_price,sale_price,mrp,
                    stock,min_stock,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        business_id,
                        f"Bulk Smoke Item {index}",
                        f"BULK-SMOKE-{index:04d}",
                        "pcs",
                        "",
                        0,
                        10,
                        12,
                        15,
                        1,
                        0,
                        now,
                        now,
                    )
                    for index in range(1, 502)
                ],
            )
            conn.commit()

    items_response = requests.get(
        f"{BASE_URL}/api/items",
        params={"q": "Bulk Smoke Item", "limit": 1000},
        headers=headers,
        timeout=30,
    )
    items_response.raise_for_status()
    items = items_response.json()
    assert len(items) == 501, len(items)

    payload = {
        "items": [
            {
                "id": item["id"],
                "name": item["name"],
                "sku": item["sku"],
                "barcode": item.get("barcode", ""),
                "category": item.get("category", ""),
                "unit": item.get("unit", "pcs"),
                "size": item.get("size", ""),
                "hsn": item.get("hsn", ""),
                "gst_rate": item.get("gst_rate", 0),
                "purchase_price": item.get("purchase_price", 0),
                "sale_price": 99,
                "mrp": item.get("mrp", 0),
                "stock": item.get("stock", 0),
                "min_stock": item.get("min_stock", 0),
            }
            for item in items
        ]
    }
    updated = requests.post(
        f"{BASE_URL}/api/items/bulk-update",
        json=payload,
        headers=headers,
        timeout=90,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["updated"] == 501, updated.json()

    invalid = requests.post(
        f"{BASE_URL}/api/items/bulk-update",
        json={"items": [{"id": items[0]["id"], "name": ""}]},
        headers=headers,
        timeout=20,
    )
    assert invalid.status_code == 400, invalid.text
    assert isinstance(invalid.json().get("detail"), str), invalid.json()

    print("BULK_ITEMS_501_OK")


if __name__ == "__main__":
    main()
