from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from backend.app import STATIC_DIR, app, current_user, db, hash_password, now_iso
from backend.order_portal_ext import ensure_order_schema, normalize_phone
from backend.saas_ext import ensure_saas_schema, slugify
import backend.customer_self_register_ext as customer_register
import backend.stable_owner_app_ext as stable_owner


OTP_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
CUSTOMER_REGISTER_VERSION = "111"
OWNER_OTP_VERSION = "111"
OWNER_OTP_JS = STATIC_DIR / "owner-customer-otp.js"
OWNER_OTP_CSS = STATIC_DIR / "owner-customer-otp.css"


class CustomerOtpRequestIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    shop_slug: str = Field(min_length=1, max_length=60)


class CustomerOtpVerifyIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    shop_slug: str = Field(min_length=1, max_length=60)
    otp: str = Field(min_length=6, max_length=6)
    pin: str = Field(min_length=4, max_length=128)
    confirm_pin: str = Field(min_length=4, max_length=128)


def shop_row(conn: Any, shop_slug: str) -> Any:
    row = conn.execute(
        """
        SELECT sb.business_id,sb.slug,sb.subscription_status,b.name AS business_name
        FROM saas_businesses sb
        JOIN businesses b ON b.id=sb.business_id
        WHERE sb.slug=?
        """,
        (slugify(shop_slug),),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop link is invalid. Please use the link shared by the shop.")
    if row["subscription_status"] in {"suspended", "expired"}:
        raise HTTPException(status_code=403, detail="Online ordering is currently unavailable for this shop.")
    return row


def matching_parties(conn: Any, business_id: int, phone: str) -> list[dict[str, Any]]:
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
    return [dict(row) for row in rows if normalize_phone(row["phone"]) == phone]


def registration_target(conn: Any, business_id: int, phone: str) -> tuple[dict[str, Any], Any | None]:
    matches = matching_parties(conn, business_id, phone)
    if not matches:
        raise HTTPException(
            status_code=404,
            detail="This mobile number is not saved in the shop's customer list. Ask the shop to update your mobile number.",
        )
    if len(matches) > 1:
        names = ", ".join(str(row["name"]) for row in matches[:3])
        raise HTTPException(
            status_code=409,
            detail=f"This mobile number is saved for more than one customer ({names}). Ask the shop to remove the duplicate number.",
        )

    party = matches[0]
    account = conn.execute(
        """
        SELECT * FROM customer_accounts
        WHERE business_id=? AND (party_id=? OR phone=?)
        ORDER BY CASE WHEN party_id=? THEN 0 ELSE 1 END,id
        LIMIT 1
        """,
        (business_id, party["id"], phone, party["id"]),
    ).fetchone()
    if account and int(account["party_id"]) != int(party["id"]):
        raise HTTPException(
            status_code=409,
            detail="This mobile number is linked to another customer account. Ask the shop to correct the customer mobile number.",
        )
    return party, account


def expire_old_otps(conn: Any, business_id: int, phone: str) -> None:
    conn.execute(
        """
        UPDATE customer_registration_otps
        SET status='expired'
        WHERE business_id=? AND phone=? AND status='pending'
        """,
        (business_id, phone),
    )


@app.post("/api/customer/register/request-otp")
def request_customer_registration_or_reset(payload: CustomerOtpRequestIn) -> dict[str, Any]:
    customer_register.ensure_customer_otp_schema()
    phone = normalize_phone(payload.phone)
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Enter a valid 10 digit mobile number")

    with db() as conn:
        shop = shop_row(conn, payload.shop_slug)
        party, account = registration_target(conn, int(shop["business_id"]), phone)
        now = datetime.now().replace(microsecond=0)
        recent = conn.execute(
            """
            SELECT * FROM customer_registration_otps
            WHERE business_id=? AND party_id=? AND phone=? AND status='pending'
            ORDER BY id DESC LIMIT 1
            """,
            (shop["business_id"], party["id"], phone),
        ).fetchone()

        if recent:
            created = datetime.fromisoformat(recent["created_at"])
            expires = datetime.fromisoformat(recent["expires_at"])
            if expires > now and (now - created).total_seconds() < 60:
                return {
                    "request_id": int(recent["id"]),
                    "customer_name": party["name"],
                    "masked_phone": f"******{phone[-4:]}",
                    "expires_in_minutes": OTP_MINUTES,
                    "mode": "reset" if account else "register",
                    "message": "OTP request is already pending. The shop will send it on WhatsApp.",
                }

        expire_old_otps(conn, int(shop["business_id"]), phone)
        otp = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = (now + timedelta(minutes=OTP_MINUTES)).isoformat()
        cursor = conn.execute(
            """
            INSERT INTO customer_registration_otps(
                business_id,party_id,phone,otp_code,status,attempts,expires_at,created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                shop["business_id"],
                party["id"],
                phone,
                otp,
                "pending",
                0,
                expires_at,
                now.isoformat(),
            ),
        )

    mode = "reset" if account else "register"
    return {
        "request_id": int(cursor.lastrowid),
        "customer_name": party["name"],
        "masked_phone": f"******{phone[-4:]}",
        "expires_in_minutes": OTP_MINUTES,
        "mode": mode,
        "message": (
            "PIN reset request sent to the shop. Enter the OTP sent by the shop on WhatsApp."
            if mode == "reset"
            else "Registration request sent to the shop. Enter the OTP sent by the shop on WhatsApp."
        ),
    }


@app.post("/api/customer/register/verify-otp")
def verify_customer_registration_or_reset(payload: CustomerOtpVerifyIn) -> dict[str, Any]:
    customer_register.ensure_customer_otp_schema()
    phone = normalize_phone(payload.phone)
    otp = str(payload.otp or "").strip()
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Enter a valid 10 digit mobile number")
    if not otp.isdigit() or len(otp) != 6:
        raise HTTPException(status_code=400, detail="Enter the 6 digit OTP")
    if payload.pin != payload.confirm_pin:
        raise HTTPException(status_code=400, detail="PIN and Confirm PIN do not match")

    with db() as conn:
        shop = shop_row(conn, payload.shop_slug)
        party, account = registration_target(conn, int(shop["business_id"]), phone)
        row = conn.execute(
            """
            SELECT * FROM customer_registration_otps
            WHERE business_id=? AND party_id=? AND phone=? AND status='pending'
            ORDER BY id DESC LIMIT 1
            """,
            (shop["business_id"], party["id"], phone),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No pending OTP request was found. Request a new OTP.")
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now():
            conn.execute("UPDATE customer_registration_otps SET status='expired' WHERE id=?", (row["id"],))
            raise HTTPException(status_code=410, detail="OTP has expired. Request a new OTP.")
        if int(row["attempts"] or 0) >= OTP_MAX_ATTEMPTS:
            conn.execute("UPDATE customer_registration_otps SET status='cancelled' WHERE id=?", (row["id"],))
            raise HTTPException(status_code=429, detail="Too many incorrect attempts. Request a new OTP.")
        if not secrets.compare_digest(str(row["otp_code"]), otp):
            conn.execute("UPDATE customer_registration_otps SET attempts=attempts+1 WHERE id=?", (row["id"],))
            remaining = OTP_MAX_ATTEMPTS - int(row["attempts"] or 0) - 1
            raise HTTPException(status_code=400, detail=f"Incorrect OTP. {max(0, remaining)} attempts remaining.")

        reset_existing = account is not None
        if account:
            account_id = int(account["id"])
            conn.execute(
                """
                UPDATE customer_accounts
                SET party_id=?,phone=?,password_hash=?,is_active=1,updated_at=?
                WHERE id=? AND business_id=?
                """,
                (
                    party["id"],
                    phone,
                    hash_password(payload.pin),
                    now_iso(),
                    account_id,
                    shop["business_id"],
                ),
            )
            conn.execute("DELETE FROM customer_sessions WHERE customer_account_id=?", (account_id,))
        else:
            cursor = conn.execute(
                """
                INSERT INTO customer_accounts(
                    business_id,party_id,phone,password_hash,is_active,created_at,updated_at
                ) VALUES(?,?,?,?,1,?,?)
                """,
                (
                    shop["business_id"],
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
        "customer": {
            "party_id": party["id"],
            "party_name": party["name"],
            "phone": phone,
        },
        "business_name": shop["business_name"],
        "shop_slug": shop["slug"],
        "registered": not reset_existing,
        "pin_reset": reset_existing,
        "expires_at": expires_at,
    }


_original_registration_html = customer_register.customer_registration_html


def customer_registration_html_v111() -> str:
    html = _original_registration_html()
    for old_version in ("060", "061", "062", "109", "110"):
        html = html.replace(
            f"/customer-self-register.js?v={old_version}",
            f"/customer-self-register.js?v={CUSTOMER_REGISTER_VERSION}",
        )
    html = html.replace(">Register</button>", ">Register / Reset PIN</button>")
    html = html.replace(
        "Database wale mobile number se WhatsApp OTP lekar register karein.",
        "Use your saved mobile number to register or reset your PIN with WhatsApp OTP.",
    )
    return html


customer_register.customer_registration_html = customer_registration_html_v111


_original_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_customer_otp(token: str) -> HTMLResponse:
    original = _original_owner_page(token)
    html = original.body.decode("utf-8")
    if "/owner-customer-otp.css" not in html:
        html = html.replace(
            "</head>",
            f'<link rel="stylesheet" href="/owner-customer-otp.css?v={OWNER_OTP_VERSION}" /></head>',
            1,
        )
    if "/owner-customer-otp.js" not in html:
        html = html.replace(
            "</body>",
            f'<script src="/owner-customer-otp.js?v={OWNER_OTP_VERSION}"></script></body>',
            1,
        )
    headers = {
        key: value
        for key, value in original.headers.items()
        if key.lower() not in {"content-length", "content-type", "set-cookie"}
    }
    response = HTMLResponse(html, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie:
        response.headers.append("set-cookie", cookie)
    return response


stable_owner.stable_owner_page = stable_owner_page_with_customer_otp


@app.middleware("http")
async def serve_customer_registration_reset_assets(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if request.method == "GET" and path == "/owner-customer-otp.js":
        return Response(OWNER_OTP_JS.read_text(encoding="utf-8"), media_type="application/javascript", headers=headers)
    if request.method == "GET" and path == "/owner-customer-otp.css":
        return Response(OWNER_OTP_CSS.read_text(encoding="utf-8"), media_type="text/css", headers=headers)
    return await call_next(request)


# Keep only the latest registration/reset endpoints and place them before the SPA fallback.
_latest_routes = []
for route in list(app.router.routes):
    path = getattr(route, "path", None)
    endpoint = getattr(route, "endpoint", None)
    if path == "/api/customer/register/request-otp":
        app.router.routes.remove(route)
        if endpoint is request_customer_registration_or_reset:
            _latest_routes.append(route)
    elif path == "/api/customer/register/verify-otp":
        app.router.routes.remove(route)
        if endpoint is verify_customer_registration_or_reset:
            _latest_routes.append(route)

_fallback_index = next(
    (
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _latest_routes
