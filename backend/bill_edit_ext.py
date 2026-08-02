from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

import backend.app as core
from backend.app import app, current_user, db, normalize_date, now_iso
import backend.transaction_detail_ext as transaction_detail


VERSION = "130"
SUPPORTED_KINDS = {"sale", "purchase", "sale_return", "purchase_return"}


class BillEditLineIn(BaseModel):
    item_id: int | None = None
    item_name: str = ""
    size: str = ""
    qty: float = Field(gt=0)
    rate: float = Field(ge=0)
    gst_rate: float = Field(default=0, ge=0)


class BillEditIn(BaseModel):
    number: str = ""
    party_id: int | None = None
    date: str
    reference_no: str = ""
    discount: float = Field(default=0, ge=0)
    initial_paid: float = Field(default=0, ge=0)
    payment_mode: str = "cash"
    notes: str = ""
    items: list[BillEditLineIn] = Field(min_items=1)


def _clean_kind(kind: str) -> str:
    value = str(kind or "").strip().lower()
    if value not in SUPPORTED_KINDS:
        raise HTTPException(status_code=400, detail="This bill type cannot be edited")
    return value


def _table_exists(conn: Any, table: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    )


def _allocated_amount(conn: Any, kind: str, transaction_id: int) -> float:
    if kind not in {"sale", "purchase"} or not _table_exists(conn, "payment_allocations"):
        return 0.0
    row = conn.execute(
        """
        SELECT COALESCE(SUM(allocated_amount),0) AS amount
        FROM payment_allocations
        WHERE reference_type=? AND reference_id=?
        """,
        (kind, transaction_id),
    ).fetchone()
    return round(float(row["amount"] or 0), 2) if row else 0.0


def _load_bill(conn: Any, business_id: int, kind: str, transaction_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if kind == "sale":
        row = conn.execute(
            "SELECT * FROM sales WHERE id=? AND business_id=?",
            (transaction_id, business_id),
        ).fetchone()
        line_rows = conn.execute(
            "SELECT * FROM sale_items WHERE sale_id=? ORDER BY id",
            (transaction_id,),
        ).fetchall() if row else []
    elif kind == "purchase":
        row = conn.execute(
            "SELECT * FROM purchases WHERE id=? AND business_id=?",
            (transaction_id, business_id),
        ).fetchone()
        line_rows = conn.execute(
            "SELECT * FROM purchase_items WHERE purchase_id=? ORDER BY id",
            (transaction_id,),
        ).fetchall() if row else []
    else:
        row = conn.execute(
            "SELECT * FROM returns WHERE id=? AND business_id=? AND kind=?",
            (transaction_id, business_id, kind),
        ).fetchone()
        line_rows = conn.execute(
            "SELECT * FROM return_items WHERE return_id=? ORDER BY id",
            (transaction_id,),
        ).fetchall() if row else []
    if not row:
        raise HTTPException(status_code=404, detail="Bill not found")
    return dict(row), [dict(item) for item in line_rows]


def _detail(conn: Any, business_id: int, kind: str, transaction_id: int) -> dict[str, Any]:
    detail = transaction_detail._bill_detail(conn, business_id, kind, transaction_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Bill details were not found")
    allocated = _allocated_amount(conn, kind, transaction_id)
    detail["allocated_paid"] = allocated
    detail["initial_paid"] = max(0.0, round(float(detail.get("paid") or 0) - allocated, 2))
    return detail


def _party_rows(conn: Any, business_id: int, kind: str) -> list[dict[str, Any]]:
    expected = "customer" if kind in {"sale", "sale_return"} else "supplier"
    rows = conn.execute(
        """
        SELECT id,name,type,phone,balance
        FROM parties
        WHERE business_id=? AND type IN (?, 'both')
        ORDER BY name COLLATE NOCASE
        """,
        (business_id, expected),
    ).fetchall()
    return [dict(row) for row in rows]


def _item_rows(conn: Any, business_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id,name,size,unit,sku,stock,sale_price,purchase_price,gst_rate
        FROM items
        WHERE business_id=?
        ORDER BY name COLLATE NOCASE,size COLLATE NOCASE,id
        LIMIT 5000
        """,
        (business_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _stock_sign(kind: str) -> int:
    return {
        "sale": -1,
        "purchase": 1,
        "sale_return": 1,
        "purchase_return": -1,
    }[kind]


def _account_sign(kind: str) -> int:
    return {
        "sale": 1,
        "purchase": -1,
        "sale_return": -1,
        "purchase_return": 1,
    }[kind]


def _update_party_balance(conn: Any, business_id: int, party_id: int | None, amount: float, clamp: bool = False) -> None:
    if not party_id or abs(amount) < 0.005:
        return
    if clamp:
        conn.execute(
            "UPDATE parties SET balance=max(0,balance+?),updated_at=? WHERE id=? AND business_id=?",
            (amount, now_iso(), party_id, business_id),
        )
    else:
        conn.execute(
            "UPDATE parties SET balance=round(balance+?,2),updated_at=? WHERE id=? AND business_id=?",
            (amount, now_iso(), party_id, business_id),
        )


def _refresh_allocations(
    conn: Any,
    kind: str,
    transaction_id: int,
    number: str,
    transaction_date: str,
    total: float,
    initial_paid: float,
) -> float:
    if kind not in {"sale", "purchase"} or not _table_exists(conn, "payment_allocations"):
        return 0.0
    rows = conn.execute(
        """
        SELECT id,allocated_amount
        FROM payment_allocations
        WHERE reference_type=? AND reference_id=?
        ORDER BY id
        """,
        (kind, transaction_id),
    ).fetchall()
    running = max(0.0, round(total - initial_paid, 2))
    allocated_total = 0.0
    for row in rows:
        allocated = round(float(row["allocated_amount"] or 0), 2)
        before = running
        after = max(0.0, round(before - allocated, 2))
        conn.execute(
            """
            UPDATE payment_allocations
            SET invoice_no=?,invoice_date=?,bill_total=?,balance_before=?,balance_after=?
            WHERE id=?
            """,
            (number, transaction_date, total, before, after, row["id"]),
        )
        running = after
        allocated_total = round(allocated_total + allocated, 2)
    return allocated_total


def _insert_ledger(
    conn: Any,
    business_id: int,
    kind: str,
    transaction_id: int,
    party_id: int | None,
    transaction_date: str,
    amount: float,
    note: str,
) -> None:
    if not party_id or amount <= 0.005:
        return
    if kind in {"sale", "purchase"}:
        debit, credit = amount, 0
    else:
        debit, credit = 0, amount
    conn.execute(
        """
        INSERT INTO ledger_entries(
            business_id,party_id,entry_date,entry_type,reference_type,reference_id,
            debit,credit,note,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            business_id, party_id, transaction_date, kind, kind, transaction_id,
            debit, credit, note, now_iso(),
        ),
    )


@app.get("/api/bill-edit/{kind}/{transaction_id}")
def get_bill_for_edit(
    kind: str,
    transaction_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    clean_kind = _clean_kind(kind)
    if transaction_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid bill")
    business_id = int(user["business_id"])
    with db() as conn:
        _load_bill(conn, business_id, clean_kind, transaction_id)
        detail = _detail(conn, business_id, clean_kind, transaction_id)
        return {
            "bill": detail,
            "parties": _party_rows(conn, business_id, clean_kind),
            "items": _item_rows(conn, business_id),
            "party_locked": bool(detail.get("allocated_paid")),
        }


@app.put("/api/bill-edit/{kind}/{transaction_id}")
def update_bill(
    kind: str,
    transaction_id: int,
    payload: BillEditIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    clean_kind = _clean_kind(kind)
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot edit bills")
    if transaction_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid bill")

    business_id = int(user["business_id"])
    with db() as conn:
        old, old_lines = _load_bill(conn, business_id, clean_kind, transaction_id)
        allocated = _allocated_amount(conn, clean_kind, transaction_id)
        if allocated and int(old.get("party_id") or 0) != int(payload.party_id or 0):
            raise HTTPException(
                status_code=400,
                detail="Linked payment laga hai, isliye party change nahi kar sakte",
            )

        expected_party = "customer" if clean_kind in {"sale", "sale_return"} else "supplier"
        party = core.get_party(conn, business_id, payload.party_id, expected_party)
        rate_field = "sale_price" if clean_kind in {"sale", "sale_return"} else "purchase_price"
        lines, subtotal, tax = core.calculate_lines(conn, business_id, payload.items, rate_field)
        total = max(0.0, round(subtotal + tax - float(payload.discount or 0), 2))
        if allocated > total + 0.005:
            raise HTTPException(
                status_code=400,
                detail="New bill total linked payment se kam nahi ho sakta",
            )
        maximum_initial_paid = max(0.0, round(total - allocated, 2))
        initial_paid = min(round(float(payload.initial_paid or 0), 2), maximum_initial_paid)
        paid = round(initial_paid + allocated, 2)
        due = max(0.0, round(total - paid, 2))
        transaction_date = normalize_date(payload.date)
        number = payload.number.strip()

        if clean_kind in {"sale", "purchase"}:
            number = number or str(old.get("invoice_no") or "")
            old_base_paid = max(0.0, round(float(old.get("paid") or 0) - allocated, 2))
            old_initial_due = max(0.0, round(float(old.get("total") or 0) - old_base_paid, 2))
            new_initial_due = max(0.0, round(total - initial_paid, 2))
        else:
            number = number or str(old.get("return_no") or "")
            old_base_paid = round(float(old.get("paid") or 0), 2)
            old_initial_due = round(float(old.get("due") or 0), 2)
            new_initial_due = due

        stock_sign = _stock_sign(clean_kind)
        for line in old_lines:
            if line.get("item_id"):
                conn.execute(
                    "UPDATE items SET stock=stock-?,updated_at=? WHERE id=? AND business_id=?",
                    (
                        stock_sign * float(line.get("qty") or 0),
                        now_iso(), line["item_id"], business_id,
                    ),
                )

        conn.execute(
            "DELETE FROM stock_movements WHERE business_id=? AND reference_type=? AND reference_id=?",
            (business_id, clean_kind, transaction_id),
        )
        conn.execute(
            "DELETE FROM ledger_entries WHERE business_id=? AND reference_type=? AND reference_id=?",
            (business_id, clean_kind, transaction_id),
        )

        old_account_delta = _account_sign(clean_kind) * old_base_paid
        core.adjust_account(conn, business_id, str(old.get("payment_mode") or "cash"), -old_account_delta)

        if clean_kind in {"sale", "purchase"}:
            _update_party_balance(
                conn, business_id, old.get("party_id"), -old_initial_due,
            )
            _update_party_balance(
                conn, business_id, payload.party_id, new_initial_due,
            )
        else:
            _update_party_balance(
                conn, business_id, old.get("party_id"), old_initial_due,
            )
            _update_party_balance(
                conn, business_id, payload.party_id, -new_initial_due, clamp=True,
            )

        try:
            if clean_kind == "sale":
                conn.execute(
                    """
                    UPDATE sales
                    SET invoice_no=?,party_id=?,party_name=?,invoice_date=?,subtotal=?,discount=?,tax=?,
                        total=?,paid=?,due=?,payment_mode=?,notes=?
                    WHERE id=? AND business_id=?
                    """,
                    (
                        number, payload.party_id, party["name"] if party else "Cash Customer",
                        transaction_date, subtotal, payload.discount, tax, total, paid, due,
                        payload.payment_mode, payload.notes, transaction_id, business_id,
                    ),
                )
                line_table, foreign_key = "sale_items", "sale_id"
            elif clean_kind == "purchase":
                conn.execute(
                    """
                    UPDATE purchases
                    SET invoice_no=?,party_id=?,party_name=?,invoice_date=?,subtotal=?,discount=?,tax=?,
                        total=?,paid=?,due=?,payment_mode=?,notes=?
                    WHERE id=? AND business_id=?
                    """,
                    (
                        number, payload.party_id, party["name"] if party else "Cash Supplier",
                        transaction_date, subtotal, payload.discount, tax, total, paid, due,
                        payload.payment_mode, payload.notes, transaction_id, business_id,
                    ),
                )
                line_table, foreign_key = "purchase_items", "purchase_id"
            else:
                conn.execute(
                    """
                    UPDATE returns
                    SET return_no=?,party_id=?,party_name=?,return_date=?,reference_no=?,subtotal=?,
                        discount=?,tax=?,total=?,paid=?,due=?,payment_mode=?,notes=?
                    WHERE id=? AND business_id=? AND kind=?
                    """,
                    (
                        number, payload.party_id,
                        party["name"] if party else ("Cash Customer" if clean_kind == "sale_return" else "Cash Supplier"),
                        transaction_date, payload.reference_no.strip(), subtotal, payload.discount,
                        tax, total, paid, due, payload.payment_mode, payload.notes,
                        transaction_id, business_id, clean_kind,
                    ),
                )
                line_table, foreign_key = "return_items", "return_id"
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail=f"Bill number {number} already exists") from exc

        conn.execute(f"DELETE FROM {line_table} WHERE {foreign_key}=?", (transaction_id,))
        for line in lines:
            conn.execute(
                f"""
                INSERT INTO {line_table}(
                    {foreign_key},item_id,item_name,size,qty,rate,gst_rate,line_subtotal,line_tax,line_total
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    transaction_id, line["item_id"], line["item_name"], line["size"],
                    line["qty"], line["rate"], line["gst_rate"], line["line_subtotal"],
                    line["line_tax"], line["line_total"],
                ),
            )
            if line["item_id"]:
                delta = stock_sign * float(line["qty"])
                if clean_kind == "purchase":
                    conn.execute(
                        "UPDATE items SET stock=stock+?,purchase_price=?,updated_at=? WHERE id=? AND business_id=?",
                        (delta, line["rate"], now_iso(), line["item_id"], business_id),
                    )
                else:
                    conn.execute(
                        "UPDATE items SET stock=stock+?,updated_at=? WHERE id=? AND business_id=?",
                        (delta, now_iso(), line["item_id"], business_id),
                    )
                conn.execute(
                    """
                    INSERT INTO stock_movements(
                        business_id,item_id,movement_date,kind,qty,reference_type,reference_id,note,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        business_id, line["item_id"], transaction_date, clean_kind, delta,
                        clean_kind, transaction_id, number, now_iso(),
                    ),
                )

        new_account_delta = _account_sign(clean_kind) * initial_paid
        core.adjust_account(conn, business_id, payload.payment_mode, new_account_delta)
        _insert_ledger(
            conn, business_id, clean_kind, transaction_id, payload.party_id,
            transaction_date, new_initial_due, number,
        )

        allocated = _refresh_allocations(
            conn, clean_kind, transaction_id, number, transaction_date, total, initial_paid,
        )
        if clean_kind in {"sale", "purchase"}:
            paid = round(initial_paid + allocated, 2)
            due = max(0.0, round(total - paid, 2))
            table = "sales" if clean_kind == "sale" else "purchases"
            conn.execute(
                f"UPDATE {table} SET paid=?,due=? WHERE id=? AND business_id=?",
                (paid, due, transaction_id, business_id),
            )

        detail = _detail(conn, business_id, clean_kind, transaction_id)
        return {"bill": detail, "message": "Bill updated successfully"}


_edit_routes = [
    route for route in list(app.router.routes)
    if getattr(route, "path", None) in {
        "/api/bill-edit/{kind}/{transaction_id}",
    }
]
for route in _edit_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _edit_routes
