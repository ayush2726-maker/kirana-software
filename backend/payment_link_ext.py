from __future__ import annotations

from typing import Any, Literal

from fastapi import Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.app import (
    STATIC_DIR,
    app,
    current_user,
    db,
    normalize_date,
    now_iso,
    today_iso,
)


class PaymentAllocationIn(BaseModel):
    reference_type: Literal["sale", "purchase"]
    reference_id: int
    amount: float


class LinkedPaymentIn(BaseModel):
    payment_type: Literal["received", "paid"]
    party_id: int
    payment_date: str = Field(default_factory=today_iso)
    amount: float
    mode: str = "cash"
    account_id: int | None = None
    note: str = ""
    allocations: list[PaymentAllocationIn] = Field(default_factory=list)


@app.on_event("startup")
def init_payment_linking() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS payment_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                receipt_no TEXT NOT NULL,
                payment_type TEXT NOT NULL CHECK(payment_type IN ('received','paid')),
                party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
                party_name TEXT NOT NULL,
                payment_date TEXT NOT NULL,
                amount REAL NOT NULL,
                allocated_amount REAL NOT NULL DEFAULT 0,
                unallocated_amount REAL NOT NULL DEFAULT 0,
                mode TEXT DEFAULT 'cash',
                account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
                note TEXT DEFAULT '',
                created_by INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(business_id, receipt_no)
            );
            CREATE INDEX IF NOT EXISTS idx_payment_receipts_party_date
            ON payment_receipts(party_id, payment_date DESC, id DESC);

            CREATE TABLE IF NOT EXISTS payment_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL REFERENCES payment_receipts(id) ON DELETE CASCADE,
                reference_type TEXT NOT NULL CHECK(reference_type IN ('sale','purchase')),
                reference_id INTEGER NOT NULL,
                invoice_no TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                bill_total REAL NOT NULL,
                balance_before REAL NOT NULL,
                allocated_amount REAL NOT NULL,
                balance_after REAL NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(payment_id, reference_type, reference_id)
            );
            CREATE INDEX IF NOT EXISTS idx_payment_allocations_reference
            ON payment_allocations(reference_type, reference_id);
            """
        )


def _expected_kind(payment_type: str) -> tuple[str, str, str]:
    if payment_type == "received":
        return "sales", "sale", "customer"
    return "purchases", "purchase", "supplier"


def _receipt_no(conn: Any, business_id: int, payment_type: str) -> str:
    prefix = "RCPT" if payment_type == "received" else "PAY"
    row = conn.execute(
        "SELECT id FROM payment_receipts WHERE business_id=? ORDER BY id DESC LIMIT 1",
        (business_id,),
    ).fetchone()
    sequence = int(row["id"] if row else 0) + 1
    return f"{prefix}-{sequence:06d}"


def _party(conn: Any, business_id: int, party_id: int, expected: str) -> Any:
    row = conn.execute(
        "SELECT * FROM parties WHERE id=? AND business_id=?",
        (party_id, business_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Party not found")
    if row["type"] not in {expected, "both"}:
        label = "customer" if expected == "customer" else "supplier"
        raise HTTPException(status_code=400, detail=f"Selected party is not a {label}")
    return row


def _open_bills(conn: Any, business_id: int, party_id: int, payment_type: str) -> list[dict[str, Any]]:
    table, reference_type, _ = _expected_kind(payment_type)
    rows = conn.execute(
        f"""
        SELECT id,invoice_no,invoice_date,total,paid,due,payment_mode,notes,created_at
        FROM {table}
        WHERE business_id=? AND party_id=? AND due>0.009
        ORDER BY invoice_date ASC,id ASC
        LIMIT 1000
        """,
        (business_id, party_id),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["reference_type"] = reference_type
        item["status"] = "partial" if float(item.get("paid") or 0) > 0 else "unpaid"
        output.append(item)
    return output


@app.get("/api/parties/{party_id}/open-bills")
def party_open_bills(
    party_id: int,
    payment_type: Literal["received", "paid"] = Query(default="received"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    table, reference_type, expected = _expected_kind(payment_type)
    del table, reference_type
    with db() as conn:
        party = _party(conn, user["business_id"], party_id, expected)
        bills = _open_bills(conn, user["business_id"], party_id, payment_type)
    return {
        "party": dict(party),
        "payment_type": payment_type,
        "bills": bills,
        "bill_count": len(bills),
        "total_due": round(sum(float(row["due"] or 0) for row in bills), 2),
    }


@app.post("/api/payments/linked")
def create_linked_payment(
    payload: LinkedPaymentIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot create payments")
    amount = round(float(payload.amount or 0), 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    table, reference_type, expected = _expected_kind(payload.payment_type)
    with db() as conn:
        party = _party(conn, user["business_id"], payload.party_id, expected)

        account_id = payload.account_id
        if account_id is not None:
            account = conn.execute(
                "SELECT id FROM accounts WHERE id=? AND business_id=?",
                (account_id, user["business_id"]),
            ).fetchone()
            if not account:
                raise HTTPException(status_code=404, detail="Payment account not found")
        else:
            wanted = "bank" if payload.mode.lower() in {"bank", "upi", "card", "cheque"} else "cash"
            account = conn.execute(
                "SELECT id FROM accounts WHERE business_id=? AND account_type=? ORDER BY is_default DESC,id LIMIT 1",
                (user["business_id"], wanted),
            ).fetchone()
            if not account:
                account = conn.execute(
                    "SELECT id FROM accounts WHERE business_id=? ORDER BY is_default DESC,id LIMIT 1",
                    (user["business_id"],),
                ).fetchone()
            account_id = int(account["id"]) if account else None

        seen: set[int] = set()
        validated: list[dict[str, Any]] = []
        allocated_total = 0.0
        for allocation in payload.allocations:
            if allocation.reference_type != reference_type:
                raise HTTPException(status_code=400, detail="Payment type and selected bill type do not match")
            if allocation.reference_id in seen:
                raise HTTPException(status_code=400, detail="Same bill selected more than once")
            seen.add(allocation.reference_id)
            allocated = round(float(allocation.amount or 0), 2)
            if allocated <= 0:
                continue
            bill = conn.execute(
                f"""
                SELECT id,invoice_no,invoice_date,total,paid,due
                FROM {table}
                WHERE id=? AND business_id=? AND party_id=?
                """,
                (allocation.reference_id, user["business_id"], payload.party_id),
            ).fetchone()
            if not bill:
                raise HTTPException(status_code=404, detail="Selected bill not found for this party")
            due_before = round(float(bill["due"] or 0), 2)
            if allocated > due_before + 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"{bill['invoice_no']} allocation exceeds pending balance",
                )
            allocated_total = round(allocated_total + allocated, 2)
            validated.append({"bill": bill, "amount": allocated})

        if allocated_total > amount + 0.01:
            raise HTTPException(status_code=400, detail="Bill allocation is greater than payment amount")
        unallocated = round(amount - allocated_total, 2)
        current_balance = round(float(party["balance"] or 0), 2)
        maximum_reasonable = max(
            current_balance,
            round(sum(float(row["due"] or 0) for row in _open_bills(conn, user["business_id"], payload.party_id, payload.payment_type)), 2),
        )
        if amount > maximum_reasonable + 0.01:
            raise HTTPException(status_code=400, detail="Payment is greater than party outstanding")

        receipt_no = _receipt_no(conn, user["business_id"], payload.payment_type)
        cursor = conn.execute(
            """
            INSERT INTO payment_receipts(
                business_id,receipt_no,payment_type,party_id,party_name,payment_date,
                amount,allocated_amount,unallocated_amount,mode,account_id,note,created_by,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user["business_id"], receipt_no, payload.payment_type, payload.party_id,
                party["name"], normalize_date(payload.payment_date), amount, allocated_total,
                unallocated, payload.mode, account_id, payload.note.strip(), user.get("user_id"), now_iso(),
            ),
        )
        payment_id = int(cursor.lastrowid)

        allocation_rows: list[dict[str, Any]] = []
        for item in validated:
            bill = item["bill"]
            allocated = item["amount"]
            due_before = round(float(bill["due"] or 0), 2)
            due_after = max(0.0, round(due_before - allocated, 2))
            paid_after = min(round(float(bill["total"] or 0), 2), round(float(bill["paid"] or 0) + allocated, 2))
            conn.execute(
                f"UPDATE {table} SET paid=?,due=? WHERE id=? AND business_id=?",
                (paid_after, due_after, bill["id"], user["business_id"]),
            )
            conn.execute(
                """
                INSERT INTO payment_allocations(
                    payment_id,reference_type,reference_id,invoice_no,invoice_date,bill_total,
                    balance_before,allocated_amount,balance_after,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    payment_id, reference_type, bill["id"], bill["invoice_no"], bill["invoice_date"],
                    bill["total"], due_before, allocated, due_after, now_iso(),
                ),
            )
            allocation_rows.append({
                "reference_type": reference_type,
                "reference_id": int(bill["id"]),
                "invoice_no": bill["invoice_no"],
                "invoice_date": bill["invoice_date"],
                "bill_total": bill["total"],
                "balance_before": due_before,
                "allocated_amount": allocated,
                "balance_after": due_after,
            })

        new_party_balance = max(0.0, round(current_balance - amount, 2))
        conn.execute(
            "UPDATE parties SET balance=?,updated_at=? WHERE id=? AND business_id=?",
            (new_party_balance, now_iso(), payload.party_id, user["business_id"]),
        )
        entry_type = "payment_received" if payload.payment_type == "received" else "payment_paid"
        note_parts = [receipt_no]
        if allocation_rows:
            note_parts.append(", ".join(row["invoice_no"] for row in allocation_rows[:8]))
        if payload.note.strip():
            note_parts.append(payload.note.strip())
        conn.execute(
            """
            INSERT INTO ledger_entries(
                business_id,party_id,entry_date,entry_type,reference_type,reference_id,
                debit,credit,note,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user["business_id"], payload.party_id, normalize_date(payload.payment_date),
                entry_type, "linked_payment", payment_id, 0, amount,
                " · ".join(note_parts), now_iso(),
            ),
        )
        if account_id:
            account_delta = amount if payload.payment_type == "received" else -amount
            conn.execute(
                "UPDATE accounts SET balance=balance+?,updated_at=? WHERE id=? AND business_id=?",
                (account_delta, now_iso(), account_id, user["business_id"]),
            )

        receipt = dict(conn.execute("SELECT * FROM payment_receipts WHERE id=?", (payment_id,)).fetchone())
        updated_party = dict(conn.execute("SELECT * FROM parties WHERE id=?", (payload.party_id,)).fetchone())

    receipt["allocations"] = allocation_rows
    receipt["party"] = updated_party
    return receipt


@app.get("/api/payments/linked")
def list_linked_payments(
    payment_type: str = "",
    party_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM payment_receipts WHERE business_id=?"
    args: list[Any] = [user["business_id"]]
    if payment_type in {"received", "paid"}:
        sql += " AND payment_type=?"
        args.append(payment_type)
    if party_id:
        sql += " AND party_id=?"
        args.append(party_id)
    sql += " ORDER BY payment_date DESC,id DESC LIMIT ?"
    args.append(limit)
    with db() as conn:
        rows = [dict(row) for row in conn.execute(sql, args).fetchall()]
        for row in rows:
            row["allocations"] = [
                dict(item) for item in conn.execute(
                    "SELECT * FROM payment_allocations WHERE payment_id=? ORDER BY id",
                    (row["id"],),
                ).fetchall()
            ]
    return rows


# This extension is imported last. It serves one complete root document so all
# previous browser modules remain active, including the duplicate-import button.
@app.middleware("http")
async def inject_payment_assets(request, call_next):
    if request.method == "GET" and request.url.path == "/":
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace(
            "</head>",
            '<link rel="stylesheet" href="/settings-v2.css?v=042" /></head>',
        )
        html = html.replace(
            "</body>",
            '<script src="/settings-v2.js?v=042"></script>'
            '<script src="/import-fix.js?v=044"></script>'
            '<script src="/activity-navigation.js?v=046"></script>'
            '<script src="/sale-item-picker.js?v=044"></script>'
            '<script src="/manual-sale-cleanup.js?v=047"></script>'
            '<script src="/payment-link.js?v=048"></script></body>',
        )
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return await call_next(request)


new_paths = {
    "/api/parties/{party_id}/open-bills",
    "/api/payments/linked",
}
new_routes = [route for route in app.router.routes if getattr(route, "path", None) in new_paths]
for route in new_routes:
    app.router.routes.remove(route)
fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback_index:fallback_index] = new_routes
