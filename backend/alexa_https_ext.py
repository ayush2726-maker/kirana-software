from __future__ import annotations

import json
import os
import re
from typing import Any

import ask_sdk_core.utils as ask_utils
from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_model import Response
from ask_sdk_webservice_support.webservice_handler import WebserviceSkillHandler
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from backend.app import TransactionIn, TxLineIn, app, db, insert_sale


# This is the current Alexa skill created for Shop Assistant. Railway can
# override it without a code change if a new skill is created later.
ALEXA_SKILL_ID = os.getenv(
    "ALEXA_SKILL_ID",
    "amzn1.ask.skill.398b05ec-135a-48e8-89a1-37e1e7fcdb9a",
).strip()
ALEXA_BUSINESS_ID = os.getenv("ALEXA_BUSINESS_ID", "").strip()
ALEXA_OWNER_USERNAME = os.getenv("ALEXA_OWNER_USERNAME", "").strip().lower()


def _business_id() -> int:
    """Resolve the one business Alexa is allowed to operate on.

    SaaS databases can contain several shops, so we never silently select an
    arbitrary shop when more than one exists. Configure ALEXA_BUSINESS_ID or
    ALEXA_OWNER_USERNAME in Railway for a multi-business database.
    """
    with db() as conn:
        if ALEXA_BUSINESS_ID:
            try:
                bid = int(ALEXA_BUSINESS_ID)
            except ValueError as exc:
                raise RuntimeError("ALEXA_BUSINESS_ID must be a number") from exc
            row = conn.execute("SELECT id FROM businesses WHERE id=?", (bid,)).fetchone()
            if not row:
                raise RuntimeError("Configured ALEXA_BUSINESS_ID was not found")
            return bid

        if ALEXA_OWNER_USERNAME:
            row = conn.execute(
                "SELECT business_id FROM users WHERE lower(username)=? ORDER BY id LIMIT 1",
                (ALEXA_OWNER_USERNAME,),
            ).fetchone()
            if not row:
                raise RuntimeError("Configured ALEXA_OWNER_USERNAME was not found")
            return int(row["business_id"])

        rows = conn.execute("SELECT id FROM businesses ORDER BY id LIMIT 2").fetchall()
        if len(rows) == 1:
            return int(rows[0]["id"])
        if not rows:
            raise RuntimeError("Shop Assistant setup is incomplete")
        raise RuntimeError(
            "Multiple shops exist. Set ALEXA_BUSINESS_ID or ALEXA_OWNER_USERNAME in Railway."
        )


def _slot(handler_input: HandlerInput, name: str) -> str:
    slots = handler_input.request_envelope.request.intent.slots or {}
    slot = slots.get(name)
    return str(slot.value or "").strip() if slot else ""


def _attrs(handler_input: HandlerInput) -> dict[str, Any]:
    return handler_input.attributes_manager.session_attributes


def _speak(handler_input: HandlerInput, text: str, reprompt: str | None = None, end: bool = False) -> Response:
    builder = handler_input.response_builder.speak(text)
    if reprompt:
        builder = builder.ask(reprompt)
    if end:
        builder.set_should_end_session(True)
    return builder.response


def _normalize_size(value: str) -> str:
    text = str(value or "").strip().lower()
    replacements = {
        "kilograms": "kg", "kilogram": "kg", "kilos": "kg", "kilo": "kg",
        "grams": "gm", "gram": "gm", "litres": "ltr", "litre": "ltr",
        "liters": "ltr", "liter": "ltr", "pieces": "pcs", "piece": "pcs",
        "packets": "packet", "pkt": "packet",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_item_phrase(phrase: str) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", str(phrase or "")).strip()
    match = re.match(
        r"^(?P<name>.+?)\s+(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>kg|kilo|kilogram|gm|g|gram|ml|ltr|litre|liter|packet|pkt|pcs|piece)?$",
        clean,
        flags=re.IGNORECASE,
    )
    if not match or not match.group("unit"):
        return clean, ""
    return match.group("name").strip(), _normalize_size(f"{match.group('num')} {match.group('unit')}")


def _find_customer(query: str) -> dict[str, Any] | None:
    bid = _business_id()
    q = str(query or "").strip()
    if not q:
        return None
    with db() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM parties
                WHERE business_id=? AND type IN ('customer','both') AND name LIKE ?
                ORDER BY name LIMIT 25
                """,
                (bid, f"%{q}%"),
            ).fetchall()
        ]
    if not rows:
        return None
    exact = [r for r in rows if str(r.get("name", "")).casefold() == q.casefold()]
    return exact[0] if exact else rows[0]


def _find_item(phrase: str) -> dict[str, Any] | None:
    bid = _business_id()
    name, requested_size = _split_item_phrase(phrase)
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
        sized = [r for r in candidates if _normalize_size(r.get("size", "")) == requested_size]
        if sized:
            candidates = sized
    exact = [r for r in candidates if str(r.get("name", "")).casefold() == name_cf]
    return exact[0] if exact else candidates[0]


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:.2f}".rstrip("0").rstrip(".")


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        _attrs(handler_input).setdefault("cart", [])
        return _speak(
            handler_input,
            "Shop Assistant ready hai. Customer ka naam bolo, ya aaj ki sale pucho.",
            "Customer ka naam bolo.",
        )


class SelectCustomerIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("SelectCustomerIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        query = _slot(handler_input, "customer")
        customer = _find_customer(query)
        if not customer:
            return _speak(handler_input, f"{query} customer nahi mila. Dusra naam bolo.", "Customer ka naam bolo.")
        attrs = _attrs(handler_input)
        attrs["customer"] = {"id": customer["id"], "name": customer["name"]}
        attrs["cart"] = []
        return _speak(handler_input, f"{customer['name']} select ho gaya. Item bolo.", "Item bolo.")


class AddItemIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("AddItemIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        phrase = _slot(handler_input, "item")
        qty_text = _slot(handler_input, "quantity")
        try:
            qty = float(qty_text) if qty_text else 1.0
        except ValueError:
            qty = 1.0
        qty = qty if qty > 0 else 1.0
        item = _find_item(phrase)
        if not item:
            return _speak(handler_input, f"{phrase} item nahi mila. Dobara item bolo.", "Item bolo.")
        cart = _attrs(handler_input).setdefault("cart", [])
        cart.append({
            "item_id": int(item["id"]),
            "item_name": str(item["name"]),
            "size": str(item.get("size") or ""),
            "qty": qty,
            "rate": float(item.get("sale_price") or 0),
            "gst_rate": float(item.get("gst_rate") or 0),
        })
        size = f" {item.get('size')}" if item.get("size") else ""
        return _speak(
            handler_input,
            f"{_money(qty)} {item['name']}{size}, rate {_money(item.get('sale_price'))} rupaye add ho gaya. Aur item?",
            "Aur item bolo, ya bill bana do.",
        )


class RemoveLastItemIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("RemoveLastItemIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        cart = _attrs(handler_input).setdefault("cart", [])
        if not cart:
            return _speak(handler_input, "Bill mein abhi koi item nahi hai.", "Item bolo.")
        removed = cart.pop()
        return _speak(handler_input, f"{removed['item_name']} hata diya. Aur item?", "Item bolo, ya bill bana do.")


class CompleteBillIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("CompleteBillIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        attrs = _attrs(handler_input)
        customer = attrs.get("customer")
        cart = attrs.get("cart") or []
        if not customer:
            return _speak(handler_input, "Pehle customer select karo.", "Customer ka naam bolo.")
        if not cart:
            return _speak(handler_input, "Bill mein item nahi hai. Pehle item add karo.", "Item bolo.")

        payload = TransactionIn(
            party_id=int(customer["id"]),
            paid=0,
            payment_mode="cash",
            notes="Created by Alexa HTTPS",
            items=[TxLineIn(**line) for line in cart],
        )
        with db() as conn:
            sale = insert_sale(conn, _business_id(), payload)
        attrs["cart"] = []
        return _speak(
            handler_input,
            f"Bill ban gaya. Total {_money(sale.get('total'))} rupaye. Bill number {sale.get('invoice_no', '')}.",
            end=True,
        )


class CheckRateIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("CheckRateIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        phrase = _slot(handler_input, "item")
        item = _find_item(phrase)
        if not item:
            return _speak(handler_input, f"{phrase} item nahi mila.", "Dusra item bolo.")
        size = f" {item.get('size')}" if item.get("size") else ""
        return _speak(handler_input, f"{item['name']}{size} ka rate {_money(item.get('sale_price'))} rupaye hai.")


class CustomerBalanceIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("CustomerBalanceIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        query = _slot(handler_input, "customer")
        customer = _find_customer(query)
        if not customer:
            return _speak(handler_input, f"{query} customer nahi mila.")
        return _speak(handler_input, f"{customer['name']} ka balance {_money(customer.get('balance'))} rupaye hai.")


class TodaySalesIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("TodaySalesIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        bid = _business_id()
        with db() as conn:
            total = conn.execute(
                "SELECT COALESCE(SUM(total),0) FROM sales WHERE business_id=? AND invoice_date=date('now','localtime')",
                (bid,),
            ).fetchone()[0]
        return _speak(handler_input, f"Aaj ki sale {_money(total)} rupaye hai.")


class CancelBillIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("CancelBillIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        attrs = _attrs(handler_input)
        attrs["cart"] = []
        attrs.pop("customer", None)
        return _speak(handler_input, "Current bill cancel kar diya.", end=True)


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        return _speak(
            handler_input,
            "Aap customer select kar sakte ho, item add kar sakte ho, rate ya balance puch sakte ho, aur bill bana sakte ho.",
            "Customer ka naam bolo.",
        )


class StopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input) or ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        return _speak(handler_input, "Theek hai.", end=True)


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input: HandlerInput, exception: Exception) -> bool:
        return True

    def handle(self, handler_input: HandlerInput, exception: Exception) -> Response:
        print(f"Alexa HTTPS error: {exception}")
        return _speak(handler_input, "Shop Assistant se connect karne mein problem aa rahi hai. Thodi der baad dobara try karo.")


sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(SelectCustomerIntentHandler())
sb.add_request_handler(AddItemIntentHandler())
sb.add_request_handler(RemoveLastItemIntentHandler())
sb.add_request_handler(CompleteBillIntentHandler())
sb.add_request_handler(CheckRateIntentHandler())
sb.add_request_handler(CustomerBalanceIntentHandler())
sb.add_request_handler(TodaySalesIntentHandler())
sb.add_request_handler(CancelBillIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(StopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

# Official ASK web-service support performs Alexa signature and timestamp
# verification before dispatching the request to the skill.
webservice_handler = WebserviceSkillHandler(
    skill=sb.create(),
    verify_signature=True,
    verify_timestamp=True,
)


def _application_id(payload: dict[str, Any]) -> str:
    session_id = (((payload.get("session") or {}).get("application") or {}).get("applicationId") or "")
    context_id = (((((payload.get("context") or {}).get("System") or {}).get("application") or {}).get("applicationId")) or "")
    return str(session_id or context_id)


@app.post("/api/alexa")
async def alexa_https_endpoint(request: Request):
    raw_bytes = await request.body()
    raw_body = raw_bytes.decode("utf-8")
    try:
        payload = json.loads(raw_body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Alexa JSON") from exc

    application_id = _application_id(payload)
    if not ALEXA_SKILL_ID or application_id != ALEXA_SKILL_ID:
        raise HTTPException(status_code=400, detail="Alexa Skill ID mismatch")

    try:
        serialized = webservice_handler.verify_request_and_dispatch(
            http_request_headers=dict(request.headers),
            http_request_body=raw_body,
        )
        return JSONResponse(content=json.loads(serialized), media_type="application/json")
    except Exception as exc:
        print(f"Alexa verification/dispatch failed: {exc}")
        raise HTTPException(status_code=400, detail="Alexa request verification failed") from exc


@app.get("/api/alexa/health")
def alexa_https_health() -> dict[str, Any]:
    try:
        bid = _business_id()
        configured = True
        error = ""
    except Exception as exc:
        bid = None
        configured = False
        error = str(exc)
    return {
        "ok": True,
        "mode": "https",
        "skill_id": ALEXA_SKILL_ID,
        "business_configured": configured,
        "business_id": bid,
        "configuration_error": error,
    }
