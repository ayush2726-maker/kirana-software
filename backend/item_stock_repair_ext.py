from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app import app, current_user, db, now_iso, today_iso
import backend.bill_edit_ext as bill_edit


VERSION = "131"
SUPPORTED = {"sale", "purchase", "sale_return", "purchase_return"}
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
    if len(rows) == 1:
        return int(rows[0]["id"])
    return None


def _patched_load_bill(
    conn: Any,
    business_id: int,
    kind: str,
    transaction_id: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bill, lines = _ORIGINAL_LOAD_BILL(conn, business_id, kind, transaction_id)
    if kind == "sale":
        table = "sale_items"
    elif kind == "purchase":
        table = "purchase_items"
    else:
        table = "return_items"

    for line in lines:
        resolved = _resolve_item_id(
            conn,
            business_id,
            line.get("item_id"),
            line.get("item_name"),
            line.get("size"),
        )
        if resolved and int(line.get("item_id") or 0) != resolved:
            conn.execute(
                f"UPDATE {table} SET item_id=? WHERE id=?",
                (resolved, line["id"]),
            )
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


def _kind_meta(kind: str) -> tuple[str, str, int, str, str]:
    if kind == "sale":
        return "sale_items", "sale_id", -1, "sales", "invoice_date"
    if kind == "purchase":
        return "purchase_items", "purchase_id", 1, "purchases", "invoice_date"
    if kind == "sale_return":
        return "return_items", "return_id", 1, "returns", "return_date"
    if kind == "purchase_return":
        return "return_items", "return_id", -1, "returns", "return_date"
    raise ValueError(kind)


def _bill_header(conn: Any, business_id: int, kind: str, transaction_id: int) -> tuple[str, str] | None:
    if kind == "sale":
        row = conn.execute(
            "SELECT invoice_no AS number,invoice_date AS tx_date FROM sales WHERE id=? AND business_id=?",
            (transaction_id, business_id),
        ).fetchone()
    elif kind == "purchase":
        row = conn.execute(
            "SELECT invoice_no AS number,invoice_date AS tx_date FROM purchases WHERE id=? AND business_id=?",
            (transaction_id, business_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT return_no AS number,return_date AS tx_date FROM returns WHERE id=? AND business_id=? AND kind=?",
            (transaction_id, business_id, kind),
        ).fetchone()
    return (str(row["number"] or ""), str(row["tx_date"] or today_iso())) if row else None


def _reconcile_reference(
    conn: Any,
    business_id: int,
    kind: str,
    transaction_id: int,
    *,
    require_existing_movement: bool,
) -> bool:
    if kind not in SUPPORTED or transaction_id <= 0:
        return False
    header = _bill_header(conn, business_id, kind, transaction_id)
    if not header:
        return False
    line_table, foreign_key, sign, _header_table, _date_column = _kind_meta(kind)
    lines = conn.execute(
        f"SELECT id,item_id,item_name,size,qty FROM {line_table} WHERE {foreign_key}=? ORDER BY id",
        (transaction_id,),
    ).fetchall()
    if not lines:
        return False

    expected: dict[int, float] = defaultdict(float)
    unresolved = False
    for raw in lines:
        line = dict(raw)
        item_id = _resolve_item_id(
            conn,
            business_id,
            line.get("item_id"),
            line.get("item_name"),
            line.get("size"),
        )
        if not item_id:
            unresolved = True
            continue
        if int(line.get("item_id") or 0) != item_id:
            conn.execute(
                f"UPDATE {line_table} SET item_id=? WHERE id=?",
                (item_id, line["id"]),
            )
        expected[item_id] += sign * float(line.get("qty") or 0)
    if unresolved:
        return False

    movement_rows = conn.execute(
        """
        SELECT item_id,COALESCE(SUM(qty),0) AS qty
        FROM stock_movements
        WHERE business_id=? AND reference_type=? AND reference_id=?
        GROUP BY item_id
        """,
        (business_id, kind, transaction_id),
    ).fetchall()
    if require_existing_movement and not movement_rows:
        return False
    existing = {
        int(row["item_id"]): float(row["qty"] or 0)
        for row in movement_rows
        if row["item_id"] is not None
    }
    rounded_expected = {item_id: round(qty, 4) for item_id, qty in expected.items() if abs(qty) > 0.00005}
    rounded_existing = {item_id: round(qty, 4) for item_id, qty in existing.items() if abs(qty) > 0.00005}
    if rounded_expected == rounded_existing:
        return False

    for item_id in set(rounded_expected) | set(rounded_existing):
        difference = round(rounded_expected.get(item_id, 0) - rounded_existing.get(item_id, 0), 4)
        if difference:
            conn.execute(
                "UPDATE items SET stock=round(stock+?,4),updated_at=? WHERE id=? AND business_id=?",
                (difference, now_iso(), item_id, business_id),
            )

    conn.execute(
        "DELETE FROM stock_movements WHERE business_id=? AND reference_type=? AND reference_id=?",
        (business_id, kind, transaction_id),
    )
    number, tx_date = header
    for item_id, qty in rounded_expected.items():
        conn.execute(
            """
            INSERT INTO stock_movements(
                business_id,item_id,movement_date,kind,qty,reference_type,reference_id,note,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                business_id, item_id, tx_date, kind, qty,
                kind, transaction_id, number, now_iso(),
            ),
        )
    return True


@app.on_event("startup")
def repair_changed_variant_stock() -> None:
    with db() as conn:
        references = conn.execute(
            """
            SELECT DISTINCT business_id,reference_type,reference_id
            FROM stock_movements
            WHERE reference_type IN ('sale','purchase','sale_return','purchase_return')
              AND reference_id IS NOT NULL
            """
        ).fetchall()
        for row in references:
            try:
                _reconcile_reference(
                    conn,
                    int(row["business_id"]),
                    str(row["reference_type"]),
                    int(row["reference_id"]),
                    require_existing_movement=True,
                )
            except Exception:
                # One damaged historical row must not block the app startup.
                continue


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

        conn.execute(
            "DELETE FROM items WHERE id=? AND business_id=?",
            (item_id, business_id),
        )
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


@app.middleware("http")
async def reconcile_after_bill_edit(request: Request, call_next):
    path = request.url.path.rstrip("/")
    response = await call_next(request)
    if request.method == "PUT" and response.status_code < 400 and path.startswith("/api/bill-edit/"):
        parts = path.split("/")
        if len(parts) >= 5:
            kind = parts[-2]
            try:
                transaction_id = int(parts[-1])
            except ValueError:
                transaction_id = 0
            if kind in SUPPORTED and transaction_id > 0:
                try:
                    user = current_user(request.headers.get("authorization"))
                    with db() as conn:
                        _reconcile_reference(
                            conn,
                            int(user["business_id"]),
                            kind,
                            transaction_id,
                            require_existing_movement=False,
                        )
                except Exception:
                    pass
    return response
