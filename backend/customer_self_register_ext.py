from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.app import app, current_user, db, hash_password, now_iso
from backend.order_portal_ext import CUSTOMER_PORTAL_HTML, ensure_order_schema, normalize_phone
from backend.saas_ext import ensure_saas_schema, slugify


OTP_MINUTES = 10
OTP_MAX_ATTEMPTS = 5


def ensure_customer_otp_schema() -> None:
    ensure_order_schema()
    ensure_saas_schema()
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customer_registration_otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
                phone TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                verified_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_customer_registration_otps_lookup
            ON customer_registration_otps(business_id,phone,status,id DESC);
            """
        )


@app.on_event("startup")
def startup_customer_otp() -> None:
    ensure_customer_otp_schema()


class CustomerOtpRequestIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    shop_slug: str = Field(min_length=1, max_length=60)


class CustomerOtpVerifyIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    shop_slug: str = Field(min_length=1, max_length=60)
    otp: str = Field(min_length=6, max_length=6)
    pin: str = Field(min_length=4, max_length=128)
    confirm_pin: str = Field(min_length=4, max_length=128)


def business_for_slug(conn, shop_slug: str):
    row = conn.execute(
        """
        SELECT sb.business_id,sb.slug,sb.subscription_status,b.name AS business_name
        FROM saas_businesses sb JOIN businesses b ON b.id=sb.business_id
        WHERE sb.slug=?
        """,
        (slugify(shop_slug),),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop link galat hai")
    if row["subscription_status"] == "suspended":
        raise HTTPException(status_code=403, detail="Is shop ka online order temporarily band hai")
    return row


def matching_customer_parties(conn, business_id: int, phone: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    rows = conn.execute(
        """
        SELECT id,business_id,name,phone,type
        FROM parties
        WHERE business_id=? AND type IN ('customer','both')
          AND TRIM(COALESCE(phone,''))<>''
        ORDER BY id
        """,
        (business_id,),
    ).fetchall()
    for row in rows:
        if normalize_phone(row["phone"]) == phone:
            matches.append(dict(row))
    return matches


def validate_customer_for_registration(conn, business_id: int, phone: str) -> dict[str, Any]:
    matches = matching_customer_parties(conn, business_id, phone)
    if not matches:
        raise HTTPException(
            status_code=404,
            detail="Ye mobile number customer database mein nahi mila. Dukaan se mobile number update karwayein.",
        )
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Is mobile number se ek se zyada customer mile. Dukaan se duplicate mobile number theek karwayein.",
        )
    party = matches[0]
    existing = conn.execute(
        "SELECT id,is_active FROM customer_accounts WHERE business_id=? AND party_id=?",
        (business_id, party["id"]),
    ).fetchone()
    if existing:
        if existing["is_active"]:
            raise HTTPException(
                status_code=409,
                detail="Account pehle se registered hai. Login karein ya dukaan se PIN reset karwayein.",
            )
        raise HTTPException(status_code=403, detail="Customer login blocked hai. Dukaan se contact karein.")
    return party


@app.post("/api/customer/register/request-otp")
def request_customer_registration_otp(payload: CustomerOtpRequestIn) -> dict[str, Any]:
    ensure_customer_otp_schema()
    phone = normalize_phone(payload.phone)
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Valid 10 digit mobile number daalein")
    with db() as conn:
        business = business_for_slug(conn, payload.shop_slug)
        party = validate_customer_for_registration(conn, business["business_id"], phone)
        now = datetime.now().replace(microsecond=0)
        recent = conn.execute(
            """
            SELECT * FROM customer_registration_otps
            WHERE business_id=? AND phone=? AND status='pending'
            ORDER BY id DESC LIMIT 1
            """,
            (business["business_id"], phone),
        ).fetchone()
        if recent:
            created = datetime.fromisoformat(recent["created_at"])
            expires = datetime.fromisoformat(recent["expires_at"])
            if expires > now and (now - created).total_seconds() < 60:
                return {
                    "request_id": recent["id"],
                    "customer_name": party["name"],
                    "masked_phone": f"******{phone[-4:]}",
                    "expires_in_minutes": OTP_MINUTES,
                    "message": "OTP request pehle se pending hai. Dukaan WhatsApp se OTP bhejegi.",
                }
            conn.execute(
                "UPDATE customer_registration_otps SET status='expired' WHERE id=?",
                (recent["id"],),
            )
        otp = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = (now + timedelta(minutes=OTP_MINUTES)).isoformat()
        cursor = conn.execute(
            """
            INSERT INTO customer_registration_otps(
                business_id,party_id,phone,otp_code,status,attempts,expires_at,created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                business["business_id"],
                party["id"],
                phone,
                otp,
                "pending",
                0,
                expires_at,
                now.isoformat(),
            ),
        )
    return {
        "request_id": int(cursor.lastrowid),
        "customer_name": party["name"],
        "masked_phone": f"******{phone[-4:]}",
        "expires_in_minutes": OTP_MINUTES,
        "message": "Request dukaan ko mil gayi. WhatsApp par OTP aane ke baad verify karein.",
    }


@app.post("/api/customer/register/verify-otp")
def verify_customer_registration_otp(payload: CustomerOtpVerifyIn) -> dict[str, Any]:
    ensure_customer_otp_schema()
    phone = normalize_phone(payload.phone)
    otp = str(payload.otp).strip()
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Valid mobile number daalein")
    if not otp.isdigit() or len(otp) != 6:
        raise HTTPException(status_code=400, detail="6 digit OTP daalein")
    if payload.pin != payload.confirm_pin:
        raise HTTPException(status_code=400, detail="PIN aur Confirm PIN match nahi kar rahe")
    with db() as conn:
        business = business_for_slug(conn, payload.shop_slug)
        party = validate_customer_for_registration(conn, business["business_id"], phone)
        row = conn.execute(
            """
            SELECT * FROM customer_registration_otps
            WHERE business_id=? AND party_id=? AND phone=? AND status='pending'
            ORDER BY id DESC LIMIT 1
            """,
            (business["business_id"], party["id"], phone),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="OTP request nahi mili. Naya OTP request karein.")
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now():
            conn.execute("UPDATE customer_registration_otps SET status='expired' WHERE id=?", (row["id"],))
            raise HTTPException(status_code=410, detail="OTP expire ho gaya. Naya OTP request karein.")
        if int(row["attempts"] or 0) >= OTP_MAX_ATTEMPTS:
            conn.execute("UPDATE customer_registration_otps SET status='cancelled' WHERE id=?", (row["id"],))
            raise HTTPException(status_code=429, detail="Bahut galat attempts hue. Naya OTP request karein.")
        if not secrets.compare_digest(str(row["otp_code"]), otp):
            conn.execute(
                "UPDATE customer_registration_otps SET attempts=attempts+1 WHERE id=?",
                (row["id"],),
            )
            remaining = OTP_MAX_ATTEMPTS - int(row["attempts"] or 0) - 1
            raise HTTPException(status_code=400, detail=f"OTP galat hai. {max(0, remaining)} attempts baaki.")
        cursor = conn.execute(
            """
            INSERT INTO customer_accounts(
                business_id,party_id,phone,password_hash,is_active,created_at,updated_at
            ) VALUES(?,?,?,?,1,?,?)
            """,
            (
                business["business_id"],
                party["id"],
                phone,
                hash_password(payload.pin),
                now_iso(),
                now_iso(),
            ),
        )
        account_id = int(cursor.lastrowid)
        token = secrets.token_urlsafe(40)
        expires_at = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
        conn.execute(
            "INSERT INTO customer_sessions(token,customer_account_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token, account_id, expires_at, now_iso()),
        )
        conn.execute(
            "UPDATE customer_registration_otps SET status='used',verified_at=? WHERE id=?",
            (now_iso(), row["id"]),
        )
    return {
        "token": token,
        "customer": {"party_id": party["id"], "party_name": party["name"], "phone": phone},
        "business_name": business["business_name"],
        "registered": True,
    }


@app.get("/api/customer/otp-requests")
def owner_otp_requests(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    ensure_customer_otp_schema()
    now = datetime.now().replace(microsecond=0)
    with db() as conn:
        conn.execute(
            """
            UPDATE customer_registration_otps
            SET status='expired'
            WHERE business_id=? AND status='pending' AND expires_at<=?
            """,
            (user["business_id"], now.isoformat()),
        )
        rows = conn.execute(
            """
            SELECT o.id,o.party_id,o.phone,o.otp_code,o.status,o.attempts,o.expires_at,o.created_at,
                   p.name AS party_name,b.name AS business_name
            FROM customer_registration_otps o
            JOIN parties p ON p.id=o.party_id
            JOIN businesses b ON b.id=o.business_id
            WHERE o.business_id=? AND o.status='pending'
            ORDER BY o.id DESC LIMIT 100
            """,
            (user["business_id"],),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        message = (
            f"{row['business_name']} registration OTP: {row['otp_code']}. "
            f"Ye OTP {OTP_MINUTES} minute ke liye valid hai. Kisi ke saath share na karein."
        )
        item = dict(row)
        item["whatsapp_url"] = f"https://wa.me/91{row['phone']}?text={quote(message)}"
        item["message"] = message
        result.append(item)
    return result


@app.delete("/api/customer/otp-requests/{request_id}")
def cancel_owner_otp_request(
    request_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, bool]:
    ensure_customer_otp_schema()
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM customer_registration_otps WHERE id=? AND business_id=?",
            (request_id, user["business_id"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="OTP request not found")
        conn.execute(
            "UPDATE customer_registration_otps SET status='cancelled' WHERE id=?",
            (request_id,),
        )
    return {"ok": True}


REGISTER_SWITCH = """
<div class="customer-auth-switch" role="tablist" aria-label="Customer login or registration">
  <button id="customer-show-login" class="active" type="button">Login</button>
  <button id="customer-show-register" type="button">Register</button>
</div>
"""

REGISTER_FORM = """
<div id="customer-register-box" class="hidden">
  <form id="customer-otp-request-form">
    <label>Database wala mobile number<input name="phone" inputmode="tel" required maxlength="15" /></label>
    <button type="submit">WhatsApp OTP Request Karein</button>
    <small class="customer-register-help">Request dukaan ko jayegi. Dukaan WhatsApp par OTP bhejegi.</small>
  </form>
  <form id="customer-otp-verify-form" class="hidden">
    <label>6 Digit OTP<input name="otp" inputmode="numeric" required minlength="6" maxlength="6" /></label>
    <label>Naya PIN<input name="pin" type="password" inputmode="numeric" required minlength="4" /></label>
    <label>Confirm PIN<input name="confirm_pin" type="password" inputmode="numeric" required minlength="4" /></label>
    <button type="submit">OTP Verify & Register</button>
    <button id="customer-request-again" class="customer-link-button" type="button">Mobile Number Badlein / Naya OTP</button>
  </form>
</div>
"""


def customer_registration_html() -> str:
    html = CUSTOMER_PORTAL_HTML
    html = html.replace(
        "<p>Apna mobile number aur dukaan se mila PIN daalein.</p>",
        '<p id="customer-auth-copy">Apna mobile number aur PIN daalein.</p>' + REGISTER_SWITCH,
        1,
    )
    html = html.replace(
        "</form>\n    </div>\n  </section>",
        "</form>" + REGISTER_FORM + "\n    </div>\n  </section>",
        1,
    )
    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="/customer-self-register.css?v=062" /></head>',
        1,
    )
    html = html.replace(
        "</body>",
        '<script src="/customer-self-register.js?v=062"></script></body>',
        1,
    )
    return html


@app.middleware("http")
async def serve_customer_registration_portal(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/customer":
        return HTMLResponse(
            customer_registration_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return await call_next(request)


_otp_paths = {
    "/api/customer/register/request-otp",
    "/api/customer/register/verify-otp",
    "/api/customer/otp-requests",
    "/api/customer/otp-requests/{request_id}",
}
_selected = []
for route in list(app.router.routes):
    path = getattr(route, "path", None)
    if path == "/api/customer/register":
        app.router.routes.remove(route)
    elif path in _otp_paths:
        app.router.routes.remove(route)
        _selected.append(route)
_fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _selected
