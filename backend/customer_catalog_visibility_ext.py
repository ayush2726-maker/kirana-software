from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app import app, current_user, db, split_item_name_size
from backend.customer_catalog_dedupe_ext import (
    catalog_identity,
    deduped_customer_catalog,
    normalized_text,
    normalized_unit,
    tidy_text,
)
from backend.order_portal_ext import (
    OrderCreateIn,
    create_order_record,
    customer_user,
    ensure_order_schema,
)


def catalog_key_from_identity(identity: tuple[str, str, str]) -> str:
    return json.dumps(identity, ensure_ascii=False, separators=(",", ":"))


def catalog_key_for_item(item: dict[str, Any]) -> str:
    return catalog_key_from_identity(catalog_identity(item))


def ensure_catalog_visibility_schema() -> None:
    ensure_order_schema()
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customer_catalog_visibility (
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                catalog_key TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (business_id, catalog_key)
            );
            CREATE INDEX IF NOT EXISTS idx_customer_catalog_visibility_business
            ON customer_catalog_visibility(business_id, catalog_key);
            """
        )


@app.on_event("startup")
def startup_customer_catalog_visibility() -> None:
    ensure_catalog_visibility_schema()


class CatalogVisibilityIn(BaseModel):
    catalog_key: str = Field(min_length=2, max_length=1000)
    is_visible: bool


class CatalogVisibilityBulkIn(BaseModel):
    action: Literal["show_all", "hide_all"]


def all_catalog_groups(conn, business_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id,name,size,unit,category,gst_rate,sale_price,stock
        FROM items
        WHERE business_id=?
        ORDER BY name,size,id
        """,
        (business_id,),
    ).fetchall()

    groups: dict[str, dict[str, Any]] = {}
    for raw in rows:
        item = dict(raw)
        display_name, display_size = split_item_name_size(
            item["name"], item.get("size", ""), item.get("unit", "")
        )
        key = catalog_key_for_item(item)
        current = groups.get(key)
        candidate = {
            "catalog_key": key,
            "item_id": int(item["id"]),
            "name": display_name or tidy_text(item["name"]),
            "size": display_size,
            "unit": tidy_text(item.get("unit", "")),
            "category": tidy_text(item.get("category", "")),
            "sale_price": round(float(item.get("sale_price") or 0), 2),
            "member_count": 1,
        }
        if current is None:
            groups[key] = candidate
            continue
        current["member_count"] += 1
        current_score = (
            1 if float(current.get("sale_price") or 0) > 0 else 0,
            int(current.get("item_id") or 0),
        )
        candidate_score = (
            1 if float(candidate.get("sale_price") or 0) > 0 else 0,
            int(candidate.get("item_id") or 0),
        )
        if candidate_score > current_score:
            candidate["member_count"] = current["member_count"]
            groups[key] = candidate

    result = list(groups.values())
    result.sort(
        key=lambda row: (
            normalized_text(row["name"]),
            normalized_text(row.get("size", "")),
            normalized_unit(row.get("unit", "")),
        )
    )
    return result


@app.get("/api/customer-catalog/manage")
def owner_manage_customer_catalog(
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ensure_catalog_visibility_schema()
    with db() as conn:
        groups = all_catalog_groups(conn, int(user["business_id"]))
        visible_rows = conn.execute(
            "SELECT catalog_key FROM customer_catalog_visibility WHERE business_id=?",
            (user["business_id"],),
        ).fetchall()
    visible_keys = {str(row["catalog_key"]) for row in visible_rows}
    for group in groups:
        group["is_visible"] = group["catalog_key"] in visible_keys
    return {
        "total": len(groups),
        "visible": sum(1 for group in groups if group["is_visible"]),
        "products": groups,
    }


@app.put("/api/customer-catalog/visibility")
def owner_set_customer_catalog_visibility(
    payload: CatalogVisibilityIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ensure_catalog_visibility_schema()
    business_id = int(user["business_id"])
    with db() as conn:
        valid_keys = {group["catalog_key"] for group in all_catalog_groups(conn, business_id)}
        if payload.catalog_key not in valid_keys:
            raise HTTPException(status_code=404, detail="Product customer catalog mein nahi mila")
        if payload.is_visible:
            conn.execute(
                """
                INSERT INTO customer_catalog_visibility(business_id,catalog_key,created_at,updated_at)
                VALUES(?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                ON CONFLICT(business_id,catalog_key)
                DO UPDATE SET updated_at=CURRENT_TIMESTAMP
                """,
                (business_id, payload.catalog_key),
            )
        else:
            conn.execute(
                "DELETE FROM customer_catalog_visibility WHERE business_id=? AND catalog_key=?",
                (business_id, payload.catalog_key),
            )
    return {"ok": True, "catalog_key": payload.catalog_key, "is_visible": payload.is_visible}


@app.post("/api/customer-catalog/visibility/bulk")
def owner_bulk_customer_catalog_visibility(
    payload: CatalogVisibilityBulkIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ensure_catalog_visibility_schema()
    business_id = int(user["business_id"])
    with db() as conn:
        if payload.action == "hide_all":
            conn.execute(
                "DELETE FROM customer_catalog_visibility WHERE business_id=?",
                (business_id,),
            )
            return {"ok": True, "visible": 0}
        groups = all_catalog_groups(conn, business_id)
        for group in groups:
            conn.execute(
                """
                INSERT INTO customer_catalog_visibility(business_id,catalog_key,created_at,updated_at)
                VALUES(?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                ON CONFLICT(business_id,catalog_key)
                DO UPDATE SET updated_at=CURRENT_TIMESTAMP
                """,
                (business_id, group["catalog_key"]),
            )
    return {"ok": True, "visible": len(groups)}


@app.get("/api/customer/catalog")
def visible_customer_catalog(
    customer: dict[str, Any] = Depends(customer_user),
) -> list[dict[str, Any]]:
    ensure_catalog_visibility_schema()
    products = deduped_customer_catalog(customer)
    with db() as conn:
        rows = conn.execute(
            "SELECT catalog_key FROM customer_catalog_visibility WHERE business_id=?",
            (customer["business_id"],),
        ).fetchall()
    visible_keys = {str(row["catalog_key"]) for row in rows}
    return [
        product
        for product in products
        if catalog_key_for_item(product) in visible_keys
    ]


def ensure_customer_order_items_visible(
    business_id: int,
    payload: OrderCreateIn,
) -> None:
    ensure_catalog_visibility_schema()
    item_ids = sorted({int(line.item_id) for line in payload.items})
    placeholders = ",".join("?" for _ in item_ids)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT id,name,size,unit,category
            FROM items
            WHERE business_id=? AND id IN ({placeholders})
            """,
            (business_id, *item_ids),
        ).fetchall()
        items = {int(row["id"]): dict(row) for row in rows}
        visible_rows = conn.execute(
            "SELECT catalog_key FROM customer_catalog_visibility WHERE business_id=?",
            (business_id,),
        ).fetchall()
    visible_keys = {str(row["catalog_key"]) for row in visible_rows}
    for item_id in item_ids:
        item = items.get(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Product nahi mila")
        if catalog_key_for_item(item) not in visible_keys:
            raise HTTPException(
                status_code=403,
                detail=f"{item['name']} customer app ke liye allowed nahi hai",
            )


@app.post("/api/customer/orders")
def visible_customer_create_order(
    payload: OrderCreateIn,
    customer: dict[str, Any] = Depends(customer_user),
) -> dict[str, Any]:
    ensure_customer_order_items_visible(int(customer["business_id"]), payload)
    return create_order_record(
        payload,
        int(customer["business_id"]),
        int(customer["party_id"]),
        "customer",
        customer_account_id=int(customer["customer_account_id"]),
    )


# Replace the customer catalog route and only the customer POST order route.
_selected_routes = []
for route in list(app.router.routes):
    path = getattr(route, "path", None)
    methods = set(getattr(route, "methods", set()) or set())
    endpoint = getattr(route, "endpoint", None)
    if path in {
        "/api/customer-catalog/manage",
        "/api/customer-catalog/visibility",
        "/api/customer-catalog/visibility/bulk",
    }:
        app.router.routes.remove(route)
        _selected_routes.append(route)
    elif path == "/api/customer/catalog":
        app.router.routes.remove(route)
        if endpoint is visible_customer_catalog:
            _selected_routes.append(route)
    elif path == "/api/customer/orders" and "POST" in methods:
        app.router.routes.remove(route)
        if endpoint is visible_customer_create_order:
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
