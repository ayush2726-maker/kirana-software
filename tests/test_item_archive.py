from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.item_variant_stock_fix_ext  # noqa: F401
import backend.item_archive_ext  # noqa: F401


def build_client(tmp_path: Path) -> TestClient:
    app_module.DB_PATH = tmp_path / "archive.db"
    app_module.init_db()
    return TestClient(app_module.app)


def owner_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/setup",
        json={
            "business_name": "Darbar Home Pack",
            "owner_name": "Ayush",
            "username": "admin",
            "password": "1234",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def add_item(client: TestClient, headers: dict[str, str], sku: str, size: str, stock: float = 0) -> dict:
    response = client.post(
        "/api/items",
        headers=headers,
        json={
            "name": "Barik Souff (बारिक सौंफ)",
            "sku": sku,
            "unit": "kg",
            "size": size,
            "sale_price": 100,
            "stock": stock,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_bulk_remove_archives_billed_variant_and_deletes_unused_variant(tmp_path: Path):
    client = build_client(tmp_path)
    headers = owner_headers(client)
    billed = add_item(client, headers, "SOUFF-100", "100 kg", stock=5)
    unused = add_item(client, headers, "SOUFF-200", "200 pcs", stock=0)
    keeper = add_item(client, headers, "SOUFF-500", "500 gm", stock=12)

    sale = client.post(
        "/api/sales",
        headers=headers,
        json={
            "items": [
                {
                    "item_id": billed["id"],
                    "item_name": billed["name"],
                    "size": billed["size"],
                    "qty": 1,
                    "rate": 100,
                    "gst_rate": 0,
                }
            ]
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = int(sale.json()["id"])

    removed = client.post(
        "/api/items/bulk-delete",
        headers=headers,
        json={"ids": [billed["id"], unused["id"]]},
    )
    assert removed.status_code == 200, removed.text
    result = removed.json()
    assert result["archived"] == 1
    assert result["archived_ids"] == [billed["id"]]
    assert result["deleted"] == 1
    assert result["deleted_ids"] == [unused["id"]]
    assert result["blocked"] == []

    active = client.get("/api/items?limit=2000", headers=headers).json()
    assert [row["id"] for row in active] == [keeper["id"]]

    archived = client.get("/api/items/archived?limit=2000", headers=headers).json()
    assert [row["id"] for row in archived] == [billed["id"]]
    assert archived[0]["stock"] == 4
    assert archived[0]["archived_reason"] == "Used in historical bill/order"

    with app_module.db() as conn:
        old_line = conn.execute(
            "SELECT item_id,item_name,size FROM sale_items WHERE sale_id=?",
            (sale_id,),
        ).fetchone()
        assert old_line is not None
        assert int(old_line["item_id"]) == billed["id"]
        visible_rows = conn.execute(
            "SELECT id FROM items WHERE business_id=? AND COALESCE(archived_at,'')='' ORDER BY id",
            (int(billed["business_id"]),),
        ).fetchall()
        assert [int(row["id"]) for row in visible_rows] == [keeper["id"]]

    dashboard = client.get("/api/dashboard", headers=headers).json()
    assert dashboard["item_count"] == 1
    assert dashboard["stock_value"] == 0


def test_archived_billed_variant_can_be_restored_without_changing_old_bill(tmp_path: Path):
    client = build_client(tmp_path)
    headers = owner_headers(client)
    item = add_item(client, headers, "SOUFF-1KG", "1 kg", stock=3)

    sale = client.post(
        "/api/sales",
        headers=headers,
        json={
            "items": [
                {
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "size": item["size"],
                    "qty": 1,
                    "rate": 100,
                    "gst_rate": 0,
                }
            ]
        },
    )
    assert sale.status_code == 200, sale.text

    archived = client.post(
        f"/api/items/{item['id']}/merge-delete",
        headers=headers,
        json={"stock_action": "keep", "force_archive": True},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived"] is True
    assert client.get("/api/items", headers=headers).json() == []

    restored = client.post(f"/api/items/{item['id']}/restore", headers=headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["archived_at"] == ""
    assert restored.json()["stock"] == 2

    active = client.get("/api/items", headers=headers).json()
    assert [row["id"] for row in active] == [item["id"]]
    with app_module.db() as conn:
        old_line = conn.execute("SELECT item_id FROM sale_items LIMIT 1").fetchone()
        assert old_line is not None
        assert int(old_line["item_id"]) == item["id"]


def test_archive_ui_explains_safe_mixed_remove_behavior():
    script = (app_module.STATIC_DIR / "owner-item-merge-delete-v2.js").read_text(encoding="utf-8")
    bulk_script = (app_module.STATIC_DIR / "owner-bulk-items.js").read_text(encoding="utf-8")
    assert "Archived Items" in script
    assert "New Sale, Purchase and the Customer App" in script
    assert "data-restore-item-id" in script
    assert "data-toggle-delete-item-id" in script
    assert "data-archive-selected" in script
    assert "data-zero-selected" in script
    assert "refreshItemsInPlace" in script
    assert "window.location.replace('/?page=items" not in script
    assert "same unit only (kg with kg, pcs with pcs)" in script
    assert "limit=5000" not in script
    assert "Sizes used in bills will be archived and hidden" in bulk_script
    assert "refreshItemsInPlace" in bulk_script
    assert "window.location.replace('/?page=items" not in bulk_script
    assert "limit=5000" not in bulk_script
