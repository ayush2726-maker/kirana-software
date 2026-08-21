from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Query

from backend.app import app, current_user, db, now_iso
import backend.order_portal_ext as order_portal


VERSION = "178"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


@app.get("/api/items/archived")
def archived_items(
    q: str = "",
    limit: int = Query(default=2000, ge=1, le=2000),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM items WHERE business_id=? AND COALESCE(archived_at,'')<>''"
    args: list[Any] = [int(user["business_id"])]
    if q:
        like = f"%{q}%"
        sql += " AND (name LIKE ? OR size LIKE ? OR sku LIKE ? OR category LIKE ?)"
        args.extend([like, like, like, like])
    sql += " ORDER BY archived_at DESC,name,size,id LIMIT ?"
    args.append(limit)
    with db() as conn:
        return [dict(row) for row in conn.execute(sql, args).fetchall()]


@app.post("/api/items/{item_id}/restore")
def restore_archived_item(
    item_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot restore items")
    business_id = int(user["business_id"])
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM items WHERE id=? AND business_id=?",
            (item_id, business_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        item = dict(row)
        if not str(item.get("archived_at") or "").strip():
            return item

        active_rows = conn.execute(
            """
            SELECT id,name,size,unit FROM items
            WHERE business_id=? AND id<>? AND COALESCE(archived_at,'')=''
            """,
            (business_id, item_id),
        ).fetchall()
        duplicate = next(
            (
                active
                for active in active_rows
                if _clean(active["name"]) == _clean(item.get("name"))
                and _clean(active["size"]) == _clean(item.get("size"))
                and _clean(active["unit"]) == _clean(item.get("unit"))
            ),
            None,
        )
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="An active item with the same name, size and unit already exists.",
            )

        conn.execute(
            """
            UPDATE items
            SET archived_at='',archived_reason='',updated_at=?
            WHERE id=? AND business_id=?
            """,
            (now_iso(), item_id, business_id),
        )
        restored = conn.execute(
            "SELECT * FROM items WHERE id=? AND business_id=?",
            (item_id, business_id),
        ).fetchone()
        return dict(restored)


_original_create_order_record = order_portal.create_order_record


def create_order_record_without_archived_items(
    payload: Any,
    business_id: int,
    party_id: int,
    source: str,
    customer_account_id: int | None = None,
    created_by_user_id: int | None = None,
) -> dict[str, Any]:
    item_ids = sorted(
        {
            int(line.item_id)
            for line in getattr(payload, "items", [])
            if int(getattr(line, "item_id", 0) or 0) > 0
        }
    )
    if item_ids:
        placeholders = ",".join("?" for _ in item_ids)
        with db() as conn:
            archived = conn.execute(
                f"""
                SELECT name,size FROM items
                WHERE business_id=? AND id IN ({placeholders})
                  AND COALESCE(archived_at,'')<>''
                LIMIT 1
                """,
                (business_id, *item_ids),
            ).fetchone()
        if archived:
            label = str(archived["name"] or "Item")
            if archived["size"]:
                label += f" - {archived['size']}"
            raise HTTPException(
                status_code=409,
                detail=f"{label} is archived and cannot be used in a new order",
            )
    return _original_create_order_record(
        payload,
        business_id,
        party_id,
        source,
        customer_account_id=customer_account_id,
        created_by_user_id=created_by_user_id,
    )


order_portal.create_order_record = create_order_record_without_archived_items


_new_routes = [
    route
    for route in list(app.router.routes)
    if getattr(route, "endpoint", None) in {archived_items, restore_archived_item}
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
