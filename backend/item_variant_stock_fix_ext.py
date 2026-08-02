from __future__ import annotations

from typing import Any

from fastapi import Body, Depends, HTTPException

from backend.app import app, current_user, db, now_iso, today_iso
import backend.bill_edit_ext as bill_edit


VERSION = "133"
_ORIGINAL_LOAD_BILL = bill_edit._load_bill
_ORIGINAL_DETAIL = bill_edit._detail


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _resolve_item_id(
    conn: Any,
    business_id: int,
    item_id: Any,
    item_name: Any,
    size: Any,
) -> int | None:
    try:
        candidate = int(item_id or 0)
    except (TypeError, ValueError):
        candidate = 0
    if candidate > 0:
        row = conn.execute(
            "SELECT id FROM items WHERE id=? AND business_id=?",
            (candidate, business_id),
        ).fetchone()
        if row:
            return int(row["id"])

    name = _clean(item_name)
    item_size = _clean(size)
    if not name:
        return None
    rows = conn.execute(
        """
        SELECT id FROM items
        WHERE business_id=?
          AND lower(trim(name))=?
          AND lower(trim(COALESCE(size,'')))=?
        ORDER BY id
        LIMIT 2
        """,
        (business_id, name, item_size),
    ).fetchall()
    return int(rows[0]["id"]) if len(rows) == 1 else None


def _patched_load_bill(
    conn: Any,
    business_id: int,
    kind: str,
    transaction_id: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bill, lines = _ORIGINAL_LOAD_BILL(conn, business_id, kind, transaction_id)
    table = "sale_items" if kind == "sale" else "purchase_items" if kind == "purchase" else "return_items"
    for line in lines:
        resolved = _resolve_item_id(
            conn,
            business_id,
            line.get("item_id"),
            line.get("item_name"),
            line.get("size"),
        )
        if resolved and int(line.get("item_id") or 0) != resolved:
            conn.execute(f"UPDATE {table} SET item_id=? WHERE id=?", (resolved, line["id"]))
            line["item_id"] = resolved
    return bill, lines


def _patched_detail(
    conn: Any,
    business_id: int,
    kind: str,
    transaction_id: int,
) -> dict[str, Any]:
    detail = _ORIGINAL_DETAIL(conn, business_id, kind, transaction_id)
    if kind == "sale":
        row = conn.execute("SELECT party_id FROM sales WHERE id=? AND business_id=?", (transaction_id, business_id)).fetchone()
    elif kind == "purchase":
        row = conn.execute("SELECT party_id FROM purchases WHERE id=? AND business_id=?", (transaction_id, business_id)).fetchone()
    else:
        row = conn.execute("SELECT party_id FROM returns WHERE id=? AND business_id=? AND kind=?", (transaction_id, business_id, kind)).fetchone()
    detail["party_id"] = int(row["party_id"]) if row and row["party_id"] else None
    return detail


bill_edit._load_bill = _patched_load_bill
bill_edit._detail = _patched_detail


def _payload_target(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("target_item_id")
    if raw in (None, "", 0, "0"):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid merge target")
    return value if value > 0 else None


def _repair_stale_bill_links(conn: Any, business_id: int, source: dict[str, Any]) -> int:
    """Move stale bill-line pointers away from a size that was already replaced.

    Old imported rows can retain the old item_id after their visible name/size was
    edited to another variant. Such a stale pointer should not block deleting the
    now-unused variant.
    """
    source_id = int(source["id"])
    source_name = _clean(source.get("name"))
    source_size = _clean(source.get("size"))
    repaired = 0
    for table in ("sale_items", "purchase_items", "return_items"):
        rows = conn.execute(
            f"SELECT id,item_name,size FROM {table} WHERE item_id=?",
            (source_id,),
        ).fetchall()
        for row in rows:
            line_name = _clean(row["item_name"])
            line_size = _clean(row["size"])
            if line_name == source_name and line_size == source_size:
                continue
            candidates = conn.execute(
                """
                SELECT id FROM items
                WHERE business_id=? AND id<>?
                  AND lower(trim(name))=?
                  AND lower(trim(COALESCE(size,'')))=?
                ORDER BY id
                LIMIT 2
                """,
                (business_id, source_id, line_name, line_size),
            ).fetchall()
            if len(candidates) == 1:
                conn.execute(
                    f"UPDATE {table} SET item_id=? WHERE id=?",
                    (int(candidates[0]["id"]), int(row["id"])),
                )
                repaired += 1
    return repaired


@app.post("/api/items/{item_id}/merge-delete")
def merge_delete_unused_variant(
    item_id: int,
    payload: dict[str, Any] | None = Body(default=None),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot delete items")
    business_id = int(user["business_id"])
    target_item_id = _payload_target(payload)

    with db() as conn:
        source_row = conn.execute(
            "SELECT * FROM items WHERE id=? AND business_id=?",
            (item_id, business_id),
        ).fetchone()
        if not source_row:
            raise HTTPException(status_code=404, detail="Item not found")
        source = dict(source_row)

        repaired_links = _repair_stale_bill_links(conn, business_id, source)
        used = conn.execute(
            """
            SELECT 1 FROM sale_items WHERE item_id=?
            UNION ALL SELECT 1 FROM purchase_items WHERE item_id=?
            UNION ALL SELECT 1 FROM return_items WHERE item_id=?
            LIMIT 1
            """,
            (item_id, item_id, item_id),
        ).fetchone()
        if used:
            raise HTTPException(
                status_code=409,
                detail="Ye size abhi kisi purane bill me laga hua hai. Us bill ko kholkar item badalne ke baad delete karein.",
            )

        source_stock = round(float(source.get("stock") or 0), 4)
        target: dict[str, Any] | None = None
        if target_item_id:
            if target_item_id == item_id:
                raise HTTPException(status_code=400, detail="Same item me merge nahi kar sakte")
            target_row = conn.execute(
                "SELECT * FROM items WHERE id=? AND business_id=?",
                (target_item_id, business_id),
            ).fetchone()
            if not target_row:
                raise HTTPException(status_code=404, detail="Merge target item not found")
            target = dict(target_row)
            if _clean(target.get("name")) != _clean(source.get("name")):
                raise HTTPException(status_code=400, detail="Stock sirf same product ke dusre size me merge ho sakta hai")
        elif abs(source_stock) > 0.00005:
            raise HTTPException(
                status_code=400,
                detail="Is item me stock hai. Delete karne se pehle same product ka target size select karein.",
            )

        if target and abs(source_stock) > 0.00005:
            conn.execute(
                "UPDATE items SET stock=round(stock+?,4),updated_at=? WHERE id=? AND business_id=?",
                (source_stock, now_iso(), target["id"], business_id),
            )
            conn.execute(
                """
                INSERT INTO stock_movements(
                    business_id,item_id,movement_date,kind,qty,reference_type,reference_id,note,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    business_id, target["id"], today_iso(), "adjustment", source_stock,
                    "item_merge", item_id,
                    f"Merged stock from {source.get('size') or source.get('unit') or source.get('name')}",
                    now_iso(),
                ),
            )

        conn.execute("DELETE FROM items WHERE id=? AND business_id=?", (item_id, business_id))
        target_stock = None
        if target:
            refreshed = conn.execute(
                "SELECT stock FROM items WHERE id=? AND business_id=?",
                (target["id"], business_id),
            ).fetchone()
            target_stock = float(refreshed["stock"]) if refreshed else None

    return {
        "deleted": True,
        "deleted_id": item_id,
        "merged_into_id": int(target["id"]) if target else None,
        "transferred_stock": source_stock if target else 0,
        "target_stock": target_stock,
        "repaired_stale_bill_links": repaired_links,
    }


_merge_routes = [
    route for route in list(app.router.routes)
    if getattr(route, "path", None) == "/api/items/{item_id}/merge-delete"
]
for route in _merge_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _merge_routes
