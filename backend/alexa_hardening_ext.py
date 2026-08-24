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


def _name_key(value: Any) -> str:
    text = _norm(value)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b(?:souff|sauf|saunf)\b", "souf", text)
    text = re.sub(r"[^\w\s.-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _launch_billing_sathi(self, handler_input):
    attrs = alexa._attrs(handler_input)
    attrs["cart"] = []
    attrs.pop("customer", None)
    attrs.pop("pending_item", None)
    attrs.pop("pending_item_query", None)
    return alexa._speak(handler_input, "Billing Sathi ready hai. Customer ka naam bolo.", "Customer ka naam bolo.")


def _select_customer_clean(self, handler_input):
    query = alexa._slot(handler_input, "customer")
    customer = alexa._find_customer(query)
    if not customer:
        return alexa._speak(handler_input, f"{query} customer nahi mila. Dusra naam bolo.", "Customer ka naam bolo.")
    attrs = alexa._attrs(handler_input)
    attrs["customer"] = {"id": customer["id"], "name": customer["name"]}
    attrs["cart"] = []
    attrs.pop("pending_item", None)
    attrs.pop("pending_item_query", None)
    return alexa._speak(handler_input, f"{customer['name']} select ho gaya. Item bolo.", "Item bolo.")


def _candidate_rows(phrase: str) -> tuple[str, str, list[dict[str, Any]]]:
    bid = alexa._business_id()
    name, requested_size = alexa._split_item_phrase(phrase)
    query = _name_key(name)
    if not query:
        return "", "", []
    tokens = [t for t in query.split() if len(t) > 1]
    search_term = tokens[0] if tokens else str(name).strip()
    with db() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT * FROM items
            WHERE business_id=? AND COALESCE(archived_at,'')='' AND name LIKE ?
            ORDER BY name,size,id LIMIT 200
            """,
            (bid, f"%{search_term}%"),
        ).fetchall()]
    rows = [r for r in rows if query in _name_key(r.get("name")) or _name_key(r.get("name")) in query]
    if requested_size:
        rows = [r for r in rows if alexa._normalize_size(r.get("size", "")) == requested_size]
    if not re.match(r"^\d+\b", query):
        uncoded = [r for r in rows if not re.match(r"^\d+\b", _name_key(r.get("name")))]
        if uncoded:
            rows = uncoded
    return query, requested_size, rows


def _resolve_item(phrase: str) -> tuple[str, dict[str, Any] | None, list[str]]:
    query, requested_size, rows = _candidate_rows(phrase)
    if not query or not rows:
        return "missing", None, []
    exact_name = [r for r in rows if _name_key(r.get("name")) == query]
    pool = exact_name or rows
    families: dict[str, list[dict[str, Any]]] = {}
    family_labels: dict[str, str] = {}
    for row in pool:
        key = _name_key(row.get("name"))
        families.setdefault(key, []).append(row)
        family_labels.setdefault(key, str(row.get("name") or ""))
    if not exact_name and len(families) > 1:
        labels = [family_labels[k] for k in list(families)[:4]]
        return "ambiguous", None, labels
    if exact_name:
        family_key = query
        family_rows = families.get(family_key, exact_name)
    else:
        family_key = next(iter(families))
        family_rows = families[family_key]
    if not requested_size and len(family_rows) > 1:
        size_labels: list[str] = []
        seen_sizes: set[str] = set()
        for row in family_rows:
            size = str(row.get("size") or "").strip()
            size_key = alexa._normalize_size(size) if size else ""
            if size_key and size_key not in seen_sizes:
                seen_sizes.add(size_key)
                size_labels.append(size)
        if len(size_labels) > 1:
            base = family_labels.get(family_key, str(family_rows[0].get("name") or ""))
            return "ambiguous", None, [f"{base} {s}" for s in size_labels[:5]]
    def score(row: dict[str, Any]) -> tuple[int, int, int]:
        item_name = _name_key(row.get("name"))
        exact = 3 if item_name == query else 0
        starts = 2 if item_name.startswith(query + " ") else 0
        contains = 1 if query in item_name else 0
        priced = 1 if float(row.get("sale_price") or 0) > 0 else 0
        return (max(exact, starts, contains), priced, -int(row.get("id") or 0))
    best = max(family_rows, key=score)
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


def _set_pending_item(attrs: dict[str, Any], item: dict[str, Any]) -> None:
    attrs["pending_item"] = {
        "item_id": int(item["id"]),
        "item_name": str(item["name"]),
        "size": str(item.get("size") or ""),
        "gst_rate": float(item.get("gst_rate") or 0),
    }
    attrs.pop("pending_item_query", None)


def _queue_item_and_ask_quantity(self, handler_input):
    phrase = alexa._slot(handler_input, "item")
    attrs = alexa._attrs(handler_input)
    if not attrs.get("customer"):
        customer_match = alexa._find_customer(phrase) if phrase else None
        if customer_match:
            attrs["customer"] = {"id": customer_match["id"], "name": customer_match["name"]}
            attrs["cart"] = []
            attrs.pop("pending_item", None)
            attrs.pop("pending_item_query", None)
            return alexa._speak(handler_input, f"{customer_match['name']} select ho gaya. Item bolo.", "Item bolo.")
        return alexa._speak(handler_input, "Pehle customer select karo.", "Customer ka naam bolo.")
    previous_query = str(attrs.get("pending_item_query") or "").strip()
    combined_phrase = phrase
    if previous_query and phrase:
        p = _name_key(phrase)
        prev = _name_key(previous_query)
        if p != prev and not p.startswith(prev + " "):
            combined_phrase = f"{previous_query} {phrase}".strip()
    status, item, choices = _resolve_item(combined_phrase)
    if status == "ambiguous":
        attrs["pending_item_query"] = combined_phrase
        return alexa._speak(handler_input, f"{combined_phrase} ke multiple variant hain: {', '.join(choices)}. Sirf size ya exact naam bolo.", "Size ya exact item bolo.")
    if status != "ok" or not item:
        if combined_phrase != phrase:
            status, item, choices = _resolve_item(phrase)
        if status == "ambiguous":
            attrs["pending_item_query"] = phrase
            return alexa._speak(handler_input, f"{phrase} ke multiple variant hain: {', '.join(choices)}. Sirf size ya exact naam bolo.", "Size ya exact item bolo.")
        if status != "ok" or not item:
            attrs.pop("pending_item_query", None)
            return alexa._speak(handler_input, f"{phrase} item nahi mila. Naam dobara bolo.", "Item bolo.")
    _set_pending_item(attrs, item)
    size = f" {item.get('size')}" if item.get("size") else ""
    return alexa._speak(handler_input, f"{item['name']}{size}. Kitni quantity?", "Quantity bolo, jaise 1 kilo ya 200 gram.")


def _unit_label(unit: str) -> str:
    unit = _norm(unit)
    mapping = {
        "kg": "kilo", "kilo": "kilo", "kilogram": "kilo",
        "gm": "gram", "g": "gram", "gram": "gram", "grams": "gram",
        "packet": "packet", "pack": "packet", "pcs": "piece", "piece": "piece",
        "ltr": "litre", "litre": "litre", "liter": "litre", "ml": "millilitre",
    }
    return mapping.get(unit, unit)


def _billing_quantity(qty: float, unit: str) -> float:
    """Convert spoken quantity to the quantity expected by rate-per-base-unit billing.

    Grocery rates in this app are stored per kg / litre for loose goods. Therefore
    200 gram must bill as 0.2 kg, not as 200 kg. Packet/piece counts stay unchanged.
    """
    u = _norm(unit)
    if u in {"gm", "g", "gram", "grams"}:
        return qty / 1000.0
    if u in {"ml", "millilitre", "milliliter"}:
        return qty / 1000.0
    return qty


class QuantityIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input) -> bool:
        return ask_utils.is_intent_name("QuantityIntent")(handler_input)

    def handle(self, handler_input):
        attrs = alexa._attrs(handler_input)
        pending = attrs.get("pending_item")
        if not attrs.get("customer"):
            return alexa._speak(handler_input, "Pehle customer select karo.", "Customer ka naam bolo.")
        qty_text = alexa._slot(handler_input, "quantity")
        unit = alexa._slot(handler_input, "unit")
        pending_query = str(attrs.get("pending_item_query") or "").strip()
        if not pending and pending_query and qty_text:
            refinement = f"{qty_text} {unit}".strip()
            phrase = f"{pending_query} {refinement}".strip()
            status, item, choices = _resolve_item(phrase)
            if status == "ok" and item:
                _set_pending_item(attrs, item)
                size = f" {item.get('size')}" if item.get("size") else ""
                return alexa._speak(handler_input, f"{item['name']}{size} select ho gaya. Ab quantity bolo.", "Quantity bolo, jaise 1 kilo ya 200 gram.")
            if status == "ambiguous":
                attrs["pending_item_query"] = phrase
                return alexa._speak(handler_input, f"Abhi bhi multiple variant hain: {', '.join(choices)}. Aur exact size bolo.", "Exact size bolo.")
            return alexa._speak(handler_input, f"{refinement} wala variant nahi mila. Dusra size bolo.", "Size bolo.")
        if not pending:
            return alexa._speak(handler_input, "Pehle item bolo.", "Item bolo.")
        try:
            spoken_qty = float(qty_text)
        except (TypeError, ValueError):
            spoken_qty = 0
        if spoken_qty <= 0:
            return alexa._speak(handler_input, "Quantity samajh nahi aayi. Dobara bolo.", "Jaise 1 kilo ya 200 gram.")
        qty = _billing_quantity(spoken_qty, unit)
        if qty <= 0:
            return alexa._speak(handler_input, "Quantity samajh nahi aayi. Dobara bolo.", "Jaise 1 kilo ya 200 gram.")
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
        attrs.pop("pending_item_query", None)
        source_text = {"fixed": "customer rate", "recent_15_days": "recent bill rate", "catalog": "default customer rate", "last_nonzero_sale": "recent bill rate", "last_nonzero_variant_sale": "recent bill rate"}.get(source, "item rate")
        spoken_unit = f" {_unit_label(unit)}" if unit else ""
        return alexa._speak(handler_input, f"{alexa._money(spoken_qty)}{spoken_unit} {pending['item_name']}, rate {alexa._money(rate)} rupaye, {source_text}, add ho gaya. Agla item bolo, ya bill bana do.", "Agla item bolo, ya bill bana do.")


def _check_rate_with_customer(self, handler_input):
    phrase = alexa._slot(handler_input, "item")
    status, item, choices = _resolve_item(phrase)
    if status == "ambiguous":
        return alexa._speak(handler_input, f"{phrase} ke multiple variant hain: {', '.join(choices)}. Exact item bolo.", "Exact item bolo.")
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
    if attrs.get("pending_item_query"):
        return alexa._speak(handler_input, "Pehle current item ka exact variant select karo.", "Size ya exact item bolo.")
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
    attrs.pop("pending_item_query", None)
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


alexa.LaunchRequestHandler.handle = _launch_billing_sathi
alexa.SelectCustomerIntentHandler.handle = _select_customer_clean
alexa._find_item = _safe_find_item
alexa.AddItemIntentHandler.handle = _queue_item_and_ask_quantity
alexa.CheckRateIntentHandler.handle = _check_rate_with_customer
alexa.CompleteBillIntentHandler.handle = _complete_bill_once
alexa.sb.add_request_handler(QuantityIntentHandler())

_strict_handler = WebserviceSkillHandler(skill=alexa.sb.create(), verify_signature=True, verify_timestamp=True)
alexa.webservice_handler = _ManualTestAwareWebserviceHandler(_strict_handler)