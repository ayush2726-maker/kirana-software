from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException

from backend.app import app, current_user, db


def _dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _bill_detail(conn: Any, business_id: int, kind: str, transaction_id: int) -> dict[str, Any] | None:
    if kind == "sale":
        row = conn.execute(
            "SELECT * FROM sales WHERE id=? AND business_id=?",
            (transaction_id, business_id),
        ).fetchone()
        if not row:
            return None
        items = conn.execute(
            """
            SELECT id,item_id,item_name,size,qty,rate,gst_rate,line_subtotal,line_tax,line_total
            FROM sale_items WHERE sale_id=? ORDER BY id
            """,
            (transaction_id,),
        ).fetchall()
        data = dict(row)
        return {
            "id": transaction_id,
            "kind": kind,
            "source": "bill",
            "number": data.get("invoice_no") or "",
            "title": data.get("party_name") or "Cash Customer",
            "party_name": data.get("party_name") or "Cash Customer",
            "date": data.get("invoice_date") or "",
            "subtotal": data.get("subtotal") or 0,
            "discount": data.get("discount") or 0,
            "tax": data.get("tax") or 0,
            "total": data.get("total") or 0,
            "paid": data.get("paid") or 0,
            "due": data.get("due") or 0,
            "payment_mode": data.get("payment_mode") or "credit",
            "status": "unpaid" if float(data.get("due") or 0) > 0 else "completed",
            "notes": data.get("notes") or "",
            "items": [dict(item) for item in items],
        }

    if kind == "purchase":
        row = conn.execute(
            "SELECT * FROM purchases WHERE id=? AND business_id=?",
            (transaction_id, business_id),
        ).fetchone()
        if not row:
            return None
        items = conn.execute(
            """
            SELECT id,item_id,item_name,size,qty,rate,gst_rate,line_subtotal,line_tax,line_total
            FROM purchase_items WHERE purchase_id=? ORDER BY id
            """,
            (transaction_id,),
        ).fetchall()
        data = dict(row)
        return {
            "id": transaction_id,
            "kind": kind,
            "source": "bill",
            "number": data.get("invoice_no") or "",
            "title": data.get("party_name") or "Cash Supplier",
            "party_name": data.get("party_name") or "Cash Supplier",
            "date": data.get("invoice_date") or "",
            "subtotal": data.get("subtotal") or 0,
            "discount": data.get("discount") or 0,
            "tax": data.get("tax") or 0,
            "total": data.get("total") or 0,
            "paid": data.get("paid") or 0,
            "due": data.get("due") or 0,
            "payment_mode": data.get("payment_mode") or "credit",
            "status": "unpaid" if float(data.get("due") or 0) > 0 else "completed",
            "notes": data.get("notes") or "",
            "items": [dict(item) for item in items],
        }

    if kind in {"sale_return", "purchase_return"}:
        row = conn.execute(
            "SELECT * FROM returns WHERE id=? AND business_id=? AND kind=?",
            (transaction_id, business_id, kind),
        ).fetchone()
        if not row:
            return None
        items = conn.execute(
            """
            SELECT id,item_id,item_name,size,qty,rate,gst_rate,line_subtotal,line_tax,line_total
            FROM return_items WHERE return_id=? ORDER BY id
            """,
            (transaction_id,),
        ).fetchall()
        data = dict(row)
        return {
            "id": transaction_id,
            "kind": kind,
            "source": "return",
            "number": data.get("return_no") or "",
            "reference": data.get("reference_no") or "",
            "title": data.get("party_name") or kind.replace("_", " ").title(),
            "party_name": data.get("party_name") or "",
            "date": data.get("return_date") or "",
            "subtotal": data.get("subtotal") or 0,
            "discount": data.get("discount") or 0,
            "tax": data.get("tax") or 0,
            "total": data.get("total") or 0,
            "paid": data.get("paid") or 0,
            "due": data.get("due") or 0,
            "payment_mode": data.get("payment_mode") or "credit",
            "status": "completed",
            "notes": data.get("notes") or "",
            "items": [dict(item) for item in items],
        }

    return None


def _entry_detail(conn: Any, business_id: int, kind: str, transaction_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT e.*,a.name AS account_name,ta.name AS to_account_name
        FROM business_entries e
        LEFT JOIN accounts a ON a.id=e.account_id
        LEFT JOIN accounts ta ON ta.id=e.to_account_id
        WHERE e.id=? AND e.business_id=? AND e.entry_type=?
        """,
        (transaction_id, business_id, kind),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    return {
        "id": transaction_id,
        "kind": kind,
        "source": "entry",
        "number": data.get("title") or kind.replace("_", " ").title(),
        "title": data.get("party_name") or data.get("title") or kind.replace("_", " ").title(),
        "party_name": data.get("party_name") or "",
        "date": data.get("entry_date") or "",
        "total": data.get("amount") or 0,
        "paid": data.get("amount") or 0,
        "due": 0,
        "payment_mode": data.get("mode") or "",
        "status": data.get("status") or "completed",
        "notes": data.get("note") or "",
        "account_name": data.get("account_name") or "",
        "to_account_name": data.get("to_account_name") or "",
        "items": [],
    }


def _document_detail(conn: Any, business_id: int, kind: str, transaction_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM documents WHERE id=? AND business_id=? AND kind=?",
        (transaction_id, business_id, kind),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    return {
        "id": transaction_id,
        "kind": kind,
        "source": "document",
        "number": data.get("doc_no") or "",
        "title": data.get("party_name") or kind.replace("_", " ").title(),
        "party_name": data.get("party_name") or "",
        "date": data.get("doc_date") or "",
        "total": data.get("amount") or 0,
        "paid": 0,
        "due": data.get("amount") or 0,
        "payment_mode": "",
        "status": data.get("status") or "open",
        "notes": data.get("note") or "",
        "items": [],
    }


@app.get("/api/transaction-detail/{kind}/{transaction_id}")
def owner_transaction_detail(
    kind: str,
    transaction_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    clean_kind = str(kind or "").strip().lower()
    if not clean_kind or transaction_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid transaction")

    with db() as conn:
        detail = _bill_detail(conn, int(user["business_id"]), clean_kind, transaction_id)
        if detail is None:
            detail = _entry_detail(conn, int(user["business_id"]), clean_kind, transaction_id)
        if detail is None:
            detail = _document_detail(conn, int(user["business_id"]), clean_kind, transaction_id)

    if detail is None:
        raise HTTPException(status_code=404, detail="Transaction details were not found")
    return detail


# Keep the detail endpoint before the SPA fallback route.
_detail_routes = [
    route for route in list(app.router.routes)
    if getattr(route, "path", None) == "/api/transaction-detail/{kind}/{transaction_id}"
]
for route in _detail_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _detail_routes
