from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Literal

from fastapi import Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.app import DB_PATH, STATIC_DIR, app, hash_password, now_iso, today_iso


DEFAULT_SETTINGS: dict[str, Any] = {
    "general": {
        "language": "English",
        "currency": "INR",
        "decimal_places": 2,
        "date_format": "dd/MM/yyyy",
        "warn_unsaved": True,
        "theme": "Modern",
        "passcode_lock": False,
        "multifirm": False,
        "godown_management": True,
    },
    "transaction": {
        "invoice_header": True,
        "cash_sale_default": False,
        "party_details": True,
        "transaction_time": True,
        "print_time": False,
        "inclusive_tax": True,
        "display_purchase_price": False,
        "last_sale_prices": True,
        "free_quantity": True,
        "barcode_scanning": True,
        "item_discount": True,
        "round_off": True,
        "round_nearest": 1,
        "link_payments": True,
        "payment_terms": True,
        "terms_conditions": True,
        "profit_while_sale": True,
        "reverse_charge": False,
        "state_of_supply": True,
        "eway_bill": False,
    },
    "print": {
        "mode": "regular",
        "regular_size": "A4",
        "thermal_size": "80mm",
        "orientation": "portrait",
        "text_size": "small",
        "company_name": True,
        "company_logo": False,
        "address": True,
        "email": False,
        "phone": True,
        "gstin": True,
        "repeat_header": True,
        "total_quantity": True,
        "decimals": True,
        "received_amount": True,
        "balance_amount": True,
        "party_balance": True,
        "tax_details": True,
        "amount_grouping": True,
        "amount_words": True,
        "terms_conditions": True,
        "received_by": False,
        "delivered_by": False,
        "signature": False,
        "payment_mode": True,
        "page_numbers": False,
    },
    "tax": {
        "gst": True,
        "hsn_sac": True,
        "cess": False,
        "reverse_charge": False,
        "state_of_supply": True,
        "eway_bill": False,
        "composite_scheme": False,
        "tcs": False,
        "tds": False,
    },
    "party": {
        "gstin": True,
        "grouping": True,
        "additional_fields": True,
        "shipping_address": False,
    },
    "item": {
        "enabled": True,
        "item_type": "Products and Services",
        "barcode_scanning": True,
        "scanner_type": "camera",
        "stock_maintenance": True,
        "manufacturing": False,
        "units": True,
        "default_unit": False,
        "category": True,
        "party_wise_rate": False,
        "wholesale_price": False,
        "quantity_decimals": 3,
        "item_tax": True,
        "tax_on_mrp": False,
        "item_discount": True,
        "update_sale_price": False,
        "description": False,
        "hsn_sac": True,
        "cess": False,
    },
    "messaging": {
        "send_to_party": True,
        "copy_to_self": False,
        "transaction_update": True,
        "show_balance": True,
        "show_web_invoice": True,
        "auto_share": False,
        "sale": True,
        "purchase": False,
        "sale_return": True,
        "purchase_return": False,
        "estimate": True,
        "proforma": False,
        "payment_in": True,
        "payment_out": False,
        "sale_order": False,
        "purchase_order": False,
        "delivery_challan": False,
        "cancelled_invoice": False,
        "template": "Namaste {party}, invoice {invoice} amount {amount}. Balance {balance}.",
    },
}


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(base))
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def ext_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Login required")
    token = authorization.split(" ", 1)[1].strip()
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT u.id,u.business_id,u.username,u.role,s.expires_at
            FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token=?
            """,
            (token,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid session")
    try:
        if datetime.fromisoformat(row["expires_at"]) < datetime.now():
            raise HTTPException(status_code=401, detail="Session expired")
    except ValueError:
        pass
    return dict(row)


def require_owner(user: dict[str, Any]) -> None:
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")


class SettingsPayload(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


class ManagedUserIn(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=4, max_length=128)
    role: Literal["manager", "cashier", "viewer"] = "cashier"


class ReminderIn(BaseModel):
    reminder_type: Literal["payment", "service"] = "payment"
    title: str = Field(min_length=1, max_length=160)
    party_id: int | None = None
    due_date: str = Field(default_factory=today_iso)
    message: str = ""
    enabled: bool = True


@app.on_event("startup")
def init_settings_extension() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                business_id INTEGER PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
                settings_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                reminder_type TEXT NOT NULL,
                title TEXT NOT NULL,
                party_id INTEGER REFERENCES parties(id) ON DELETE SET NULL,
                due_date TEXT NOT NULL,
                message TEXT DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reminders_business_due
            ON reminders(business_id,due_date);
            """
        )
        conn.commit()
    finally:
        conn.close()


@app.get("/api/settings/advanced")
def get_advanced_settings(user: dict[str, Any] = __import__("fastapi").Depends(ext_user)) -> dict[str, Any]:
    conn = connect()
    try:
        row = conn.execute("SELECT settings_json,updated_at FROM app_settings WHERE business_id=?", (user["business_id"],)).fetchone()
    finally:
        conn.close()
    saved: dict[str, Any] = {}
    if row:
        try:
            saved = json.loads(row["settings_json"] or "{}")
        except json.JSONDecodeError:
            saved = {}
    return {"settings": deep_merge(DEFAULT_SETTINGS, saved), "updated_at": row["updated_at"] if row else None}


@app.put("/api/settings/advanced")
def save_advanced_settings(payload: SettingsPayload, user: dict[str, Any] = __import__("fastapi").Depends(ext_user)) -> dict[str, Any]:
    merged = deep_merge(DEFAULT_SETTINGS, payload.settings)
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO app_settings(business_id,settings_json,updated_at)
            VALUES(?,?,?)
            ON CONFLICT(business_id) DO UPDATE SET settings_json=excluded.settings_json,updated_at=excluded.updated_at
            """,
            (user["business_id"], json.dumps(merged, ensure_ascii=False), now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "settings": merged}


@app.get("/api/settings/users")
def list_managed_users(user: dict[str, Any] = __import__("fastapi").Depends(ext_user)) -> list[dict[str, Any]]:
    require_owner(user)
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT id,username,role,created_at FROM users WHERE business_id=? ORDER BY id",
            (user["business_id"],),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.post("/api/settings/users")
def create_managed_user(payload: ManagedUserIn, user: dict[str, Any] = __import__("fastapi").Depends(ext_user)) -> dict[str, Any]:
    require_owner(user)
    conn = connect()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO users(business_id,username,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                (user["business_id"], payload.username.strip(), hash_password(payload.password), payload.role, now_iso()),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Username already exists") from exc
        return {"id": int(cur.lastrowid), "username": payload.username.strip(), "role": payload.role}
    finally:
        conn.close()


@app.delete("/api/settings/users/{managed_user_id}")
def delete_managed_user(managed_user_id: int, user: dict[str, Any] = __import__("fastapi").Depends(ext_user)) -> dict[str, Any]:
    require_owner(user)
    if managed_user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Current owner cannot be deleted")
    conn = connect()
    try:
        row = conn.execute("SELECT role FROM users WHERE id=? AND business_id=?", (managed_user_id, user["business_id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        if row["role"] == "owner":
            raise HTTPException(status_code=400, detail="Owner cannot be deleted")
        conn.execute("DELETE FROM users WHERE id=? AND business_id=?", (managed_user_id, user["business_id"]))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/api/settings/reminders")
def list_reminders(user: dict[str, Any] = __import__("fastapi").Depends(ext_user)) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT r.*,p.name party_name
            FROM reminders r LEFT JOIN parties p ON p.id=r.party_id
            WHERE r.business_id=? ORDER BY r.due_date,id DESC
            """,
            (user["business_id"],),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.post("/api/settings/reminders")
def create_reminder(payload: ReminderIn, user: dict[str, Any] = __import__("fastapi").Depends(ext_user)) -> dict[str, Any]:
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO reminders(business_id,reminder_type,title,party_id,due_date,message,enabled,created_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (user["business_id"], payload.reminder_type, payload.title.strip(), payload.party_id, payload.due_date, payload.message, 1 if payload.enabled else 0, now_iso()),
        )
        conn.commit()
        return {"id": int(cur.lastrowid), "ok": True}
    finally:
        conn.close()


@app.delete("/api/settings/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, user: dict[str, Any] = __import__("fastapi").Depends(ext_user)) -> dict[str, Any]:
    conn = connect()
    try:
        cur = conn.execute("DELETE FROM reminders WHERE id=? AND business_id=?", (reminder_id, user["business_id"]))
        conn.commit()
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Reminder not found")
        return {"ok": True}
    finally:
        conn.close()


@app.middleware("http")
async def inject_advanced_settings_assets(request, call_next):
    if request.method == "GET" and request.url.path == "/":
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace("</head>", '<link rel="stylesheet" href="/settings-v2.css?v=042" /></head>')
        html = html.replace("</body>", '<script src="/settings-v2.js?v=042"></script></body>')
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})
    return await call_next(request)


# The catch-all SPA route is registered by backend.app before this extension.
# Move extension API routes before it so GET requests do not get swallowed by /{path:path}.
extension_paths = {
    "/api/settings/advanced",
    "/api/settings/users",
    "/api/settings/users/{managed_user_id}",
    "/api/settings/reminders",
    "/api/settings/reminders/{reminder_id}",
}
extension_routes = [route for route in app.router.routes if getattr(route, "path", None) in extension_paths]
for route in extension_routes:
    app.router.routes.remove(route)
fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[fallback_index:fallback_index] = extension_routes
