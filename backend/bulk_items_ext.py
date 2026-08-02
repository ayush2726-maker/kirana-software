from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app import app, current_user, db, now_iso, split_item_name_size, today_iso


class BulkItemRow(BaseModel):
    id: int
    name: str = Field(min_length=1, max_length=160)
    sku: str = ""
    barcode: str = ""
    category: str = ""
    unit: str = "pcs"
    size: str = ""
    hsn: str = ""
    gst_rate: float = 0
    purchase_price: float = 0
    sale_price: float = 0
    mrp: float = 0
    stock: float = 0
    min_stock: float = 0


class BulkItemUpdateIn(BaseModel):
    items: list[BulkItemRow] = Field(min_items=1, max_items=500)


class BulkItemDeleteIn(BaseModel):
    ids: list[int] = Field(min_items=1, max_items=1000)


@app.post("/api/items/bulk-update")
def bulk_update_items(
    payload: BulkItemUpdateIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    bid = int(user["business_id"])
    unique_ids = list(dict.fromkeys(int(row.id) for row in payload.items))
    if len(unique_ids) != len(payload.items):
        raise HTTPException(status_code=400, detail="The same item was included more than once")

    with db() as conn:
        placeholders = ",".join("?" for _ in unique_ids)
        existing_rows = conn.execute(
            f"SELECT * FROM items WHERE business_id=? AND id IN ({placeholders})",
            [bid, *unique_ids],
        ).fetchall()
        existing = {int(row["id"]): row for row in existing_rows}
        missing = [item_id for item_id in unique_ids if item_id not in existing]
        if missing:
            raise HTTPException(status_code=404, detail=f"Items not found: {missing[:20]}")

        updated_ids: list[int] = []
        try:
            for row in payload.items:
                old = existing[int(row.id)]
                unit = row.unit.strip() or "pcs"
                clean_name, clean_size = split_item_name_size(row.name, row.size, unit)
                sku = row.sku.strip() or str(old["sku"] or "")
                conn.execute(
                    """
                    UPDATE items
                    SET name=?,sku=?,barcode=?,category=?,unit=?,size=?,hsn=?,gst_rate=?,
                        purchase_price=?,sale_price=?,mrp=?,stock=?,min_stock=?,updated_at=?
                    WHERE id=? AND business_id=?
                    """,
                    (
                        clean_name,
                        sku,
                        row.barcode.strip(),
                        row.category.strip(),
                        unit,
                        clean_size,
                        row.hsn.strip(),
                        row.gst_rate,
                        row.purchase_price,
                        row.sale_price,
                        row.mrp,
                        row.stock,
                        row.min_stock,
                        now_iso(),
                        row.id,
                        bid,
                    ),
                )
                difference = round(float(row.stock) - float(old["stock"]), 4)
                if difference:
                    conn.execute(
                        """
                        INSERT INTO stock_movements(
                            business_id,item_id,movement_date,kind,qty,reference_type,note,created_at
                        ) VALUES(?,?,?,?,?,?,?,?)
                        """,
                        (
                            bid,
                            row.id,
                            today_iso(),
                            "adjustment",
                            difference,
                            "bulk_edit",
                            "Bulk item edit",
                            now_iso(),
                        ),
                    )
                updated_ids.append(int(row.id))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="An SKU is duplicated. Every item must have a unique SKU") from exc

        rows = conn.execute(
            f"SELECT * FROM items WHERE business_id=? AND id IN ({placeholders}) ORDER BY name,size",
            [bid, *updated_ids],
        ).fetchall()

    return {"updated": len(updated_ids), "items": [dict(row) for row in rows]}


@app.post("/api/items/bulk-delete")
def bulk_delete_items(
    payload: BulkItemDeleteIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    bid = int(user["business_id"])
    ids = list(dict.fromkeys(int(item_id) for item_id in payload.ids if int(item_id) > 0))
    if not ids:
        raise HTTPException(status_code=400, detail="Select at least one item")

    with db() as conn:
        placeholders = ",".join("?" for _ in ids)
        owned_rows = conn.execute(
            f"SELECT id,name,size FROM items WHERE business_id=? AND id IN ({placeholders})",
            [bid, *ids],
        ).fetchall()
        owned = {int(row["id"]): dict(row) for row in owned_rows}
        missing = [item_id for item_id in ids if item_id not in owned]

        used_rows = conn.execute(
            f"""
            SELECT DISTINCT item_id FROM sale_items WHERE item_id IN ({placeholders})
            UNION
            SELECT DISTINCT item_id FROM purchase_items WHERE item_id IN ({placeholders})
            UNION
            SELECT DISTINCT item_id FROM return_items WHERE item_id IN ({placeholders})
            """,
            [*ids, *ids, *ids],
        ).fetchall()
        blocked_ids = {int(row["item_id"]) for row in used_rows if row["item_id"] is not None}
        deletable = [item_id for item_id in ids if item_id in owned and item_id not in blocked_ids]

        if deletable:
            delete_placeholders = ",".join("?" for _ in deletable)
            conn.execute(
                f"DELETE FROM items WHERE business_id=? AND id IN ({delete_placeholders})",
                [bid, *deletable],
            )

    blocked = [owned[item_id] for item_id in ids if item_id in blocked_ids and item_id in owned]
    return {
        "deleted": len(deletable),
        "deleted_ids": deletable,
        "blocked": blocked,
        "missing_ids": missing,
    }
