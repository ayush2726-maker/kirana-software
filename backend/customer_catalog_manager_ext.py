from __future__ import annotations

import json
from typing import Any

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app import app, current_user, db, now_iso, split_item_name_size
from backend.customer_catalog_dedupe_ext import (
    catalog_identity,
    deduped_customer_catalog,
    normalized_text,
    normalized_unit,
    tidy_text,
)
import backend.order_portal_ext as order_portal


def catalog_key_from_identity(identity: tuple[str, str, str]) -> str:
    return json.dumps(identity, ensure_ascii=False, separators=(",", ":"))


def catalog_key_for_item(item: dict[str, Any]) -> str:
    return catalog_key_from_identity(catalog_identity(item))


def all_catalog_groups(conn: Any, business_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id,name,size,unit,category,gst_rate,sale_price,mrp,stock
        FROM items
        WHERE business_id=? AND COALESCE(archived_at,'')=''
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
        candidate = {
            "catalog_key": key,
            "item_id": int(item["id"]),
            "member_ids": [int(item["id"])],
            "name": display_name or tidy_text(item["name"]),
            "size": display_size,
            "unit": tidy_text(item.get("unit", "")),
            "category": tidy_text(item.get("category", "")),
            "sale_price": round(float(item.get("sale_price") or 0), 2),
            "mrp": round(float(item.get("mrp") or 0), 2),
            "member_count": 1,
        }
        current = groups.get(key)
        if current is None:
            groups[key] = candidate
            continue

        member_ids = list(current["member_ids"])
        member_ids.append(int(item["id"]))
        current_score = (
            1 if float(current.get("sale_price") or 0) > 0 else 0,
            int(current.get("item_id") or 0),
        )
        candidate_score = (
            1 if float(candidate.get("sale_price") or 0) > 0 else 0,
            int(candidate.get("item_id") or 0),
        )
        if candidate_score > current_score:
            candidate["member_ids"] = member_ids
            candidate["member_count"] = len(member_ids)
            groups[key] = candidate
        else:
            current["member_ids"] = member_ids
            current["member_count"] = len(member_ids)

    result = list(groups.values())
    result.sort(
        key=lambda row: (
            normalized_text(row["name"]),
            normalized_text(row.get("size", "")),
            normalized_unit(row.get("unit", "")),
        )
    )
    return result


def ensure_customer_catalog_manager_schema() -> None:
    order_portal.ensure_order_schema()
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customer_catalog_settings (
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                catalog_key TEXT NOT NULL,
                is_visible INTEGER NOT NULL DEFAULT 1,
                default_rate REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (business_id, catalog_key)
            );
            CREATE INDEX IF NOT EXISTS idx_customer_catalog_settings_business
            ON customer_catalog_settings(business_id, catalog_key);
            """
        )

        # Migrate an older allow-list table once, if it was used before this safe manager.
        old_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='customer_catalog_visibility'"
        ).fetchone()
        new_count = conn.execute("SELECT COUNT(*) AS count FROM customer_catalog_settings").fetchone()["count"]
        if old_table and int(new_count or 0) == 0:
            old_rows = conn.execute(
                "SELECT business_id,catalog_key FROM customer_catalog_visibility"
            ).fetchall()
            visible_by_business: dict[int, set[str]] = {}
            for row in old_rows:
                visible_by_business.setdefault(int(row["business_id"]), set()).add(str(row["catalog_key"]))
            for business_id, visible_keys in visible_by_business.items():
                for group in all_catalog_groups(conn, business_id):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO customer_catalog_settings(
                            business_id,catalog_key,is_visible,default_rate,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?)
                        """,
                        (
                            business_id,
                            group["catalog_key"],
                            1 if group["catalog_key"] in visible_keys else 0,
                            None,
                            now_iso(),
                            now_iso(),
                        ),
                    )


@app.on_event("startup")
def startup_customer_catalog_manager() -> None:
    ensure_customer_catalog_manager_schema()


class CatalogManagerLineIn(BaseModel):
    catalog_key: str = Field(min_length=2, max_length=1000)
    item_id: int
    is_visible: bool = True
    default_rate: float | None = Field(default=None, ge=0)
    customer_rate: float | None = Field(default=None, ge=0)


class CatalogManagerSaveIn(BaseModel):
    party_id: int | None = None
    items: list[CatalogManagerLineIn] = Field(min_items=1, max_items=3000)


def setting_rows(conn: Any, business_id: int) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT catalog_key,is_visible,default_rate,updated_at
        FROM customer_catalog_settings
        WHERE business_id=?
        """,
        (business_id,),
    ).fetchall()
    return {str(row["catalog_key"]): dict(row) for row in rows}


def specific_rates_for_groups(
    conn: Any,
    business_id: int,
    party_id: int,
    groups: list[dict[str, Any]],
) -> dict[str, float]:
    item_to_key: dict[int, str] = {}
    all_item_ids: list[int] = []
    for group in groups:
        for item_id in group["member_ids"]:
            item_to_key[int(item_id)] = group["catalog_key"]
            all_item_ids.append(int(item_id))
    if not all_item_ids:
        return {}
    placeholders = ",".join("?" for _ in all_item_ids)
    rows = conn.execute(
        f"""
        SELECT item_id,rate,updated_at,id
        FROM customer_prices
        WHERE business_id=? AND party_id=? AND item_id IN ({placeholders})
        ORDER BY updated_at DESC,id DESC
        """,
        (business_id, party_id, *all_item_ids),
    ).fetchall()
    output: dict[str, float] = {}
    for row in rows:
        key = item_to_key.get(int(row["item_id"]))
        if key and key not in output:
            output[key] = round(float(row["rate"] or 0), 2)
    return output


@app.get("/api/customer-catalog-manager")
def owner_customer_catalog_manager(
    party_id: int | None = Query(default=None),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ensure_customer_catalog_manager_schema()
    business_id = int(user["business_id"])
    with db() as conn:
        if party_id is not None:
            party = conn.execute(
                """
                SELECT id,name FROM parties
                WHERE id=? AND business_id=? AND type IN ('customer','both')
                """,
                (party_id, business_id),
            ).fetchone()
            if not party:
                raise HTTPException(status_code=404, detail="Customer not found")
        groups = all_catalog_groups(conn, business_id)
        settings = setting_rows(conn, business_id)
        specific = specific_rates_for_groups(conn, business_id, int(party_id), groups) if party_id else {}

    products: list[dict[str, Any]] = []
    for group in groups:
        row = dict(group)
        setting = settings.get(group["catalog_key"], {})
        row["is_visible"] = bool(setting.get("is_visible", 1))
        row["default_rate"] = (
            round(float(setting["default_rate"]), 2)
            if setting.get("default_rate") is not None
            else None
        )
        row["customer_rate"] = specific.get(group["catalog_key"])
        if row["customer_rate"] is not None:
            row["effective_rate"] = row["customer_rate"]
            row["rate_source"] = "customer"
        elif row["default_rate"] is not None:
            row["effective_rate"] = row["default_rate"]
            row["rate_source"] = "catalog"
        else:
            row["effective_rate"] = row["sale_price"]
            row["rate_source"] = "item"
        products.append(row)

    return {
        "total": len(products),
        "visible": sum(1 for product in products if product["is_visible"]),
        "party_id": party_id,
        "products": products,
    }


@app.post("/api/customer-catalog-manager")
def save_owner_customer_catalog_manager(
    payload: CatalogManagerSaveIn,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ensure_customer_catalog_manager_schema()
    business_id = int(user["business_id"])
    with db() as conn:
        groups = all_catalog_groups(conn, business_id)
        groups_by_key = {group["catalog_key"]: group for group in groups}
        if payload.party_id is not None:
            party = conn.execute(
                """
                SELECT id FROM parties
                WHERE id=? AND business_id=? AND type IN ('customer','both')
                """,
                (payload.party_id, business_id),
            ).fetchone()
            if not party:
                raise HTTPException(status_code=404, detail="Customer not found")

        saved = 0
        for line in payload.items:
            group = groups_by_key.get(line.catalog_key)
            if not group or int(line.item_id) not in {int(value) for value in group["member_ids"]}:
                raise HTTPException(status_code=404, detail="Customer catalog product not found")

            default_rate = round(float(line.default_rate), 2) if line.default_rate is not None else None
            if line.is_visible and default_rate is None:
                conn.execute(
                    "DELETE FROM customer_catalog_settings WHERE business_id=? AND catalog_key=?",
                    (business_id, line.catalog_key),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO customer_catalog_settings(
                        business_id,catalog_key,is_visible,default_rate,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(business_id,catalog_key)
                    DO UPDATE SET
                        is_visible=excluded.is_visible,
                        default_rate=excluded.default_rate,
                        updated_at=excluded.updated_at
                    """,
                    (
                        business_id,
                        line.catalog_key,
                        1 if line.is_visible else 0,
                        default_rate,
                        now_iso(),
                        now_iso(),
                    ),
                )

            if payload.party_id is not None:
                member_ids = [int(value) for value in group["member_ids"]]
                placeholders = ",".join("?" for _ in member_ids)
                conn.execute(
                    f"""
                    DELETE FROM customer_prices
                    WHERE business_id=? AND party_id=? AND item_id IN ({placeholders})
                    """,
                    (business_id, payload.party_id, *member_ids),
                )
                if line.customer_rate is not None:
                    customer_rate = round(float(line.customer_rate), 2)
                    for item_id in member_ids:
                        conn.execute(
                            """
                            INSERT INTO customer_prices(
                                business_id,party_id,item_id,rate,created_at,updated_at
                            ) VALUES(?,?,?,?,?,?)
                            ON CONFLICT(business_id,party_id,item_id)
                            DO UPDATE SET rate=excluded.rate,updated_at=excluded.updated_at
                            """,
                            (
                                business_id,
                                payload.party_id,
                                item_id,
                                customer_rate,
                                now_iso(),
                                now_iso(),
                            ),
                        )
            saved += 1

    return {"ok": True, "saved": saved, "party_id": payload.party_id}


def catalog_setting_for_item(
    conn: Any,
    business_id: int,
    item_id: int,
) -> tuple[str, dict[str, Any] | None]:
    item = conn.execute(
        """
        SELECT id,name,size,unit,category,gst_rate,sale_price,stock
        FROM items WHERE id=? AND business_id=?
        """,
        (item_id, business_id),
    ).fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    key = catalog_key_for_item(dict(item))
    setting = conn.execute(
        """
        SELECT is_visible,default_rate
        FROM customer_catalog_settings
        WHERE business_id=? AND catalog_key=?
        """,
        (business_id, key),
    ).fetchone()
    return key, dict(setting) if setting else None


_original_recommended_rate = order_portal.recommended_rate
_original_create_order_record = order_portal.create_order_record


def managed_recommended_rate(
    conn: Any,
    business_id: int,
    party_id: int,
    item_id: int,
) -> dict[str, Any]:
    result = _original_recommended_rate(conn, business_id, party_id, item_id)
    _key, setting = catalog_setting_for_item(conn, business_id, item_id)
    if (
        result.get("rate_source") != "fixed"
        and setting
        and setting.get("default_rate") is not None
    ):
        result["rate"] = round(float(setting["default_rate"]), 2)
        result["rate_source"] = "catalog"
    return result


def ensure_customer_items_visible(business_id: int, payload: Any) -> None:
    item_ids = sorted({int(line.item_id) for line in payload.items})
    with db() as conn:
        for item_id in item_ids:
            _key, setting = catalog_setting_for_item(conn, business_id, item_id)
            if setting and not bool(setting.get("is_visible", 1)):
                item = conn.execute("SELECT name FROM items WHERE id=?", (item_id,)).fetchone()
                raise HTTPException(
                    status_code=403,
                    detail=f"{item['name'] if item else 'Product'} is hidden from the customer app",
                )


def managed_create_order_record(
    payload: Any,
    business_id: int,
    party_id: int,
    source: str,
    created_by_user_id: int | None = None,
    customer_account_id: int | None = None,
) -> dict[str, Any]:
    if source == "customer":
        ensure_customer_items_visible(int(business_id), payload)
    return _original_create_order_record(
        payload,
        business_id,
        party_id,
        source,
        created_by_user_id=created_by_user_id,
        customer_account_id=customer_account_id,
    )


# Existing owner/customer order endpoints resolve these module globals at request time.
order_portal.recommended_rate = managed_recommended_rate
order_portal.create_order_record = managed_create_order_record


@app.middleware("http")
async def serve_managed_customer_catalog(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/api/customer/catalog":
        try:
            customer = order_portal.customer_user(request.headers.get("authorization"))
            ensure_customer_catalog_manager_schema()
            products = deduped_customer_catalog(customer)
            with db() as conn:
                settings = setting_rows(conn, int(customer["business_id"]))
            output: list[dict[str, Any]] = []
            for product in products:
                setting = settings.get(catalog_key_for_item(product))
                if setting and not bool(setting.get("is_visible", 1)):
                    continue
                row = dict(product)
                if (
                    row.get("rate_source") != "fixed"
                    and setting
                    and setting.get("default_rate") is not None
                ):
                    row["rate"] = round(float(setting["default_rate"]), 2)
                    row["rate_source"] = "catalog"
                output.append(row)
            return JSONResponse(
                output,
                headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
            )
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return await call_next(request)
