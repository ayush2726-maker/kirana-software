from __future__ import annotations

import unicodedata
from typing import Any

from fastapi import Depends, HTTPException, Request

from backend.app import app, current_user, db, now_iso, today_iso
import backend.bill_edit_ext as bill_edit


VERSION = "134"
MAX_DELETE_ITEMS = 2000
_ORIGINAL_LOAD_BILL = bill_edit._load_bill
_ORIGINAL_DETAIL = bill_edit._detail


def _clean(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    for marker in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"):
        text = text.replace(marker, "")
    return " ".join(text.strip().lower().split())


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

    wanted_name = _clean(item_name)
    wanted_size = _clean(size)
    if not wanted_name:
        return None
    matches = []
    for row in conn.execute(
        "SELECT id,name,size FROM items WHERE business_id=? ORDER BY id",
        (business_id,),
    ).fetchall():
        if _clean(row["name"]) == wanted_name and _clean(row["size"]) == wanted_size:
            matches.append(int(row["id"]))
            if len(matches) > 1:
                return None
    return matches[0] if len(matches) == 1 else None


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
        row = conn.execute(
            "SELECT party_id FROM sales WHERE id=? AND business_id=?",
            (transaction_id, business_id),
        ).fetchone()
    elif kind == "purchase":
        row = conn.execute(
            "SELECT party_id FROM purchases WHERE id=? AND business_id=?",
            (transaction_id, business_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT party_id FROM returns WHERE id=? AND business_id=? AND kind=?",
            (transaction_id, business_id, kind),
        ).fetchone()
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
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid merge target") from exc
    return value if value > 0 else None


async def _request_payload(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _same_product_items(conn: Any, business_id: int, source: dict[str, Any]) -> list[dict[str, Any]]:
    source_name = _clean(source.get("name"))
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM items WHERE business_id=? AND id<>? ORDER BY id",
            (business_id, int(source["id"])),
        ).fetchall()
        if _clean(row["name"]) == source_name
    ]


def _repair_stale_bill_links(conn: Any, business_id: int, source: dict[str, Any]) -> int:
    """Move bill-line pointers that still reference an old replaced size."""
    source_id = int(source["id"])
    source_name = _clean(source.get("name"))
    source_size = _clean(source.get("size"))
    repaired = 0
    business_items = [
        dict(row)
        for row in conn.execute(
            "SELECT id,name,size FROM items WHERE business_id=? AND id<>? ORDER BY id",
            (business_id, source_id),
        ).fetchall()
    ]

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
            candidates = [
                item
                for item in business_items
                if _clean(item.get("name")) == line_name and _clean(item.get("size")) == line_size
            ]
            if len(candidates) == 1:
                conn.execute(
                    f"UPDATE {table} SET item_id=? WHERE id=?",
                    (int(candidates[0]["id"]), int(row["id"])),
                )
                repaired += 1
    return repaired


def _usage_exists(conn: Any, item_id: int) -> bool:
    return bool(
        conn.execute(
            """
            SELECT 1 FROM sale_items WHERE item_id=?
            UNION ALL SELECT 1 FROM purchase_items WHERE item_id=?
            UNION ALL SELECT 1 FROM return_items WHERE item_id=?
            LIMIT 1
            """,
            (item_id, item_id, item_id),
        ).fetchone()
    )


def _delete_item(
    conn: Any,
    business_id: int,
    source: dict[str, Any],
    target_item_id: int | None,
) -> dict[str, Any]:
    item_id = int(source["id"])
    repaired_links = _repair_stale_bill_links(conn, business_id, source)
    if _usage_exists(conn, item_id):
        raise HTTPException(
            status_code=409,
            detail="Ye size abhi kisi asli purane bill me laga hua hai. Us bill ko kholkar item badalne ke baad delete karein.",
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
            detail="Is size me stock hai. Pehle same product ka target size select karein.",
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
                business_id,
                target["id"],
                today_iso(),
                "adjustment",
                source_stock,
                "item_merge",
                item_id,
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


# Remove older handlers first so FastAPI cannot choose a stale Pydantic-body route.
for _route in list(app.router.routes):
    if getattr(_route, "path", None) in {
        "/api/items/{item_id}/merge-delete",
        "/api/items/bulk-delete",
    } and "POST" in (getattr(_route, "methods", set()) or set()):
        app.router.routes.remove(_route)


@app.post("/api/items/{item_id}/merge-delete")
async def merge_delete_unused_variant(
    item_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot delete items")
    if item_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid item")

    payload = await _request_payload(request)
    target_item_id = _payload_target(payload)
    business_id = int(user["business_id"])
    with db() as conn:
        source_row = conn.execute(
            "SELECT * FROM items WHERE id=? AND business_id=?",
            (item_id, business_id),
        ).fetchone()
        if not source_row:
            raise HTTPException(status_code=404, detail="Item not found")
        return _delete_item(conn, business_id, dict(source_row), target_item_id)


@app.post("/api/items/bulk-delete")
async def bulk_delete_item_variants(
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot delete items")
    payload = await _request_payload(request)
    raw_ids = payload.get("ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise HTTPException(status_code=400, detail="Select at least one size or item")

    ids: list[int] = []
    for raw in raw_ids:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    if not ids:
        raise HTTPException(status_code=400, detail="Select at least one valid size or item")
    if len(ids) > MAX_DELETE_ITEMS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_DELETE_ITEMS} items can be deleted together")

    business_id = int(user["business_id"])
    deleted_ids: list[int] = []
    blocked: list[dict[str, Any]] = []
    missing_ids: list[int] = []
    with db() as conn:
        for item_id in ids:
            source_row = conn.execute(
                "SELECT * FROM items WHERE id=? AND business_id=?",
                (item_id, business_id),
            ).fetchone()
            if not source_row:
                missing_ids.append(item_id)
                continue
            source = dict(source_row)
            _repair_stale_bill_links(conn, business_id, source)
            if _usage_exists(conn, item_id):
                blocked.append(
                    {
                        "id": item_id,
                        "name": source.get("name") or "Item",
                        "size": source.get("size") or source.get("unit") or "",
                        "reason": "Used in a bill",
                    }
                )
                continue
            conn.execute("DELETE FROM items WHERE id=? AND business_id=?", (item_id, business_id))
            deleted_ids.append(item_id)

    return {
        "deleted": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "blocked": blocked,
        "missing_ids": missing_ids,
    }


_new_routes = [
    route
    for route in list(app.router.routes)
    if getattr(route, "path", None) in {
        "/api/items/{item_id}/merge-delete",
        "/api/items/bulk-delete",
    }
]
for _route in _new_routes:
    app.router.routes.remove(_route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _new_routes
