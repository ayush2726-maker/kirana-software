from __future__ import annotations

import secrets
from typing import Any

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field

import backend.ai_counter_ext as counter
from backend.app import app, db, now_iso

VERSION = "184"


class KioskItemCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    size: str = Field(default="", max_length=80)
    unit: str = Field(default="kg", max_length=20)
    sale_price: float = Field(default=0, ge=0, le=10_000_000)
    purchase_price: float = Field(default=0, ge=0, le=10_000_000)
    barcode: str = Field(default="", max_length=120)
    gst_rate: float = Field(default=0, ge=0, le=100)


def _clean_unit(value: str) -> str:
    raw = str(value or "kg").strip().lower()
    aliases = {
        "kilogram": "kg", "kilo": "kg", "kgs": "kg",
        "gram": "g", "grams": "g", "gm": "g",
        "litre": "ltr", "liter": "ltr", "l": "ltr",
        "piece": "pcs", "pieces": "pcs", "pc": "pcs",
        "pkt": "packet", "pack": "packet",
    }
    return aliases.get(raw, raw or "kg")[:20]


def _public_item(row: Any) -> dict[str, Any]:
    d = dict(row)
    return {
        "id": int(d["id"]),
        "name": str(d.get("name") or ""),
        "size": str(d.get("size") or ""),
        "unit": str(d.get("unit") or ""),
        "sku": str(d.get("sku") or ""),
        "barcode": str(d.get("barcode") or ""),
        "sale_price": float(d.get("sale_price") or 0),
        "purchase_price": float(d.get("purchase_price") or 0),
        "gst_rate": float(d.get("gst_rate") or 0),
        "stock": float(d.get("stock") or 0),
    }


@app.get("/api/ai-counter/barcode-lookup")
def ai_counter_barcode_lookup(
    code: str = Query(min_length=1, max_length=120),
    bid: int = Depends(counter._kiosk_business),
):
    clean = str(code or "").strip()
    with db() as conn:
        row = conn.execute(
            "SELECT id,name,size,unit,sku,barcode,sale_price,purchase_price,gst_rate,stock "
            "FROM items WHERE business_id=? AND COALESCE(archived_at,'')='' "
            "AND (barcode=? OR sku=?) LIMIT 1",
            (bid, clean, clean),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Barcode se item nahi mila")
    return {"ok": True, "item": _public_item(row)}


@app.post("/api/ai-counter/items")
def ai_counter_create_item(
    payload: KioskItemCreateIn,
    bid: int = Depends(counter._kiosk_business),
):
    name = " ".join(str(payload.name or "").split()).strip()
    size = " ".join(str(payload.size or "").split()).strip()
    unit = _clean_unit(payload.unit)
    barcode = str(payload.barcode or "").strip()
    if not name:
        raise HTTPException(400, "Item name required")

    with db() as conn:
        if barcode:
            existing_barcode = conn.execute(
                "SELECT id FROM items WHERE business_id=? AND barcode=? AND COALESCE(archived_at,'')='' LIMIT 1",
                (bid, barcode),
            ).fetchone()
            if existing_barcode:
                raise HTTPException(409, "Ye barcode pehle se kisi item me laga hua hai")

        duplicate = conn.execute(
            "SELECT id,name,size,unit,sku,barcode,sale_price,purchase_price,gst_rate,stock "
            "FROM items WHERE business_id=? AND lower(trim(name))=lower(trim(?)) "
            "AND lower(trim(COALESCE(size,'')))=lower(trim(?)) AND COALESCE(archived_at,'')='' LIMIT 1",
            (bid, name, size),
        ).fetchone()
        if duplicate:
            return {"ok": True, "created": False, "item": _public_item(duplicate)}

        sku = "AID-" + secrets.token_hex(6).upper()
        if not barcode:
            barcode = "AIB" + secrets.token_hex(7).upper()
        stamp = now_iso()
        cur = conn.execute(
            "INSERT INTO items(business_id,name,sku,barcode,category,unit,size,hsn,gst_rate,purchase_price,sale_price,mrp,stock,min_stock,archived_at,archived_reason,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                bid, name, sku, barcode, "", unit, size, "", float(payload.gst_rate or 0),
                float(payload.purchase_price or 0), float(payload.sale_price or 0), float(payload.sale_price or 0),
                0, 0, "", "", stamp, stamp,
            ),
        )
        row = conn.execute(
            "SELECT id,name,size,unit,sku,barcode,sale_price,purchase_price,gst_rate,stock FROM items WHERE id=? AND business_id=?",
            (int(cur.lastrowid), bid),
        ).fetchone()
    return {"ok": True, "created": True, "item": _public_item(row)}


# Keep the barcode GET route ahead of the SPA catch-all.
for wanted in ("/api/ai-counter/barcode-lookup",):
    matches = [r for r in list(app.router.routes) if getattr(r, "path", None) == wanted]
    for r in matches:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass
    fallback = next((i for i, r in enumerate(app.router.routes) if getattr(r, "path", None) == "/{path:path}"), len(app.router.routes))
    app.router.routes[fallback:fallback] = matches
