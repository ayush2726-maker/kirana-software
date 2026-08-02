from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from backend.app import STATIC_DIR, app, current_user, db
import backend.customer_catalog_manager_ext as manager
import backend.customer_catalog_owner_ui_ext as catalog_ui
import backend.order_portal_ext as order_portal


RECENT_RATE_DAYS = 15
CATALOG_JS = STATIC_DIR / "owner-customer-catalog.js"
CATALOG_VERSION = "108"
catalog_ui.CATALOG_VERSION = CATALOG_VERSION


def recent_date_range() -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=RECENT_RATE_DAYS - 1)
    return start.isoformat(), end.isoformat()


def recent_rates_for_groups(
    conn: Any,
    business_id: int,
    party_id: int,
    groups: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    item_to_key: dict[int, str] = {}
    item_ids: list[int] = []
    for group in groups:
        for item_id in group.get("member_ids", []):
            item_to_key[int(item_id)] = str(group["catalog_key"])
            item_ids.append(int(item_id))
    if not item_ids:
        return {}

    placeholders = ",".join("?" for _ in item_ids)
    start_date, end_date = recent_date_range()
    rows = conn.execute(
        f"""
        SELECT si.item_id,si.rate,s.invoice_date,s.invoice_no,
               s.id AS sale_id,si.id AS line_id
        FROM sale_items si
        JOIN sales s ON s.id=si.sale_id
        WHERE s.business_id=? AND s.party_id=?
          AND si.item_id IN ({placeholders})
          AND date(s.invoice_date)>=date(?)
          AND date(s.invoice_date)<=date(?)
        ORDER BY date(s.invoice_date) DESC,s.id DESC,si.id DESC
        """,
        (business_id, party_id, *item_ids, start_date, end_date),
    ).fetchall()

    output: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = item_to_key.get(int(row["item_id"]))
        if not key or key in output:
            continue
        output[key] = {
            "rate": round(float(row["rate"] or 0), 2),
            "invoice_date": str(row["invoice_date"] or ""),
            "invoice_no": str(row["invoice_no"] or ""),
            "sale_id": int(row["sale_id"]),
            "item_id": int(row["item_id"]),
        }
    return output


def group_for_item(conn: Any, business_id: int, item_id: int) -> dict[str, Any]:
    for group in manager.all_catalog_groups(conn, business_id):
        if int(item_id) in {int(value) for value in group.get("member_ids", [])}:
            return group
    raise ValueError("Customer catalog product not found")


def effective_group_rate(
    group: dict[str, Any],
    setting: dict[str, Any] | None,
    manual_rate: float | None,
    recent: dict[str, Any] | None,
) -> tuple[float, str]:
    if manual_rate is not None:
        return round(float(manual_rate), 2), "fixed"
    if recent is not None:
        return round(float(recent["rate"]), 2), "recent_15_days"
    if setting and setting.get("default_rate") is not None:
        return round(float(setting["default_rate"]), 2), "catalog"
    return round(float(group.get("sale_price") or 0), 2), "default"


def fixed_manager_payload(
    party_id: int | None,
    user: dict[str, Any],
) -> dict[str, Any]:
    base = manager.owner_customer_catalog_manager(party_id=party_id, user=user)
    products = list(base.get("products") or [])
    if party_id is None:
        base["products"] = products
        base["rate_rule"] = "Default customer rate, otherwise normal item rate"
        return base

    business_id = int(user["business_id"])
    with db() as conn:
        groups = manager.all_catalog_groups(conn, business_id)
        recent = recent_rates_for_groups(conn, business_id, int(party_id), groups)

    for product in products:
        recent_row = recent.get(str(product["catalog_key"]))
        product["recent_bill_rate"] = recent_row["rate"] if recent_row else None
        product["recent_bill_date"] = recent_row["invoice_date"] if recent_row else ""
        product["recent_bill_invoice"] = recent_row["invoice_no"] if recent_row else ""
        if product.get("customer_rate") is not None:
            product["effective_rate"] = round(float(product["customer_rate"]), 2)
            product["rate_source"] = "customer"
        elif recent_row is not None:
            product["effective_rate"] = recent_row["rate"]
            product["rate_source"] = "recent_15_days"
        elif product.get("default_rate") is not None:
            product["effective_rate"] = round(float(product["default_rate"]), 2)
            product["rate_source"] = "catalog"
        else:
            product["effective_rate"] = round(float(product.get("sale_price") or 0), 2)
            product["rate_source"] = "item"

    base["products"] = products
    base["rate_rule"] = (
        "Manual special rate, then latest bill rate from last 15 days, "
        "then default customer rate"
    )
    return base


@app.get("/api/customer-catalog-manager")
def owner_customer_catalog_manager_15day(
    party_id: int | None = Query(default=None),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return fixed_manager_payload(party_id, user)


@app.post("/api/customer-catalog-manager")
def save_owner_customer_catalog_manager_15day(
    payload: manager.CatalogManagerSaveIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return manager.save_owner_customer_catalog_manager(payload=payload, user=user)


def recommended_rate_15day(
    conn: Any,
    business_id: int,
    party_id: int,
    item_id: int,
) -> dict[str, Any]:
    result = manager._original_recommended_rate(conn, business_id, party_id, item_id)
    group = group_for_item(conn, business_id, item_id)
    setting = manager.setting_rows(conn, business_id).get(str(group["catalog_key"]))
    manual = manager.specific_rates_for_groups(
        conn, business_id, party_id, [group]
    ).get(str(group["catalog_key"]))
    recent = recent_rates_for_groups(
        conn, business_id, party_id, [group]
    ).get(str(group["catalog_key"]))
    rate, source = effective_group_rate(group, setting, manual, recent)
    result["rate"] = rate
    result["rate_source"] = source
    if recent:
        result["recent_bill_date"] = recent["invoice_date"]
        result["recent_bill_invoice"] = recent["invoice_no"]
    return result


# Order endpoints resolve this function from the order portal module at request time.
order_portal.recommended_rate = recommended_rate_15day


def managed_customer_catalog(customer: dict[str, Any]) -> list[dict[str, Any]]:
    manager.ensure_customer_catalog_manager_schema()
    business_id = int(customer["business_id"])
    party_id = int(customer["party_id"])
    with db() as conn:
        groups = manager.all_catalog_groups(conn, business_id)
        settings = manager.setting_rows(conn, business_id)
        manual = manager.specific_rates_for_groups(conn, business_id, party_id, groups)
        recent = recent_rates_for_groups(conn, business_id, party_id, groups)
        gst_rows = conn.execute(
            "SELECT id,gst_rate FROM items WHERE business_id=?",
            (business_id,),
        ).fetchall()
        gst_by_item = {
            int(row["id"]): round(float(row["gst_rate"] or 0), 2)
            for row in gst_rows
        }

    output: list[dict[str, Any]] = []
    for group in groups:
        key = str(group["catalog_key"])
        setting = settings.get(key)
        if setting and not bool(setting.get("is_visible", 1)):
            continue
        recent_row = recent.get(key)
        rate, source = effective_group_rate(
            group,
            setting,
            manual.get(key),
            recent_row,
        )
        row = {
            "id": int(group["item_id"]),
            "name": group["name"],
            "size": group.get("size", ""),
            "unit": group.get("unit", ""),
            "category": group.get("category", ""),
            "gst_rate": gst_by_item.get(int(group["item_id"]), 0),
            "rate": rate,
            "rate_source": source,
        }
        if recent_row:
            row["recent_bill_date"] = recent_row["invoice_date"]
            row["recent_bill_invoice"] = recent_row["invoice_no"]
        output.append(row)
    return output


def patched_catalog_script() -> str:
    script = CATALOG_JS.read_text(encoding="utf-8")
    script = script.replace(
        "    return data;\n  }\n\n  function notify",
        "    if (data == null) { throw new Error('Customer catalog server response is invalid. Please reopen the app.'); }\n"
        "    return data;\n  }\n\n  function notify",
        1,
    )
    script = script.replace(
        "    var rateLabel = product.rate_source === 'customer'\n"
        "      ? 'Customer-specific rate'\n"
        "      : product.rate_source === 'catalog'\n"
        "        ? 'Default customer rate'\n"
        "        : 'Normal item rate';",
        "    var rateLabel = product.rate_source === 'customer'\n"
        "      ? 'Manual special rate'\n"
        "      : product.rate_source === 'recent_15_days'\n"
        "        ? 'Latest bill rate (last 15 days)'\n"
        "        : product.rate_source === 'catalog'\n"
        "          ? 'Default customer rate'\n"
        "          : 'Normal item rate';",
        1,
    )
    script = script.replace(
        "      '<div class=\"catalog-product-foot\"><span>Normal ' + money(product.sale_price) + '</span><span>' + esc(rateLabel) + ': ' + money(product.effective_rate) + '</span></div>' +",
        "      '<div class=\"catalog-product-foot\"><span>Normal ' + money(product.sale_price) + '</span><span>' + esc(rateLabel) + ': ' + money(product.effective_rate) + (product.recent_bill_date ? ' · ' + esc(product.recent_bill_date) : '') + '</span></div>' +",
        1,
    )
    script = script.replace(
        "      state.products = data.products || [];",
        "      if (!data || !Array.isArray(data.products)) { throw new Error('Customer catalog products could not be loaded.'); }\n"
        "      state.products = data.products;",
        1,
    )
    script = script.replace(
        "mode.textContent = selected ? 'Special rates: ' + selected.name : 'Default rates for all customers';",
        "mode.textContent = selected ? '15-day bill rates: ' + selected.name : 'Default rates for all customers';",
        1,
    )
    return script


@app.middleware("http")
async def customer_catalog_15day_middleware(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/api/customer/catalog":
        try:
            customer = order_portal.customer_user(request.headers.get("authorization"))
            return JSONResponse(
                managed_customer_catalog(customer),
                headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", 500)
            detail = getattr(exc, "detail", str(exc) or "Customer catalog failed")
            return JSONResponse({"detail": detail}, status_code=status_code)

    if request.method == "GET" and path == "/owner-customer-catalog.js":
        return Response(
            patched_catalog_script(),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return await call_next(request)


# The base app already has an SPA catch-all. Move the manager API routes before it.
_selected_routes = []
for route in list(app.router.routes):
    if getattr(route, "path", None) != "/api/customer-catalog-manager":
        continue
    endpoint = getattr(route, "endpoint", None)
    app.router.routes.remove(route)
    if endpoint in {
        owner_customer_catalog_manager_15day,
        save_owner_customer_catalog_manager_15day,
    }:
        _selected_routes.append(route)

_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _selected_routes
