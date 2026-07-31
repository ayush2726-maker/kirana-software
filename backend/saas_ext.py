from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.app import app, current_user, db, hash_password, now_iso
from backend.order_portal_ext import ensure_order_schema, normalize_phone


TRIAL_DAYS = max(1, int(os.getenv("SAAS_TRIAL_DAYS", "30")))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug[:42] or "shop"


def unique_slug(conn, name: str) -> str:
    base = slugify(name)
    slug = base
    sequence = 2
    while conn.execute("SELECT 1 FROM saas_businesses WHERE slug=?", (slug,)).fetchone():
        slug = f"{base[:36]}-{sequence}"
        sequence += 1
    return slug


def ensure_saas_schema() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS saas_businesses (
                business_id INTEGER PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
                slug TEXT NOT NULL UNIQUE,
                plan TEXT NOT NULL DEFAULT 'trial',
                subscription_status TEXT NOT NULL DEFAULT 'trial',
                trial_ends_at TEXT,
                paid_until TEXT,
                contact_phone TEXT DEFAULT '',
                max_staff INTEGER NOT NULL DEFAULT 3,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_saas_businesses_status
            ON saas_businesses(subscription_status, trial_ends_at);
            """
        )
        existing = conn.execute(
            """
            SELECT b.id,b.name,b.phone
            FROM businesses b
            LEFT JOIN saas_businesses sb ON sb.business_id=b.id
            WHERE sb.business_id IS NULL
            ORDER BY b.id
            """
        ).fetchall()
        for row in existing:
            conn.execute(
                """
                INSERT INTO saas_businesses(
                    business_id,slug,plan,subscription_status,trial_ends_at,paid_until,
                    contact_phone,max_staff,notes,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    unique_slug(conn, row["name"]),
                    "legacy",
                    "active",
                    None,
                    None,
                    normalize_phone(row["phone"]),
                    10,
                    "Existing business migrated as active",
                    now_iso(),
                    now_iso(),
                ),
            )


@app.on_event("startup")
def startup_saas() -> None:
    ensure_saas_schema()


class BusinessSignupIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    owner_name: str = Field(default="", max_length=120)
    phone: str = Field(min_length=10, max_length=20)
    gstin: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=500)
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=4, max_length=128)


class SaasCustomerLoginIn(BaseModel):
    phone: str
    pin: str
    shop_slug: str = ""


class PlatformBusinessUpdateIn(BaseModel):
    plan: str = Field(default="starter", max_length=30)
    subscription_status: Literal["trial", "active", "expired", "suspended"] = "active"
    paid_until: str | None = None
    max_staff: int = Field(default=3, ge=1, le=100)
    notes: str = Field(default="", max_length=500)


def subscription_payload(row: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now()
    trial_ends = datetime.fromisoformat(row["trial_ends_at"]) if row.get("trial_ends_at") else None
    paid_until = datetime.fromisoformat(row["paid_until"]) if row.get("paid_until") else None
    days_left = None
    if row.get("subscription_status") == "trial" and trial_ends:
        days_left = max(0, (trial_ends.date() - now.date()).days)
    elif row.get("subscription_status") == "active" and paid_until:
        days_left = max(0, (paid_until.date() - now.date()).days)
    result = dict(row)
    result["days_left"] = days_left
    result["customer_order_path"] = f"/customer?shop={row['slug']}"
    return result


@app.post("/api/saas/register-business")
def register_business(payload: BusinessSignupIn) -> dict[str, Any]:
    ensure_saas_schema()
    phone = normalize_phone(payload.phone)
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Valid 10 digit mobile number daalein")
    username = payload.username.strip().lower()
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise HTTPException(status_code=409, detail="Ye username pehle se use ho raha hai")
        slug = unique_slug(conn, payload.business_name)
        prefix_letters = "".join(word[0] for word in re.findall(r"[A-Za-z0-9]+", payload.business_name))[:6].upper()
        prefix = prefix_letters or "KS"
        business_cursor = conn.execute(
            """
            INSERT INTO businesses(name,owner_name,phone,gstin,address,invoice_prefix,created_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                payload.business_name.strip(),
                payload.owner_name.strip(),
                phone,
                payload.gstin.strip(),
                payload.address.strip(),
                prefix,
                now_iso(),
            ),
        )
        business_id = int(business_cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO accounts(business_id,name,account_type,balance,is_default,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (business_id, "Cash In Hand", "cash", 0, 1, now_iso(), now_iso()),
        )
        user_cursor = conn.execute(
            "INSERT INTO users(business_id,username,password_hash,role,created_at) VALUES(?,?,?,?,?)",
            (business_id, username, hash_password(payload.password), "owner", now_iso()),
        )
        user_id = int(user_cursor.lastrowid)
        token = secrets.token_urlsafe(40)
        expires_at = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
        conn.execute(
            "INSERT INTO sessions(token,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token, user_id, expires_at, now_iso()),
        )
        trial_ends = (datetime.now() + timedelta(days=TRIAL_DAYS)).replace(microsecond=0).isoformat()
        conn.execute(
            """
            INSERT INTO saas_businesses(
                business_id,slug,plan,subscription_status,trial_ends_at,paid_until,
                contact_phone,max_staff,notes,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                business_id,
                slug,
                "trial",
                "trial",
                trial_ends,
                None,
                phone,
                3,
                "Self-service signup",
                now_iso(),
                now_iso(),
            ),
        )
    return {
        "token": token,
        "business_id": business_id,
        "business_name": payload.business_name.strip(),
        "slug": slug,
        "trial_days": TRIAL_DAYS,
        "customer_order_path": f"/customer?shop={slug}",
    }


@app.get("/api/saas/me")
def saas_me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    ensure_saas_schema()
    with db() as conn:
        row = conn.execute(
            """
            SELECT sb.*,b.name AS business_name,b.owner_name,b.phone,b.gstin,b.address
            FROM saas_businesses sb JOIN businesses b ON b.id=sb.business_id
            WHERE sb.business_id=?
            """,
            (user["business_id"],),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Business subscription not found")
    return subscription_payload(dict(row))


@app.get("/api/saas/business/{slug}")
def public_business(slug: str) -> dict[str, Any]:
    ensure_saas_schema()
    with db() as conn:
        row = conn.execute(
            """
            SELECT sb.slug,sb.subscription_status,b.name AS business_name,b.phone,b.address
            FROM saas_businesses sb JOIN businesses b ON b.id=sb.business_id
            WHERE sb.slug=?
            """,
            (slugify(slug),),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop link galat hai")
    return dict(row)


@app.post("/api/customer/login")
def saas_customer_login(payload: SaasCustomerLoginIn) -> dict[str, Any]:
    ensure_order_schema()
    ensure_saas_schema()
    phone = normalize_phone(payload.phone)
    with db() as conn:
        sql = """
            SELECT ca.*,p.name AS party_name,b.name AS business_name,sb.slug
            FROM customer_accounts ca
            JOIN parties p ON p.id=ca.party_id
            JOIN businesses b ON b.id=ca.business_id
            JOIN saas_businesses sb ON sb.business_id=ca.business_id
            WHERE ca.phone=? AND ca.is_active=1
        """
        args: list[Any] = [phone]
        if payload.shop_slug.strip():
            sql += " AND sb.slug=?"
            args.append(slugify(payload.shop_slug))
        rows = conn.execute(sql, args).fetchall()
        if not rows:
            raise HTTPException(status_code=401, detail="Mobile number ya PIN galat hai")
        if len(rows) > 1:
            raise HTTPException(status_code=409, detail="Apni dukaan ka sahi customer link use karein")
        row = rows[0]
        from backend.app import verify_password
        if not verify_password(payload.pin, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Mobile number ya PIN galat hai")
        token = secrets.token_urlsafe(40)
        expires_at = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
        conn.execute("DELETE FROM customer_sessions WHERE expires_at<=?", (now_iso(),))
        conn.execute(
            "INSERT INTO customer_sessions(token,customer_account_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token, row["id"], expires_at, now_iso()),
        )
    return {
        "token": token,
        "customer": {"party_id": row["party_id"], "party_name": row["party_name"], "phone": row["phone"]},
        "business_name": row["business_name"],
        "shop_slug": row["slug"],
    }


def require_platform_key(x_platform_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("SAAS_ADMIN_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="SAAS_ADMIN_KEY configured nahi hai")
    if not x_platform_key or not secrets.compare_digest(x_platform_key, expected):
        raise HTTPException(status_code=401, detail="Wrong platform admin key")


@app.get("/api/saas/platform/businesses")
def platform_businesses(_: None = Depends(require_platform_key)) -> list[dict[str, Any]]:
    ensure_saas_schema()
    with db() as conn:
        rows = conn.execute(
            """
            SELECT sb.*,b.name AS business_name,b.owner_name,b.phone,
                   (SELECT COUNT(*) FROM users u WHERE u.business_id=b.id) AS user_count,
                   (SELECT COUNT(*) FROM parties p WHERE p.business_id=b.id) AS party_count,
                   (SELECT COUNT(*) FROM sales s WHERE s.business_id=b.id) AS sale_count
            FROM saas_businesses sb JOIN businesses b ON b.id=sb.business_id
            ORDER BY sb.business_id DESC
            """
        ).fetchall()
    return [subscription_payload(dict(row)) for row in rows]


@app.put("/api/saas/platform/businesses/{business_id}")
def platform_update_business(
    business_id: int,
    payload: PlatformBusinessUpdateIn,
    _: None = Depends(require_platform_key),
) -> dict[str, Any]:
    ensure_saas_schema()
    with db() as conn:
        existing = conn.execute("SELECT * FROM saas_businesses WHERE business_id=?", (business_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Business not found")
        conn.execute(
            """
            UPDATE saas_businesses
            SET plan=?,subscription_status=?,paid_until=?,max_staff=?,notes=?,updated_at=?
            WHERE business_id=?
            """,
            (
                payload.plan.strip() or "starter",
                payload.subscription_status,
                payload.paid_until,
                payload.max_staff,
                payload.notes.strip(),
                now_iso(),
                business_id,
            ),
        )
        row = conn.execute(
            """
            SELECT sb.*,b.name AS business_name,b.owner_name,b.phone
            FROM saas_businesses sb JOIN businesses b ON b.id=sb.business_id
            WHERE sb.business_id=?
            """,
            (business_id,),
        ).fetchone()
    return subscription_payload(dict(row))


# Replace the original phone-only customer login route and keep SaaS routes
# ahead of backend.app's SPA fallback route.
_saas_paths = {
    "/api/saas/register-business",
    "/api/saas/me",
    "/api/saas/business/{slug}",
    "/api/customer/login",
    "/api/saas/platform/businesses",
    "/api/saas/platform/businesses/{business_id}",
}
_selected = []
for route in list(app.router.routes):
    path = getattr(route, "path", None)
    if path in _saas_paths:
        app.router.routes.remove(route)
        if path == "/api/customer/login":
            # Keep only the route defined in this module (the latest one).
            if getattr(route, "endpoint", None) is saas_customer_login:
                _selected.append(route)
        else:
            _selected.append(route)
_fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _selected
