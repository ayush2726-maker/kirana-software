from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

import ask_sdk_core.utils as ask_utils
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_webservice_support.webservice_handler import WebserviceSkillHandler

from backend import alexa_https_ext as alexa
from backend.app import TransactionIn, TxLineIn, db, insert_sale
from backend.customer_catalog_15day_fix_ext import recommended_rate_15day


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _launch_shop_sathi(self, handler_input):
    attrs = alexa._attrs(handler_input)
    attrs["cart"] = []
    attrs.pop("customer", None)
    attrs.pop("pending_item", None)
    return alexa._speak(handler_input, "Shop Sathi ready hai. Customer ka naam bolo.", "Customer ka naam bolo.")


def _select_customer_clean(self, handler_input):
    query = alexa._slot(handler_input, "customer")
    customer = alexa._find_customer(query)
    if not customer:
        return alexa._speak(handler_input, f"{query} customer nahi mila. Dusra naam bolo.", "Customer ka naam bolo.")
    attrs = alexa._attrs(handler_input)
    attrs["customer"] = {"id": customer["id"], "name": customer["name"]}
    attrs["cart"] = []
    attrs.pop("pending_item", None)
    return alexa._speak(handler_input, f"{customer['name']} select ho gaya. Item bolo.", "Item bolo.")


def _candidate_rows(phrase: str) -> tuple[str, str, list[dict[str, Any]]]:
    bid = alexa._business_id()
    name, requested_size = alexa._split_item_phrase(phrase)
    query = _norm(name)
    if not query:
        return "", "", []
    with db() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT * FROM items
            WHERE business_id=? AND COALESCE(archived_at,'')='' AND name LIKE ?
            ORDER BY name,size,id LIMIT 150
            """,
            (bid, f"%{name}%"),
        ).fetchall()]
    if requested_size:
        rows = [r for r in rows if alexa._normalize_size(r.get("size", "")) == requested_size]
    if not re.match(r"^\d+\b", query):
        uncoded = [r for r in rows if not re.match(r"^\d+\b", _norm(r.get("name")))]
        if uncoded:
            rows = uncoded
    return query, requested_size, rows


def _resolve_item(phrase: str) -> tuple[str, dict[str, Any] | None, list[str]]:
    """Return ok / ambiguous / missing without silently selecting a different product family."""
    query, requested_size, rows = _candidate_rows(phrase)
    if not query or not rows:
        return "missing", None, []

    exact_name = [r for r in rows if _norm(r.get("name")) == query]
    pool = exact_name or rows

    distinct_names: list[str] = []
    seen_names: set[str] = set()
    for row in pool:
        key = _norm(row.get("name"))
        if key not in seen_names:
            seen_names.add(key)
            distinct_names.append(str(row.get("name") or ""))

    if not exact_name and len(distinct_names) > 1:
        return "ambiguous", None, distinct_names[:4]

    # If the exact product itself has several size/batch variants, do not guess a size.
    if not requested_size:
        sizes = []
        seen_sizes = set()
        for row in pool:
            size = str(row.get("size") or "").strip()
            key = _norm(size)
            if key not in seen_sizes:
                seen_sizes.add(key)
                sizes.append(size)
        meaningful_sizes = [s for s in sizes if s]
        if len(meaningful_sizes) > 1:
            return "ambiguous", None, [f"{distinct_names[0]} {s}" for s in meaningful_sizes[:4]]

    def score(row: dict[str, Any]) -> tuple[int, int, int]:
        item_name = _norm(row.get("name"))
        exact = 3 if item_name == query else 0
        starts = 2 if item_name.startswith(query + " ") else 0
        contains = 1 if query in item_name else 0
        priced = 1 if float(row.get("sale_price") or 0) > 0 else 0
        return (max(exact, starts, contains), priced, -int(row.get("id") or 0))

    best = max(pool, key=score)
    return ("ok", best, []) if score(best)[0] > 0 else ("missing", None, [])


def _safe_find_item(phrase: str) -> dict[str, Any] | None:
    status, item, _ = _resolve_item(phrase)
    return item if status == "ok" else None


def _effective_rate(item_id: int, party_id: int | None) -> tuple[float, str]:
    bid = alexa._business_id()
    with db() as conn:
        if party_id:
            result = recommended_rate_15day(conn, bid, int(party_id), int(item_id))
            return float(result.get("rate") or 0), str(result.get("rate_source") or "item")
        row = conn.execute("SELECT sale_price FROM items WHERE id=? AND business_id=?", (int(item_id), bid)).fetchone()
        return float((row["sale_price"] if row else 0) or 0), "item"


def _queue_item_and_ask_quantity(self, handler_input):
    phrase = alexa._slot(handler_input, "item")
    attrs = alexa._attrs(handler_input)

    if not attrs.get("customer"):
        customer_match = alexa._find_customer(phrase) if phrase else None
        if customer_match:
            attrs["customer"] = {"id": customer_match["id"], "name": customer_match["name"]}
            attrs["cart"] = []
            attrs.pop("pending_item", None)
            return alexa._speak(handler_input, f"{customer_match['name']} select ho gaya. Item bolo.", "Item bolo.")
        return alexa._speak(handler_input, "Pehle customer select karo.", "Customer ka naam bolo.")

    status, item, choices = _resolve_item(phrase)
    if status == "ambiguous":
        choice_text = ", ".join(choices)
        return alexa._speak(handler_input, f"{phrase} ke multiple item hain: {choice_text}. Exact item ya size bolo.", "Exact item naam ya size bolo.")
    if status != "ok" or not item:
        return alexa._speak(handler_input, f"{phrase} item nahi mila. Naam ya size dobara bolo.", "Item bolo.")

    attrs["pending_item"] = {
        "item_id": int(item["id"]),
        "item_name": str(item["name"]),
        "size": str(item.get("size") or ""),
        "gst_rate": float(item.get("gst_rate") or 0),
    }
    size = f" {item.get('size')}" if item.get("size") else ""
    return alexa._speak(handler_input, f"{item['name']}{size}. Kitni quantity?", "Quantity bolo, jaise 1 kilo ya 2 packet.")


def _unit_label(unit: str) -> str:
    unit = _norm(unit)
    mapping = {
        "kg": "kilo", "kilo": "kilo", "kilogram": "kilo",
        "gm": "gram", "gram": "gram",
        "packet": "packet", "pack": "packet", "pcs": "piece", "piece": "piece",
        "ltr": "litre", "litre": "litre", "liter": "litre",
    }
    return mapping.get(unit, unit)


class QuantityIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input) -> bool:
        return ask_utils.is_intent_name("QuantityIntent")(handler_input)

    def handle(self, handler_input):
        attrs = alexa._attrs(handler_input)
        pending = attrs.get("pending_item")
        if not attrs.get("customer"):
            return alexa._speak(handler_input, "Pehle customer select karo.", "Customer ka naam bolo.")
        if not pending:
            return alexa._speak(handler_input, "Pehle item bolo.", "Item bolo.")

        qty_text = alexa._slot(handler_input, "quantity")
        unit = alexa._slot(handler_input, "unit")
        try:
            qty = float(qty_text)
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            return alexa._speak(handler_input, "Quantity samajh nahi aayi. Dobara bolo.", "Jaise 1 kilo ya 2 packet.")

        customer = attrs.get("customer") or {}
        rate, source = _effective_rate(int(pending["item_id"]), int(customer["id"]) if customer.get("id") else None)
        if rate <= 0:
            item_name = str(pending.get("item_name") or "item")
            attrs.pop("pending_item", None)
            return alexa._speak(handler_input, f"{item_name} ka sale rate zero ya missing hai. Is item ko bill mein add nahi kiya. Dusra item ya sahi size bolo.", "Dusra item bolo.")

        attrs.setdefault("cart", []).append({
            "item_id": int(pending["item_id"]),
            "item_name": str(pending["item_name"]),
            "size": str(pending.get("size") or ""),
            "qty": qty,
            "rate": rate,
            "gst_rate": float(pending.get("gst_rate") or 0),
        })
        attrs.pop("pending_item", None)

        source_text = {"fixed": "customer rate", "recent_15_days": "recent bill rate", "catalog": "default customer rate"}.get(source, "item rate")
        spoken_unit = f" {_unit_label(unit)}" if unit else ""
        return alexa._speak(handler_input, f"{alexa._money(qty)}{spoken_unit} {pending['item_name']}, rate {alexa._money(rate)} rupaye, {source_text}, add ho gaya. Agla item bolo, ya bill bana do.", "Agla item bolo, ya bill bana do.")


def _check_rate_with_customer(self, handler_input):
    phrase = alexa._slot(handler_input, "item")
    status, item, choices = _resolve_item(phrase)
    if status == "ambiguous":
        return alexa._speak(handler_input, f"{phrase} ke multiple item hain: {', '.join(choices)}. Exact item bolo.", "Exact item bolo.")
    if status != "ok" or not item:
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
    if attrs.get("pending_item"):
        return alexa._speak(handler_input, "Pehle current item ki quantity bolo.", "Quantity bolo.")
    if not cart:
        return alexa._speak(handler_input, "Bill mein item nahi hai. Pehle item add karo.", "Item bolo.")
    bad_lines = [line for line in cart if float(line.get("rate") or 0) <= 0]
    if bad_lines:
        names = ", ".join(str(line.get("item_name") or "item") for line in bad_lines[:3])
        return alexa._speak(handler_input, f"Bill save nahi hoga. {names} ka rate zero ya missing hai. Pehle rate theek karo.", "Rate theek karke phir bill banao.")

    request_id = _request_id(handler_input)
    bid = alexa._business_id()
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alexa_request_receipts (
                request_id TEXT PRIMARY KEY, business_id INTEGER NOT NULL,
                sale_id INTEGER, invoice_no TEXT DEFAULT '', total REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
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

        payload = TransactionIn(party_id=int(customer["id"]), paid=0, payment_mode="cash", notes="Created by Alexa HTTPS", items=[TxLineIn(**line) for line in cart])
        sale = insert_sale(conn, bid, payload)
        if request_id:
            conn.execute("UPDATE alexa_request_receipts SET sale_id=?,invoice_no=?,total=? WHERE request_id=?", (sale.get("id"), sale.get("invoice_no", ""), float(sale.get("total") or 0), request_id))

    attrs["cart"] = []
    return alexa._speak(handler_input, f"Bill ban gaya. Total {alexa._money(sale.get('total'))} rupaye. Bill number {sale.get('invoice_no', '')}.", end=True)


class _ManualTestAwareWebserviceHandler:
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


alexa.LaunchRequestHandler.handle = _launch_shop_sathi
alexa.SelectCustomerIntentHandler.handle = _select_customer_clean
alexa._find_item = _safe_find_item
alexa.AddItemIntentHandler.handle = _queue_item_and_ask_quantity
alexa.CheckRateIntentHandler.handle = _check_rate_with_customer
alexa.CompleteBillIntentHandler.handle = _complete_bill_once
alexa.sb.add_request_handler(QuantityIntentHandler())

_strict_handler = WebserviceSkillHandler(skill=alexa.sb.create(), verify_signature=True, verify_timestamp=True)
alexa.webservice_handler = _ManualTestAwareWebserviceHandler(_strict_handler)
