from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from backend.app import app, current_user, db, now_iso, today_iso
import backend.bill_edit_ext as bill_edit


VERSION = "132"
_ORIGINAL_LOAD_BILL = bill_edit._load_bill
_ORIGINAL_DETAIL = bill_edit._detail


class MergeDeleteIn(BaseModel):
    target_item_id: int | None = None


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


@app.post("/api/items/{item_id}/merge-delete")
def merge_delete_unused_variant(
    item_id: int,
    payload: MergeDeleteIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot delete items")
    business_id = int(user["business_id"])
    with db() as conn:
        source_row = conn.execute(
            "SELECT * FROM items WHERE id=? AND business_id=?",
            (item_id, business_id),
        ).fetchone()
        if not source_row:
            raise HTTPException(status_code=404, detail="Item not found")
        source = dict(source_row)

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
                detail="Item abhi kisi bill me laga hua hai. Pehle us bill se item badlein.",
            )

        source_stock = round(float(source.get("stock") or 0), 4)
        target: dict[str, Any] | None = None
        if payload.target_item_id:
            if int(payload.target_item_id) == item_id:
                raise HTTPException(status_code=400, detail="Same item me merge nahi kar sakte")
            target_row = conn.execute(
                "SELECT * FROM items WHERE id=? AND business_id=?",
                (int(payload.target_item_id), business_id),
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
