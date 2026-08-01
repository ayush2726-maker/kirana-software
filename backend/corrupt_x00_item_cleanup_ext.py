from __future__ import annotations

import json
from typing import Any

from fastapi import Depends

from backend.app import app, current_user, db, now_iso


CORRUPT_SQL = """
lower(
    coalesce(name,'') || ' ' ||
    coalesce(size,'') || ' ' ||
    coalesce(sku,'') || ' ' ||
    coalesce(barcode,'') || ' ' ||
    coalesce(category,'')
) LIKE '%x00%'
"""


def table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
    )


def ensure_corrupt_item_cleanup_schema() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS corrupt_item_cleanup_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                old_item_id INTEGER NOT NULL,
                item_snapshot_json TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT 'x00 import marker',
                deleted_at TEXT NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS block_corrupt_x00_item_insert
            BEFORE INSERT ON items
            WHEN lower(
                coalesce(NEW.name,'') || ' ' ||
                coalesce(NEW.size,'') || ' ' ||
                coalesce(NEW.sku,'') || ' ' ||
                coalesce(NEW.barcode,'') || ' ' ||
                coalesce(NEW.category,'')
            ) LIKE '%x00%'
            BEGIN
                SELECT RAISE(IGNORE);
            END;

            CREATE TRIGGER IF NOT EXISTS block_corrupt_x00_item_update
            BEFORE UPDATE OF name,size,sku,barcode,category ON items
            WHEN lower(
                coalesce(NEW.name,'') || ' ' ||
                coalesce(NEW.size,'') || ' ' ||
                coalesce(NEW.sku,'') || ' ' ||
                coalesce(NEW.barcode,'') || ' ' ||
                coalesce(NEW.category,'')
            ) LIKE '%x00%'
            BEGIN
                SELECT RAISE(IGNORE);
            END;
            """
        )


def recalculate_order(conn, order_id: int) -> None:
    summary = conn.execute(
        """
        SELECT COUNT(*) AS line_count,
               coalesce(SUM(line_subtotal),0) AS subtotal,
               coalesce(SUM(line_tax),0) AS tax,
               coalesce(SUM(line_total),0) AS total
        FROM order_items
        WHERE order_id=?
        """,
        (order_id,),
    ).fetchone()
    if not summary or int(summary["line_count"] or 0) == 0:
        conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
        return
    conn.execute(
        """
        UPDATE orders
        SET subtotal=?,tax=?,total=?,updated_at=?
        WHERE id=?
        """,
        (
            round(float(summary["subtotal"] or 0), 2),
            round(float(summary["tax"] or 0), 2),
            round(float(summary["total"] or 0), 2),
            now_iso(),
            order_id,
        ),
    )


def cleanup_corrupt_x00_items(business_id: int | None = None) -> dict[str, Any]:
    ensure_corrupt_item_cleanup_schema()
    with db() as conn:
        params: tuple[Any, ...] = ()
        business_filter = ""
        if business_id is not None:
            business_filter = " AND business_id=?"
            params = (business_id,)
        rows = conn.execute(
            f"""
            SELECT * FROM items
            WHERE ({CORRUPT_SQL}) {business_filter}
            ORDER BY business_id,id
            """,
            params,
        ).fetchall()

        deleted: list[dict[str, Any]] = []
        has_orders = table_exists(conn, "orders") and table_exists(conn, "order_items")
        for row in rows:
            item = dict(row)
            order_ids: list[int] = []
            if has_orders:
                order_ids = [
                    int(record["order_id"])
                    for record in conn.execute(
                        "SELECT DISTINCT order_id FROM order_items WHERE item_id=?",
                        (item["id"],),
                    ).fetchall()
                ]
                conn.execute("DELETE FROM order_items WHERE item_id=?", (item["id"],))

            conn.execute(
                """
                INSERT INTO corrupt_item_cleanup_log(
                    business_id,old_item_id,item_snapshot_json,reason,deleted_at
                ) VALUES(?,?,?,?,?)
                """,
                (
                    item["business_id"],
                    item["id"],
                    json.dumps(item, ensure_ascii=False, default=str),
                    "Item field contained x00 import/control marker",
                    now_iso(),
                ),
            )
            conn.execute("DELETE FROM items WHERE id=?", (item["id"],))
            for order_id in order_ids:
                recalculate_order(conn, order_id)
            deleted.append(
                {
                    "id": item["id"],
                    "business_id": item["business_id"],
                    "name": item["name"],
                    "size": item.get("size", ""),
                    "sku": item.get("sku", ""),
                }
            )

    return {"deleted_count": len(deleted), "deleted_items": deleted}


@app.on_event("startup")
def startup_cleanup_corrupt_x00_items() -> None:
    cleanup_corrupt_x00_items()


@app.post("/api/items/cleanup-x00")
def owner_cleanup_corrupt_x00_items(
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return cleanup_corrupt_x00_items(int(user["business_id"]))


# Keep the maintenance API ahead of backend.app's SPA fallback route.
_cleanup_routes = [
    route
    for route in app.router.routes
    if getattr(route, "path", None) == "/api/items/cleanup-x00"
]
for route in _cleanup_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _cleanup_routes
