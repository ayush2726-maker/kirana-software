from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.app import app, db, hash_password, now_iso
from backend.order_portal_ext import CUSTOMER_PORTAL_HTML, ensure_order_schema, normalize_phone


class CustomerRegisterIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    pin: str = Field(min_length=4, max_length=128)
    confirm_pin: str = Field(min_length=4, max_length=128)


def matching_customer_parties(conn, phone: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    rows = conn.execute(
        """
        SELECT id,business_id,name,phone,type
        FROM parties
        WHERE type IN ('customer','both') AND TRIM(COALESCE(phone,''))<>''
        ORDER BY business_id,id
        """
    ).fetchall()
    for row in rows:
        if normalize_phone(row["phone"]) == phone:
            matches.append(dict(row))
    return matches


@app.post("/api/customer/register")
def customer_self_register(payload: CustomerRegisterIn) -> dict[str, Any]:
    ensure_order_schema()
    phone = normalize_phone(payload.phone)
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Valid 10 digit mobile number daalein")
    if payload.pin != payload.confirm_pin:
        raise HTTPException(status_code=400, detail="PIN aur Confirm PIN match nahi kar rahe")

    with db() as conn:
        matches = matching_customer_parties(conn, phone)
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
            (party["business_id"], party["id"]),
        ).fetchone()
        if existing:
            if existing["is_active"]:
                raise HTTPException(
                    status_code=409,
                    detail="Is mobile number ka account pehle se registered hai. Login karein ya dukaan se PIN reset karwayein.",
                )
            raise HTTPException(
                status_code=403,
                detail="Customer login blocked hai. Dukaan se contact karein.",
            )

        phone_owner = conn.execute(
            "SELECT id,party_id FROM customer_accounts WHERE business_id=? AND phone=?",
            (party["business_id"], phone),
        ).fetchone()
        if phone_owner:
            raise HTTPException(
                status_code=409,
                detail="Ye mobile number kisi doosre customer login se juda hua hai. Dukaan se contact karein.",
            )

        cursor = conn.execute(
            """
            INSERT INTO customer_accounts(
                business_id,party_id,phone,password_hash,is_active,created_at,updated_at
            ) VALUES(?,?,?,?,1,?,?)
            """,
            (
                party["business_id"],
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
        business = conn.execute(
            "SELECT name FROM businesses WHERE id=?",
            (party["business_id"],),
        ).fetchone()

    return {
        "token": token,
        "customer": {
            "party_id": party["id"],
            "party_name": party["name"],
            "phone": phone,
        },
        "business_name": business["name"] if business else "Kishore Traders",
        "registered": True,
    }


REGISTER_SWITCH = """
<div class="customer-auth-switch" role="tablist" aria-label="Customer login or registration">
  <button id="customer-show-login" class="active" type="button">Login</button>
  <button id="customer-show-register" type="button">Register</button>
</div>
"""

REGISTER_FORM = """
<form id="customer-register-form" class="hidden">
  <label>Database wala mobile number<input name="phone" inputmode="tel" required maxlength="15" /></label>
  <label>Naya PIN<input name="pin" type="password" inputmode="numeric" required minlength="4" /></label>
  <label>Confirm PIN<input name="confirm_pin" type="password" inputmode="numeric" required minlength="4" /></label>
  <button type="submit">Register & Login</button>
  <small class="customer-register-help">Sirf wahi mobile register hoga jo Kishore Traders ke customer database mein saved hai.</small>
</form>
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
        '<link rel="stylesheet" href="/customer-self-register.css?v=061" /></head>',
        1,
    )
    html = html.replace(
        "</body>",
        '<script src="/customer-self-register.js?v=061"></script></body>',
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


# Keep the registration API ahead of the SPA fallback route.
_register_routes = [
    route for route in app.router.routes
    if getattr(route, "path", None) == "/api/customer/register"
]
for route in _register_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _register_routes
