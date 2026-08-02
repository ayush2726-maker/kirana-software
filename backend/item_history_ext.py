from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app, current_user, db
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "129"
HISTORY_JS = STATIC_DIR / "owner-item-history.js"
HISTORY_URL = f"/owner-item-history.js?v={VERSION}"


if HISTORY_URL not in native_owner.OPTIONAL_JS_URLS:
    native_owner.OPTIONAL_JS_URLS.append(HISTORY_URL)
if HISTORY_JS not in final_owner.JS_FILES:
    final_owner.JS_FILES.append(HISTORY_JS)

native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION


_previous_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_item_history(token: str) -> HTMLResponse:
    original = _previous_stable_owner_page(token)
    page = original.body.decode("utf-8")
    if HISTORY_URL not in page:
        page = page.replace("</body>", f'<script src="{HISTORY_URL}"></script></body>', 1)
    headers = {
        key: value
        for key, value in original.headers.items()
        if key.lower() not in {"content-length", "content-type", "set-cookie"}
    }
    response = HTMLResponse(page, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie:
        response.headers.append("set-cookie", cookie)
    return response


stable_owner.stable_owner_page = stable_owner_page_with_item_history


@app.on_event("startup")
def ensure_item_history_indexes() -> None:
    """Keep item-history lookups fast even after large Vyapar imports."""

    with db() as conn:
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_sale_items_item_history
                ON sale_items(item_id, sale_id);
            CREATE INDEX IF NOT EXISTS idx_purchase_items_item_history
                ON purchase_items(item_id, purchase_id);
            CREATE INDEX IF NOT EXISTS idx_return_items_item_history
                ON return_items(item_id, return_id);
            CREATE INDEX IF NOT EXISTS idx_sale_items_legacy_history
                ON sale_items(item_name COLLATE NOCASE, size COLLATE NOCASE, sale_id);
            CREATE INDEX IF NOT EXISTS idx_purchase_items_legacy_history
                ON purchase_items(item_name COLLATE NOCASE, size COLLATE NOCASE, purchase_id);
            CREATE INDEX IF NOT EXISTS idx_return_items_legacy_history
                ON return_items(item_name COLLATE NOCASE, size COLLATE NOCASE, return_id);
            """
        )


def _append_rows(
    target: list[dict[str, Any]],
    rows: list[Any],
    stock_sign: int,
) -> None:
    for row in rows:
        data = dict(row)
        quantity = abs(float(data.get("qty") or 0))
        data["stock_delta"] = stock_sign * quantity
        target.append(data)


def _sale_rows(
    conn: Any,
    business_id: int,
    item_id: int,
    item_name: str,
    item_size: str,
) -> list[Any]:
    linked = conn.execute(
        """
        SELECT
            'sale' AS kind,
            s.id AS transaction_id,
            s.invoice_no AS number,
            s.invoice_date AS transaction_date,
            COALESCE(NULLIF(s.party_name,''),'Cash Customer') AS party_name,
            SUM(si.qty) AS qty,
            CASE WHEN SUM(si.qty)<>0 THEN SUM(si.line_total)/SUM(si.qty) ELSE 0 END AS rate,
            SUM(si.line_total) AS amount,
            s.created_at AS created_at
        FROM sale_items si INDEXED BY idx_sale_items_item_history
        JOIN sales s ON s.id=si.sale_id
        WHERE s.business_id=? AND si.item_id=?
        GROUP BY s.id,s.invoice_no,s.invoice_date,s.party_name,s.created_at
        """,
        (business_id, item_id),
    ).fetchall()
    legacy = conn.execute(
        """
        SELECT
            'sale' AS kind,
            s.id AS transaction_id,
            s.invoice_no AS number,
            s.invoice_date AS transaction_date,
            COALESCE(NULLIF(s.party_name,''),'Cash Customer') AS party_name,
            SUM(si.qty) AS qty,
            CASE WHEN SUM(si.qty)<>0 THEN SUM(si.line_total)/SUM(si.qty) ELSE 0 END AS rate,
            SUM(si.line_total) AS amount,
            s.created_at AS created_at
        FROM sale_items si INDEXED BY idx_sale_items_legacy_history
        JOIN sales s ON s.id=si.sale_id
        WHERE s.business_id=?
          AND si.item_id IS NULL
          AND si.item_name=? COLLATE NOCASE
          AND COALESCE(si.size,'')=? COLLATE NOCASE
        GROUP BY s.id,s.invoice_no,s.invoice_date,s.party_name,s.created_at
        """,
        (business_id, item_name, item_size),
    ).fetchall()
    return list(linked) + list(legacy)


def _purchase_rows(
    conn: Any,
    business_id: int,
    item_id: int,
    item_name: str,
    item_size: str,
) -> list[Any]:
    linked = conn.execute(
        """
        SELECT
            'purchase' AS kind,
            p.id AS transaction_id,
            p.invoice_no AS number,
            p.invoice_date AS transaction_date,
            COALESCE(NULLIF(p.party_name,''),'Cash Supplier') AS party_name,
            SUM(pi.qty) AS qty,
            CASE WHEN SUM(pi.qty)<>0 THEN SUM(pi.line_total)/SUM(pi.qty) ELSE 0 END AS rate,
            SUM(pi.line_total) AS amount,
            p.created_at AS created_at
        FROM purchase_items pi INDEXED BY idx_purchase_items_item_history
        JOIN purchases p ON p.id=pi.purchase_id
        WHERE p.business_id=? AND pi.item_id=?
        GROUP BY p.id,p.invoice_no,p.invoice_date,p.party_name,p.created_at
        """,
        (business_id, item_id),
    ).fetchall()
    legacy = conn.execute(
        """
        SELECT
            'purchase' AS kind,
            p.id AS transaction_id,
            p.invoice_no AS number,
            p.invoice_date AS transaction_date,
            COALESCE(NULLIF(p.party_name,''),'Cash Supplier') AS party_name,
            SUM(pi.qty) AS qty,
            CASE WHEN SUM(pi.qty)<>0 THEN SUM(pi.line_total)/SUM(pi.qty) ELSE 0 END AS rate,
            SUM(pi.line_total) AS amount,
            p.created_at AS created_at
        FROM purchase_items pi INDEXED BY idx_purchase_items_legacy_history
        JOIN purchases p ON p.id=pi.purchase_id
        WHERE p.business_id=?
          AND pi.item_id IS NULL
          AND pi.item_name=? COLLATE NOCASE
          AND COALESCE(pi.size,'')=? COLLATE NOCASE
        GROUP BY p.id,p.invoice_no,p.invoice_date,p.party_name,p.created_at
        """,
        (business_id, item_name, item_size),
    ).fetchall()
    return list(linked) + list(legacy)


def _return_rows(
    conn: Any,
    business_id: int,
    item_id: int,
    item_name: str,
    item_size: str,
) -> list[Any]:
    linked = conn.execute(
        """
        SELECT
            r.kind AS kind,
            r.id AS transaction_id,
            r.return_no AS number,
            r.return_date AS transaction_date,
            COALESCE(NULLIF(r.party_name,''),replace(r.kind,'_',' ')) AS party_name,
            SUM(ri.qty) AS qty,
            CASE WHEN SUM(ri.qty)<>0 THEN SUM(ri.line_total)/SUM(ri.qty) ELSE 0 END AS rate,
            SUM(ri.line_total) AS amount,
            r.created_at AS created_at
        FROM return_items ri INDEXED BY idx_return_items_item_history
        JOIN returns r ON r.id=ri.return_id
        WHERE r.business_id=? AND ri.item_id=?
        GROUP BY r.id,r.kind,r.return_no,r.return_date,r.party_name,r.created_at
        """,
        (business_id, item_id),
    ).fetchall()
    legacy = conn.execute(
        """
        SELECT
            r.kind AS kind,
            r.id AS transaction_id,
            r.return_no AS number,
            r.return_date AS transaction_date,
            COALESCE(NULLIF(r.party_name,''),replace(r.kind,'_',' ')) AS party_name,
            SUM(ri.qty) AS qty,
            CASE WHEN SUM(ri.qty)<>0 THEN SUM(ri.line_total)/SUM(ri.qty) ELSE 0 END AS rate,
            SUM(ri.line_total) AS amount,
            r.created_at AS created_at
        FROM return_items ri INDEXED BY idx_return_items_legacy_history
        JOIN returns r ON r.id=ri.return_id
        WHERE r.business_id=?
          AND ri.item_id IS NULL
          AND ri.item_name=? COLLATE NOCASE
          AND COALESCE(ri.size,'')=? COLLATE NOCASE
        GROUP BY r.id,r.kind,r.return_no,r.return_date,r.party_name,r.created_at
        """,
        (business_id, item_name, item_size),
    ).fetchall()
    return list(linked) + list(legacy)


def _bill_rows(conn: Any, business_id: int, item: dict[str, Any]) -> list[dict[str, Any]]:
    item_id = int(item["id"])
    item_name = str(item.get("name") or "").strip()
    item_size = str(item.get("size") or "").strip()
    rows: list[dict[str, Any]] = []

    _append_rows(rows, _sale_rows(conn, business_id, item_id, item_name, item_size), -1)
    _append_rows(rows, _purchase_rows(conn, business_id, item_id, item_name, item_size), 1)

    for row in _return_rows(conn, business_id, item_id, item_name, item_size):
        data = dict(row)
        quantity = abs(float(data.get("qty") or 0))
        data["stock_delta"] = quantity if data.get("kind") == "sale_return" else -quantity
        rows.append(data)

    manual_rows = conn.execute(
        """
        SELECT id, movement_date, kind, qty, reference_type, note, created_at
        FROM stock_movements
        WHERE business_id=? AND item_id=?
          AND COALESCE(reference_type,'') NOT IN ('sale','purchase','sale_return','purchase_return')
        ORDER BY movement_date DESC,id DESC
        """,
        (business_id, item_id),
    ).fetchall()
    for row in manual_rows:
        movement = dict(row)
        quantity = float(movement.get("qty") or 0)
        movement_kind = str(movement.get("kind") or "adjustment")
        if movement_kind == "opening":
            kind = "opening_stock"
        elif quantity >= 0:
            kind = "add_stock"
        else:
            kind = "reduce_stock"
        rows.append(
            {
                "kind": kind,
                "transaction_id": None,
                "movement_id": int(movement["id"]),
                "number": movement.get("note") or movement_kind.replace("_", " ").title(),
                "transaction_date": movement.get("movement_date") or "",
                "party_name": "Main Godown",
                "qty": abs(quantity),
                "rate": 0,
                "amount": 0,
                "stock_delta": quantity,
                "created_at": movement.get("created_at") or "",
            }
        )

    rows.sort(
        key=lambda row: (
            str(row.get("transaction_date") or ""),
            str(row.get("created_at") or ""),
            int(row.get("transaction_id") or row.get("movement_id") or 0),
        ),
        reverse=True,
    )
    return rows


@app.get("/api/item-history/{item_id}")
def owner_item_history(
    item_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if item_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid item")

    business_id = int(user["business_id"])
    with db() as conn:
        row = conn.execute(
            """
            SELECT id,name,size,unit,sku,category,sale_price,purchase_price,stock,min_stock,mrp,gst_rate
            FROM items WHERE id=? AND business_id=?
            """,
            (item_id, business_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item was not found")
        item = dict(row)
        transactions = _bill_rows(conn, business_id, item)

    sale_rows = [row for row in transactions if row.get("kind") == "sale"]
    purchase_rows = [row for row in transactions if row.get("kind") == "purchase"]
    item["stock_value"] = round(float(item.get("stock") or 0) * float(item.get("purchase_price") or 0), 2)
    return {
        "item": item,
        "summary": {
            "transactions": len(transactions),
            "sale_qty": round(sum(float(row.get("qty") or 0) for row in sale_rows), 4),
            "purchase_qty": round(sum(float(row.get("qty") or 0) for row in purchase_rows), 4),
            "sale_amount": round(sum(float(row.get("amount") or 0) for row in sale_rows), 2),
            "purchase_amount": round(sum(float(row.get("amount") or 0) for row in purchase_rows), 2),
        },
        "transactions": transactions,
    }


_item_history_routes = [
    route for route in list(app.router.routes)
    if getattr(route, "path", None) == "/api/item-history/{item_id}"
]
for route in _item_history_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _item_history_routes


@app.middleware("http")
async def serve_item_history_asset(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-item-history.js":
        return Response(
            HISTORY_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Kirana-Item-History": VERSION,
            },
        )
    return await call_next(request)
