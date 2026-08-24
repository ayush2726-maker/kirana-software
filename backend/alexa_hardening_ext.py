from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from ask_sdk_webservice_support.webservice_handler import WebserviceSkillHandler

from backend import alexa_https_ext as alexa
from backend.app import TransactionIn, TxLineIn, db, insert_sale
from backend.customer_catalog_15day_fix_ext import recommended_rate_15day


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _safe_find_item(phrase: str) -> dict[str, Any] | None:
    """Prefer exact/canonical matches and never silently substitute a wrong size."""
    bid = alexa._business_id()
    name, requested_size = alexa._split_item_phrase(phrase)
    if not name:
        return None
    with db() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT * FROM items
            WHERE business_id=? AND COALESCE(archived_at,'')='' AND name LIKE ?
            ORDER BY name,size,id LIMIT 100
            """,
            (bid, f"%{name}%"),
        ).fetchall()]
    if not rows:
        return None

    query = _norm(name)
    if requested_size:
        rows = [r for r in rows if alexa._normalize_size(r.get("size", "")) == requested_size]
        if not rows:
            return None

    def score(row: dict[str, Any]) -> tuple[int, int, int, int]:
        item_name = _norm(row.get("name"))
        words = set(re.findall(r"[\w]+", item_name))
        exact = 4 if item_name == query else 0
        starts = 3 if item_name.startswith(query + " ") else 0
        word = 2 if query in words else 0
        contains = 1 if query in item_name else 0
        priced = 1 if float(row.get("sale_price") or 0) > 0 else 0
        # Higher textual match wins first; then prefer a usable priced canonical row;
        # finally shorter names avoid odd code-prefixed matches such as "147 gehu".
        return (max(exact, starts, word, contains), priced, -len(item_name), -int(row.get("id") or 0))

    best = max(rows, key=score)
    if score(best)[0] <= 0:
        return None
    return best


def _effective_rate(item_id: int, party_id: int | None) -> tuple[float, str]:
    bid = alexa._business_id()
    with db() as conn:
        if party_id:
            result = recommended_rate_15day(conn, bid, int(party_id), int(item_id))
            return float(result.get("rate") or 0), str(result.get("rate_source") or "item")
        row = conn.execute(
            "SELECT sale_price FROM items WHERE id=? AND business_id=?",
            (int(item_id), bid),
        ).fetchone()
        return float((row["sale_price"] if row else 0) or 0), "item"


def _add_item_with_customer_rate(self, handler_input):
    phrase = alexa._slot(handler_input, "item")
    qty_text = alexa._slot(handler_input, "quantity")
    try:
        qty = float(qty_text) if qty_text else 1.0
    except ValueError:
        qty = 1.0
    qty = qty if qty > 0 else 1.0

    item = _safe_find_item(phrase)
    if not item:
        return alexa._speak(handler_input, f"{phrase} item nahi mila. Naam ya size dobara bolo.", "Item bolo.")

    attrs = alexa._attrs(handler_input)
    customer = attrs.get("customer") or {}
    rate, source = _effective_rate(int(item["id"]), int(customer["id"]) if customer.get("id") else None)
    cart = attrs.setdefault("cart", [])
    cart.append({
        "item_id": int(item["id"]),
        "item_name": str(item["name"]),
        "size": str(item.get("size") or ""),
        "qty": qty,
        "rate": rate,
        "gst_rate": float(item.get("gst_rate") or 0),
    })
    size = f" {item.get('size')}" if item.get("size") else ""
    source_text = {
        "fixed": "customer rate",
        "recent_15_days": "recent bill rate",
        "catalog": "default customer rate",
    }.get(source, "item rate")
    return alexa._speak(
        handler_input,
        f"{alexa._money(qty)} {item['name']}{size}, rate {alexa._money(rate)} rupaye, {source_text}, add ho gaya. Aur item?",
        "Aur item bolo, ya bill bana do.",
    )


def _check_rate_with_customer(self, handler_input):
    phrase = alexa._slot(handler_input, "item")
    item = _safe_find_item(phrase)
    if not item:
        return alexa._speak(handler_input, f"{phrase} item nahi mila.", "Dusra item bolo.")
    attrs = alexa._attrs(handler_input)
    customer = attrs.get("customer") or {}
    rate, _source = _effective_rate(int(item["id"]), int(customer["id"]) if customer.get("id") else None)
    size = f" {item.get('size')}" if item.get("size") else ""
    return alexa._speak(handler_input, f"{item['name']}{size} ka rate {alexa._money(rate)} rupaye hai.")


def _request_id(handler_input) -> str:
    request = getattr(handler_input.request_envelope, "request", None)
    return str(getattr(request, "request_id", "") or "").strip()


def _complete_bill_once(self, handler_input):
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alexa_request_receipts (
                request_id TEXT PRIMARY KEY, business_id INTEGER NOT NULL,
                sale_id INTEGER, invoice_no TEXT DEFAULT '', total REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
        if request_id:
            previous = conn.execute("SELECT invoice_no,total FROM alexa_request_receipts WHERE request_id=? AND business_id=?", (request_id, bid)).fetchone()
            if previous and previous["invoice_no"]:
                attrs["cart"] = []
                return alexa._speak(handler_input, f"Bill pehle hi ban chuka hai. Total {alexa._money(previous['total'])} rupaye. Bill number {previous['invoice_no']}.", end=True)
            try:
                conn.execute("INSERT INTO alexa_request_receipts(request_id,business_id) VALUES(?,?)", (request_id, bid))
            except sqlite3.IntegrityError:
                previous = conn.execute("SELECT invoice_no,total FROM alexa_request_receipts WHERE request_id=? AND business_id=?", (request_id, bid)).fetchone()
                if previous and previous["invoice_no"]:
                    attrs["cart"] = []
                    return alexa._speak(handler_input, f"Bill pehle hi ban chuka hai. Total {alexa._money(previous['total'])} rupaye. Bill number {previous['invoice_no']}.", end=True)
                raise

        payload = TransactionIn(
            party_id=int(customer["id"]), paid=0, payment_mode="cash",
            notes="Created by Alexa HTTPS", items=[TxLineIn(**line) for line in cart],
        )
        sale = insert_sale(conn, bid, payload)
        if request_id:
            conn.execute(
                "UPDATE alexa_request_receipts SET sale_id=?,invoice_no=?,total=? WHERE request_id=?",
                (sale.get("id"), sale.get("invoice_no", ""), float(sale.get("total") or 0), request_id),
            )

    attrs["cart"] = []
    return alexa._speak(handler_input, f"Bill ban gaya. Total {alexa._money(sale.get('total'))} rupaye. Bill number {sale.get('invoice_no', '')}.", end=True)


class _ManualTestAwareWebserviceHandler:
    """Keep production verification strict while supporting signed Console Manual JSON."""

    def __init__(self, strict_handler):
        self.strict_handler = strict_handler
        self.manual_test_handler = WebserviceSkillHandler(skill=alexa.sb.create(), verify_signature=True, verify_timestamp=False)

    @staticmethod
    def _is_console_manual_test(raw_body: str) -> bool:
        try:
            payload = json.loads(raw_body)
        except Exception:
            return False
        session = payload.get("session") or {}
        context_system = ((payload.get("context") or {}).get("System") or {})
        user_id = str(((session.get("user") or {}).get("userId")) or ((context_system.get("user") or {}).get("userId")) or "")
        device_id = str(((context_system.get("device") or {}).get("deviceId")) or "")
        request_id = str(((payload.get("request") or {}).get("requestId")) or "")
        return user_id == "amzn1.ask.account.test-user" and device_id == "test-device" and request_id.startswith("amzn1.echo-api.request.")

    @staticmethod
    def _as_json_text(result):
        if isinstance(result, (str, bytes, bytearray)):
            return result
        return json.dumps(result)

    def verify_request_and_dispatch(self, http_request_headers, http_request_body):
        if self._is_console_manual_test(http_request_body):
            print("Alexa Manual JSON test: signature verified, timestamp-age check skipped", flush=True)
            result = self.manual_test_handler.verify_request_and_dispatch(http_request_headers=http_request_headers, http_request_body=http_request_body)
            return self._as_json_text(result)
        result = self.strict_handler.verify_request_and_dispatch(http_request_headers=http_request_headers, http_request_body=http_request_body)
        return self._as_json_text(result)


alexa._find_item = _safe_find_item
alexa.AddItemIntentHandler.handle = _add_item_with_customer_rate
alexa.CheckRateIntentHandler.handle = _check_rate_with_customer
alexa.CompleteBillIntentHandler.handle = _complete_bill_once
alexa.webservice_handler = _ManualTestAwareWebserviceHandler(alexa.webservice_handler)
