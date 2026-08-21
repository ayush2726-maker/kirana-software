from __future__ import annotations

import sqlite3
from typing import Any

from backend import alexa_https_ext as alexa
from backend.app import TransactionIn, TxLineIn, db, insert_sale


def _safe_find_item(phrase: str) -> dict[str, Any] | None:
    """Resolve items without silently substituting the wrong size variant."""
    bid = alexa._business_id()
    name, requested_size = alexa._split_item_phrase(phrase)
    if not name:
        return None
    with db() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM items
                WHERE business_id=? AND COALESCE(archived_at,'')='' AND name LIKE ?
                ORDER BY name,size LIMIT 100
                """,
                (bid, f"%{name}%"),
            ).fetchall()
        ]
    if not rows:
        return None
    name_cf = name.casefold()
    candidates = [r for r in rows if name_cf in str(r.get("name", "")).casefold()] or rows
    if requested_size:
        sized = [r for r in candidates if alexa._normalize_size(r.get("size", "")) == requested_size]
        if not sized:
            return None
        candidates = sized
    exact = [r for r in candidates if str(r.get("name", "")).casefold() == name_cf]
    return exact[0] if exact else candidates[0]


def _request_id(handler_input) -> str:
    request = getattr(handler_input.request_envelope, "request", None)
    return str(getattr(request, "request_id", "") or "").strip()


def _complete_bill_once(self, handler_input):
    """Create at most one sale for an Alexa request ID.

    Alexa can retry a request when a response is delayed. A unique request ID
    marker prevents a retry from creating a second invoice/stock movement.
    """
    attrs = alexa._attrs(handler_input)
    customer = attrs.get("customer")
    cart = attrs.get("cart") or []
    if not customer:
        return alexa._speak(handler_input, "Pehle customer select karo.", "Customer ka naam bolo.")
    if not cart:
        return alexa._speak(handler_input, "Bill mein item nahi hai. Pehle item add karo.", "Item bolo.")

    request_id = _request_id(handler_input)
    bid = alexa._business_id()

    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alexa_request_receipts (
                request_id TEXT PRIMARY KEY,
                business_id INTEGER NOT NULL,
                sale_id INTEGER,
                invoice_no TEXT DEFAULT '',
                total REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        if request_id:
            previous = conn.execute(
                "SELECT invoice_no,total FROM alexa_request_receipts WHERE request_id=? AND business_id=?",
                (request_id, bid),
            ).fetchone()
            if previous and previous["invoice_no"]:
                attrs["cart"] = []
                return alexa._speak(
                    handler_input,
                    f"Bill pehle hi ban chuka hai. Total {alexa._money(previous['total'])} rupaye. Bill number {previous['invoice_no']}.",
                    end=True,
                )
            try:
                conn.execute(
                    "INSERT INTO alexa_request_receipts(request_id,business_id) VALUES(?,?)",
                    (request_id, bid),
                )
            except sqlite3.IntegrityError:
                previous = conn.execute(
                    "SELECT invoice_no,total FROM alexa_request_receipts WHERE request_id=? AND business_id=?",
                    (request_id, bid),
                ).fetchone()
                if previous and previous["invoice_no"]:
                    attrs["cart"] = []
                    return alexa._speak(
                        handler_input,
                        f"Bill pehle hi ban chuka hai. Total {alexa._money(previous['total'])} rupaye. Bill number {previous['invoice_no']}.",
                        end=True,
                    )
                raise

        payload = TransactionIn(
            party_id=int(customer["id"]),
            paid=0,
            payment_mode="cash",
            notes="Created by Alexa HTTPS",
            items=[TxLineIn(**line) for line in cart],
        )
        sale = insert_sale(conn, bid, payload)
        if request_id:
            conn.execute(
                "UPDATE alexa_request_receipts SET sale_id=?,invoice_no=?,total=? WHERE request_id=?",
                (sale.get("id"), sale.get("invoice_no", ""), float(sale.get("total") or 0), request_id),
            )

    attrs["cart"] = []
    return alexa._speak(
        handler_input,
        f"Bill ban gaya. Total {alexa._money(sale.get('total'))} rupaye. Bill number {sale.get('invoice_no', '')}.",
        end=True,
    )


# Handler instances already exist inside the ASK Skill object, but Python
# resolves methods and module globals at call time, so these patches safely
# harden the existing live handlers without rebuilding the interaction model.
alexa._find_item = _safe_find_item
alexa.CompleteBillIntentHandler.handle = _complete_bill_once
