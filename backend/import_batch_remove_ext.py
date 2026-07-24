from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel

import backend.app as core
from backend.app import app, current_user, db, now_iso


class RemoveBatchIn(BaseModel):
    confirm_filename: str


def _table_exists(conn: Any, table: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone())


def _sale_batch_info(conn: Any, business_id: int, batch_id: int) -> dict[str, Any] | None:
    batch = conn.execute(
        """
        SELECT * FROM import_batches
        WHERE id=? AND business_id=? AND entity_type='sales'
          AND COALESCE(status,'')!='rolled_back'
        """,
        (batch_id, business_id),
    ).fetchone()
    if not batch:
        return None

    stats = conn.execute(
        """
        SELECT COUNT(*) AS transactions,
               COALESCE(SUM(total),0) AS total,
               COALESCE(SUM(paid),0) AS paid,
               COALESCE(SUM(due),0) AS due,
               MIN(invoice_date) AS date_from,
               MAX(invoice_date) AS date_to
        FROM sales WHERE business_id=? AND import_batch_id=?
        """,
        (business_id, batch_id),
    ).fetchone()
    lines = conn.execute(
        """
        SELECT COUNT(*)
        FROM sale_items si
        JOIN sales s ON s.id=si.sale_id
        WHERE s.business_id=? AND s.import_batch_id=?
        """,
        (business_id, batch_id),
    ).fetchone()[0]
    linked = 0
    if _table_exists(conn, "payment_allocations"):
        linked = conn.execute(
            """
            SELECT COUNT(*)
            FROM payment_allocations pa
            JOIN sales s ON s.id=pa.reference_id
            WHERE pa.reference_type='sale'
              AND s.business_id=? AND s.import_batch_id=?
            """,
            (business_id, batch_id),
        ).fetchone()[0]

    result = dict(batch)
    result.update({
        "transactions": int(stats["transactions"] or 0),
        "lines": int(lines or 0),
        "total": round(float(stats["total"] or 0), 2),
        "paid": round(float(stats["paid"] or 0), 2),
        "due": round(float(stats["due"] or 0), 2),
        "date_from": stats["date_from"] or "",
        "date_to": stats["date_to"] or "",
        "linked_payments": int(linked or 0),
    })
    result.pop("errors_json", None)
    return result


@app.get("/api/import/removable-sales-batches")
def removable_sales_batches(
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    with db() as conn:
        ids = [
            int(row["id"])
            for row in conn.execute(
                """
                SELECT id FROM import_batches
                WHERE business_id=? AND entity_type='sales'
                  AND COALESCE(status,'')!='rolled_back'
                ORDER BY id DESC
                """,
                (user["business_id"],),
            ).fetchall()
        ]
        return [info for batch_id in ids if (info := _sale_batch_info(conn, user["business_id"], batch_id))]


@app.post("/api/import/remove-sales-batch/{batch_id}")
def remove_sales_batch(
    batch_id: int,
    payload: RemoveBatchIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    business_id = user["business_id"]
    with db() as conn:
        info = _sale_batch_info(conn, business_id, batch_id)
        if not info:
            raise HTTPException(status_code=404, detail="Active Sales import batch not found")
        if payload.confirm_filename.strip() != str(info["filename"] or "").strip():
            raise HTTPException(status_code=400, detail="Import filename confirmation did not match")
        if info["linked_payments"]:
            raise HTTPException(
                status_code=409,
                detail=f"Is import ke {info['linked_payments']} bills par linked payments hain. Pehle un payments ko reverse/delete karna padega.",
            )

        # Restore stock in aggregate. This avoids thousands of per-invoice SQL
        # calls and keeps a large 85k-line import removal fast enough for Railway.
        stock_rows = conn.execute(
            """
            SELECT si.item_id,SUM(si.qty) AS qty
            FROM sale_items si
            JOIN sales s ON s.id=si.sale_id
            WHERE s.business_id=? AND s.import_batch_id=? AND si.item_id IS NOT NULL
            GROUP BY si.item_id
            """,
            (business_id, batch_id),
        ).fetchall()
        for row in stock_rows:
            conn.execute(
                "UPDATE items SET stock=stock+?,updated_at=? WHERE id=? AND business_id=?",
                (float(row["qty"] or 0), now_iso(), row["item_id"], business_id),
            )

        # Remove the original sale movements and sale ledger debits.
        conn.execute(
            """
            DELETE FROM stock_movements
            WHERE business_id=? AND reference_type='sale'
              AND reference_id IN (
                SELECT id FROM sales WHERE business_id=? AND import_batch_id=?
              )
            """,
            (business_id, business_id, batch_id),
        )
        conn.execute(
            """
            DELETE FROM ledger_entries
            WHERE business_id=? AND reference_type='sale'
              AND reference_id IN (
                SELECT id FROM sales WHERE business_id=? AND import_batch_id=?
              )
            """,
            (business_id, business_id, batch_id),
        )

        # Restore party outstanding and account balances created by the import.
        party_rows = conn.execute(
            """
            SELECT party_id,SUM(due) AS due
            FROM sales
            WHERE business_id=? AND import_batch_id=? AND party_id IS NOT NULL
            GROUP BY party_id
            """,
            (business_id, batch_id),
        ).fetchall()
        for row in party_rows:
            conn.execute(
                "UPDATE parties SET balance=MAX(0,balance-?),updated_at=? WHERE id=? AND business_id=?",
                (float(row["due"] or 0), now_iso(), row["party_id"], business_id),
            )

        paid_rows = conn.execute(
            """
            SELECT payment_mode,SUM(paid) AS paid
            FROM sales
            WHERE business_id=? AND import_batch_id=? AND paid>0
            GROUP BY payment_mode
            """,
            (business_id, batch_id),
        ).fetchall()
        for row in paid_rows:
            core.adjust_account(
                conn,
                business_id,
                str(row["payment_mode"] or "cash"),
                -float(row["paid"] or 0),
            )

        # sale_items are deleted by the sales FK cascade.
        conn.execute(
            "DELETE FROM sales WHERE business_id=? AND import_batch_id=?",
            (business_id, batch_id),
        )
        conn.execute(
            """
            UPDATE import_batches
            SET status='rolled_back',rows_imported=0,rows_skipped=rows_total,
                errors_json='[{"error":"Removed manually from Import History"}]'
            WHERE id=? AND business_id=?
            """,
            (batch_id, business_id),
        )

        # Remove only now-unused imported item masters with zero stock.
        conn.execute(
            """
            DELETE FROM items
            WHERE business_id=? AND sku LIKE 'IMP-%'
              AND ABS(COALESCE(stock,0))<0.000001
              AND NOT EXISTS (SELECT 1 FROM sale_items WHERE sale_items.item_id=items.id)
              AND NOT EXISTS (SELECT 1 FROM purchase_items WHERE purchase_items.item_id=items.id)
              AND NOT EXISTS (SELECT 1 FROM return_items WHERE return_items.item_id=items.id)
            """,
            (business_id,),
        )

    return {
        "ok": True,
        "batch_id": batch_id,
        "filename": info["filename"],
        "removed_transactions": info["transactions"],
        "removed_lines": info["lines"],
    }


paths = {
    "/api/import/removable-sales-batches",
    "/api/import/remove-sales-batch/{batch_id}",
}
routes = [route for route in app.router.routes if getattr(route, "path", None) in paths]
for route in routes:
    app.router.routes.remove(route)
fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback_index:fallback_index] = routes
