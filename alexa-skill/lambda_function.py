from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import ask_sdk_core.utils as ask_utils
from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_model import Response


API_URL = os.getenv("KIRANA_API_URL", "").rstrip("/")
USERNAME = os.getenv("KIRANA_USERNAME", "")
PASSWORD = os.getenv("KIRANA_PASSWORD", "")
STATIC_TOKEN = os.getenv("KIRANA_TOKEN", "")

_cached_token = STATIC_TOKEN


def _request(method: str, path: str, payload: dict[str, Any] | None = None, *, auth: bool = True, retry: bool = True) -> Any:
    global _cached_token
    if not API_URL:
        raise RuntimeError("KIRANA_API_URL is not configured")

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth:
        token = _get_token()
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(f"{API_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        if auth and exc.code == 401 and retry and not STATIC_TOKEN:
            _cached_token = ""
            return _request(method, path, payload, auth=auth, retry=False)
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Kirana API {exc.code}: {detail}") from exc


def _get_token() -> str:
    global _cached_token
    if _cached_token:
        return _cached_token
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Set KIRANA_TOKEN or KIRANA_USERNAME/KIRANA_PASSWORD")
    result = _request("POST", "/api/login", {"username": USERNAME, "password": PASSWORD}, auth=False)
    token = str((result or {}).get("token") or "")
    if not token:
        raise RuntimeError("Kirana login did not return a token")
    _cached_token = token
    return token


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    if params:
        path = f"{path}?{urllib.parse.urlencode(params)}"
    return _request("GET", path)


def _post(path: str, payload: dict[str, Any]) -> Any:
    return _request("POST", path, payload)


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


def _find_customer(query: str) -> dict[str, Any] | None:
    rows = _get("/api/parties", {"q": query, "party_type": "customer"}) or []
    if not rows:
        return None
    q = query.casefold()
    exact = [r for r in rows if str(r.get("name", "")).casefold() == q]
    return exact[0] if exact else rows[0]


def _normalize_size(value: str) -> str:
    text = value.strip().lower().replace("kilograms", "kg").replace("kilogram", "kg")
    text = text.replace("kilos", "kg").replace("kilo", "kg")
    text = text.replace("grams", "gm").replace("gram", "gm")
    text = text.replace("litres", "ltr").replace("litre", "ltr").replace("liters", "ltr").replace("liter", "ltr")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_item_phrase(phrase: str) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", phrase).strip()
    match = re.match(
        r"^(?P<name>.+?)\s+(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>kg|kilo|kilogram|gm|g|gram|ml|ltr|litre|liter|packet|pkt|pcs|piece)?$",
        clean,
        flags=re.IGNORECASE,
    )
    if not match or not match.group("unit"):
        return clean, ""
    return match.group("name").strip(), _normalize_size(f"{match.group('num')} {match.group('unit')}")


def _find_item(phrase: str) -> dict[str, Any] | None:
    name, requested_size = _split_item_phrase(phrase)
    rows = _get("/api/items", {"q": name, "limit": 100}) or []
    if not rows:
        return None
    name_cf = name.casefold()
    candidates = [r for r in rows if name_cf in str(r.get("name", "")).casefold()] or rows
    if requested_size:
        size_matches = [r for r in candidates if _normalize_size(str(r.get("size", ""))) == requested_size]
        if size_matches:
            candidates = size_matches
    exact = [r for r in candidates if str(r.get("name", "")).casefold() == name_cf]
    return exact[0] if exact else candidates[0]


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:.2f}".rstrip("0").rstrip(".")


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        _attrs(handler_input).setdefault("cart", [])
        return _speak(
            handler_input,
            "Kirana Software ready hai. Customer ka naam bolo, ya aaj ki sale pucho.",
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
        if qty <= 0:
            qty = 1.0

        item = _find_item(phrase)
        if not item:
            return _speak(handler_input, f"{phrase} item nahi mila. Dobara item bolo.", "Item bolo.")

        attrs = _attrs(handler_input)
        cart = attrs.setdefault("cart", [])
        cart.append(
            {
                "item_id": item["id"],
                "item_name": item["name"],
                "size": item.get("size", ""),
                "qty": qty,
                "rate": float(item.get("sale_price") or 0),
                "gst_rate": float(item.get("gst_rate") or 0),
            }
        )
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

        sale = _post(
            "/api/sales",
            {
                "party_id": customer["id"],
                "paid": 0,
                "payment_mode": "cash",
                "notes": "Created by Alexa",
                "items": cart,
            },
        )
        attrs["cart"] = []
        total = _money((sale or {}).get("total"))
        invoice = (sale or {}).get("invoice_no", "")
        return _speak(handler_input, f"Bill ban gaya. Total {total} rupaye. Bill number {invoice}.", end=True)


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
        data = _get("/api/dashboard") or {}
        return _speak(handler_input, f"Aaj ki sale {_money(data.get('sales_today'))} rupaye hai.")


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
        return _speak(handler_input, "Aap customer select kar sakte ho, item add kar sakte ho, rate ya balance puch sakte ho, aur bill bana sakte ho.", "Customer ka naam bolo.")


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
        print(f"Alexa error: {exception}")
        return _speak(handler_input, "Kirana Software se connect karne mein problem aa rahi hai. Thodi der baad dobara try karo.")


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

lambda_handler = sb.lambda_handler()
