from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, HTTPException

from backend.app import app, current_user, db, now_iso, split_item_name_size, today_iso


MAX_BULK_ITEMS = 2000


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _number(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return default
    return round(parsed, 4)


def _bulk_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list) or not raw_items:
        raise HTTPException(status_code=400, detail="Select at least one item to save")
    if len(raw_items) > MAX_BULK_ITEMS:
        raise HTTPException(
            status_code=400,
            detail=f"A maximum of {MAX_BULK_ITEMS} items can be saved at one time",
        )

    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail=f"Item {index} has invalid data")
        try:
            item_id = int(raw.get("id") or 0)
        except (TypeError, ValueError):
            item_id = 0
        if item_id <= 0:
            raise HTTPException(status_code=400, detail=f"Item {index} has an invalid ID")
        if item_id in seen_ids:
            raise HTTPException(status_code=400, detail=f"Item ID {item_id} was selected more than once")
        seen_ids.add(item_id)

        name = _text(raw.get("name"))
        if not name:
            raise HTTPException(status_code=400, detail=f"Item {index} needs a name")

        rows.append(
            {
                "id": item_id,
                "name": name,
                "sku": _text(raw.get("sku")),
                "barcode": _text(raw.get("barcode")),
                "category": _text(raw.get("category")),
                "unit": _text(raw.get("unit"), "pcs") or "pcs",
                "size": _text(raw.get("size")),
                "hsn": _text(raw.get("hsn")),
                "gst_rate": _number(raw.get("gst_rate")),
                "purchase_price": _number(raw.get("purchase_price")),
                "sale_price": _number(raw.get("sale_price")),
                "mrp": _number(raw.get("mrp")),
                "stock": _number(raw.get("stock")),
                "min_stock": _number(raw.get("min_stock")),
            }
        )
    return rows


@app.post("/api/items/bulk-update")
def bulk_update_items(
    payload: dict[str, Any],
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    bid = int(user["business_id"])
    items = _bulk_rows(payload)
    item_ids = [int(row["id"]) for row in items]

    with db() as conn:
        placeholders = ",".join("?" for _ in item_ids)
        existing_rows = conn.execute(
            f"SELECT * FROM items WHERE business_id=? AND id IN ({placeholders})",
            [bid, *item_ids],
        ).fetchall()
        existing = {int(row["id"]): row for row in existing_rows}
        missing = [item_id for item_id in item_ids if item_id not in existing]
        if missing:
            raise HTTPException(status_code=404, detail=f"Items not found: {missing[:20]}")

        updated_ids: list[int] = []
        try:
            for row in items:
                old = existing[int(row["id"])]
                unit = row["unit"] or "pcs"
                clean_name, clean_size = split_item_name_size(row["name"], row["size"], unit)
                sku = row["sku"] or str(old["sku"] or "")
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
                        row["barcode"],
                        row["category"],
                        unit,
                        clean_size,
                        row["hsn"],
                        row["gst_rate"],
                        row["purchase_price"],
                        row["sale_price"],
                        row["mrp"],
                        row["stock"],
                        row["min_stock"],
                        now_iso(),
                        row["id"],
                        bid,
                    ),
                )
                difference = round(float(row["stock"]) - float(old["stock"]), 4)
                if difference:
                    conn.execute(
                        """
                        INSERT INTO stock_movements(
                            business_id,item_id,movement_date,kind,qty,reference_type,note,created_at
                        ) VALUES(?,?,?,?,?,?,?,?)
                        """,
                        (
                            bid,
                            row["id"],
                            today_iso(),
                            "adjustment",
                            difference,
                            "bulk_edit",
                            "Bulk item edit",
                            now_iso(),
                        ),
                    )
                updated_ids.append(int(row["id"]))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="An SKU is duplicated. Every item must have a unique SKU",
            ) from exc

        rows = conn.execute(
            f"SELECT * FROM items WHERE business_id=? AND id IN ({placeholders}) ORDER BY name,size",
            [bid, *updated_ids],
        ).fetchall()

    return {"updated": len(updated_ids), "items": [dict(row) for row in rows]}


@app.post("/api/items/bulk-delete")
def bulk_delete_items(
    payload: dict[str, Any],
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    raw_ids = payload.get("ids") if isinstance(payload, dict) else None
    if not isinstance(raw_ids, list) or not raw_ids:
        raise HTTPException(status_code=400, detail="Select at least one item")
    if len(raw_ids) > MAX_BULK_ITEMS:
        raise HTTPException(
            status_code=400,
            detail=f"A maximum of {MAX_BULK_ITEMS} items can be deleted at one time",
        )

    ids: list[int] = []
    for value in raw_ids:
        try:
            item_id = int(value)
        except (TypeError, ValueError):
            continue
        if item_id > 0 and item_id not in ids:
            ids.append(item_id)
    if not ids:
        raise HTTPException(status_code=400, detail="Select at least one valid item")

    bid = int(user["business_id"])
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
