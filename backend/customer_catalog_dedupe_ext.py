from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

from fastapi import Depends

from backend.app import app, db, split_item_name_size
from backend.order_portal_ext import customer_user, ensure_order_schema


UNIT_ALIASES = {
    "g": "gm", "gm": "gm", "gms": "gm", "gram": "gm", "grams": "gm",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml",
    "l": "ltr", "lt": "ltr", "ltr": "ltr", "litre": "ltr", "litres": "ltr", "liter": "ltr", "liters": "ltr",
    "pc": "pcs", "pcs": "pcs", "piece": "pcs", "pieces": "pcs",
    "pkt": "packet", "pkts": "packet", "packet": "packet", "packets": "packet",
}


def tidy_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"[\u200B-\u200D\u2060\uFEFF]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_text(value: Any) -> str:
    text = tidy_text(value).casefold()
    text = re.sub(r"\s*\(\s*", "(", text)
    text = re.sub(r"\s*\)\s*", ")", text)
    text = re.sub(r"[._,\-/]+$", "", text)
    return text.strip()


def normalized_unit(value: Any) -> str:
    unit = normalized_text(value).replace(".", "")
    return UNIT_ALIASES.get(unit, unit)


def catalog_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    display_name, display_size = split_item_name_size(item["name"], item.get("size", ""), item.get("unit", ""))
    return (
        normalized_text(display_name),
        normalized_text(display_size),
        normalized_unit(item.get("unit", "")),
    )


def sortable_time(value: Any) -> float:
    text = tidy_text(value)
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


def candidate_payload(
    item: dict[str, Any],
    fixed: dict[str, Any] | None,
    last_bill: dict[str, Any] | None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    display_name, display_size = split_item_name_size(item["name"], item.get("size", ""), item.get("unit", ""))
    if fixed:
        rate = round(float(fixed["rate"] or 0), 2)
        source = "fixed"
        score = (3, sortable_time(fixed.get("updated_at")), int(item["id"]))
    elif last_bill:
        rate = round(float(last_bill["rate"] or 0), 2)
        source = "last_bill"
        score = (
            2,
            sortable_time(last_bill.get("invoice_date")),
            int(last_bill.get("sale_id") or 0),
            int(last_bill.get("line_id") or 0),
        )
    else:
        rate = round(float(item.get("sale_price") or 0), 2)
        source = "default"
        score = (
            1,
            1 if rate > 0 else 0,
            1 if float(item.get("stock") or 0) > 0 else 0,
            float(item.get("stock") or 0),
            int(item["id"]),
        )

    # Stock is deliberately omitted: customers should never see internal stock.
    payload = {
        "id": int(item["id"]),
        "name": display_name or tidy_text(item["name"]),
        "size": display_size,
        "unit": tidy_text(item.get("unit", "")),
        "category": tidy_text(item.get("category", "")),
        "gst_rate": round(float(item.get("gst_rate") or 0), 2),
        "rate": rate,
        "rate_source": source,
    }
    return score, payload


@app.get("/api/customer/catalog")
def deduped_customer_catalog(customer: dict[str, Any] = Depends(customer_user)) -> list[dict[str, Any]]:
    ensure_order_schema()
    with db() as conn:
        item_rows = conn.execute(
            """
            SELECT id,name,size,unit,category,gst_rate,sale_price,stock
            FROM items
            WHERE business_id=?
            ORDER BY name,size,id
            """,
            (customer["business_id"],),
        ).fetchall()
        items = [dict(row) for row in item_rows]

        fixed_rows = conn.execute(
            """
            SELECT item_id,rate,updated_at
            FROM customer_prices
            WHERE business_id=? AND party_id=?
            """,
            (customer["business_id"], customer["party_id"]),
        ).fetchall()
        fixed_by_item = {int(row["item_id"]): dict(row) for row in fixed_rows}

        bill_rows = conn.execute(
            """
            SELECT si.item_id,si.rate,s.invoice_date,s.id AS sale_id,si.id AS line_id
            FROM sale_items si
            JOIN sales s ON s.id=si.sale_id
            WHERE s.business_id=? AND s.party_id=? AND si.item_id IS NOT NULL
            ORDER BY s.invoice_date DESC,s.id DESC,si.id DESC
            """,
            (customer["business_id"], customer["party_id"]),
        ).fetchall()
        last_bill_by_item: dict[int, dict[str, Any]] = {}
        for row in bill_rows:
            item_id = int(row["item_id"])
            if item_id not in last_bill_by_item:
                last_bill_by_item[item_id] = dict(row)

    grouped: dict[tuple[str, str, str], tuple[tuple[Any, ...], dict[str, Any]]] = {}
    for item in items:
        item_id = int(item["id"])
        candidate = candidate_payload(item, fixed_by_item.get(item_id), last_bill_by_item.get(item_id))
        key = catalog_identity(item)
        current = grouped.get(key)
        if current is None or candidate[0] > current[0]:
            grouped[key] = candidate

    products = [candidate[1] for candidate in grouped.values()]
    products.sort(
        key=lambda row: (
            normalized_text(row["name"]),
            normalized_text(row.get("size", "")),
            normalized_unit(row.get("unit", "")),
        )
    )
    return products


# Replace the original catalog route and keep this one ahead of the SPA fallback.
_catalog_routes = [
    route
    for route in list(app.router.routes)
    if getattr(route, "path", None) == "/api/customer/catalog"
]
for route in _catalog_routes:
    app.router.routes.remove(route)
_selected = [route for route in _catalog_routes if getattr(route, "endpoint", None) is deduped_customer_catalog]
_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _selected
