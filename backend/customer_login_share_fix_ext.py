from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from backend.app import STATIC_DIR, app, current_user, db, now_iso, verify_password
from backend.order_portal_ext import ensure_order_schema, normalize_phone
from backend.saas_ext import ensure_saas_schema, slugify
import backend.customer_self_register_ext as customer_register
import backend.stable_owner_app_ext as stable_owner


CUSTOMER_ASSET_VERSION = "109"
OWNER_SHARE_VERSION = "109"
CUSTOMER_ORDER_JS = STATIC_DIR / "customer-order.js"
OWNER_SHARE_JS = STATIC_DIR / "owner-customer-share.js"
OWNER_SHARE_CSS = STATIC_DIR / "owner-customer-share.css"


class CustomerShopLoginIn(BaseModel):
    phone: str
    pin: str
    shop_slug: str = ""


def active_shop_row(conn: Any, shop_slug: str) -> Any:
    slug = slugify(shop_slug)
    row = conn.execute(
        """
        SELECT sb.business_id,sb.slug,sb.subscription_status,b.name AS business_name
        FROM saas_businesses sb
        JOIN businesses b ON b.id=sb.business_id
        WHERE sb.slug=?
        """,
        (slug,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop link is invalid. Please use the link shared by the shop.")
    if row["subscription_status"] in {"suspended", "expired"}:
        raise HTTPException(status_code=403, detail="Online ordering is currently unavailable for this shop.")
    return row


@app.post("/api/customer/login")
def customer_shop_login(payload: CustomerShopLoginIn) -> dict[str, Any]:
    ensure_order_schema()
    ensure_saas_schema()
    phone = normalize_phone(payload.phone)
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Enter a valid 10 digit mobile number")

    with db() as conn:
        shop = active_shop_row(conn, payload.shop_slug) if payload.shop_slug.strip() else None
        sql = """
            SELECT ca.*,p.name AS party_name,b.name AS business_name,sb.slug
            FROM customer_accounts ca
            JOIN parties p ON p.id=ca.party_id
            JOIN businesses b ON b.id=ca.business_id
            JOIN saas_businesses sb ON sb.business_id=ca.business_id
            WHERE ca.phone=? AND ca.is_active=1
        """
        args: list[Any] = [phone]
        if shop:
            sql += " AND ca.business_id=?"
            args.append(int(shop["business_id"]))
        rows = conn.execute(sql, args).fetchall()

        if not rows:
            raise HTTPException(status_code=401, detail="Mobile number or PIN is incorrect")
        if len(rows) > 1:
            raise HTTPException(status_code=409, detail="Please open the exact customer link shared by your shop")

        row = rows[0]
        if not verify_password(payload.pin, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Mobile number or PIN is incorrect")

        token = secrets.token_urlsafe(40)
        expires_at = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
        conn.execute("DELETE FROM customer_sessions WHERE expires_at<=?", (now_iso(),))
        # Keep one current session per customer account. This removes stale sessions
        # that can otherwise race with a newly completed login in the browser.
        conn.execute(
            "DELETE FROM customer_sessions WHERE customer_account_id=?",
            (row["id"],),
        )
        conn.execute(
            "INSERT INTO customer_sessions(token,customer_account_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token, row["id"], expires_at, now_iso()),
        )

    return {
        "token": token,
        "customer": {
            "party_id": row["party_id"],
            "party_name": row["party_name"],
            "phone": row["phone"],
        },
        "business_name": row["business_name"],
        "shop_slug": row["slug"],
        "expires_at": expires_at,
    }


@app.get("/api/customer/share-info")
def customer_share_info(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    ensure_saas_schema()
    with db() as conn:
        row = conn.execute(
            """
            SELECT b.name AS business_name,sb.slug
            FROM businesses b
            JOIN saas_businesses sb ON sb.business_id=b.id
            WHERE b.id=?
            """,
            (user["business_id"],),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer ordering link is not configured")
    return {
        "business_name": row["business_name"],
        "shop_slug": row["slug"],
        "customer_order_path": f"/customer?shop={row['slug']}",
    }


_original_registration_html = customer_register.customer_registration_html


def customer_registration_html_v109() -> str:
    html = _original_registration_html()
    html = html.replace("/customer-order.js?v=060", f"/customer-order.js?v={CUSTOMER_ASSET_VERSION}")
    html = html.replace("/customer-order.js?v=061", f"/customer-order.js?v={CUSTOMER_ASSET_VERSION}")
    html = html.replace("/customer-order.js?v=062", f"/customer-order.js?v={CUSTOMER_ASSET_VERSION}")
    return html


customer_register.customer_registration_html = customer_registration_html_v109


_original_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_share(token: str) -> HTMLResponse:
    original = _original_stable_owner_page(token)
    html = original.body.decode("utf-8")
    if "/owner-customer-share.css" not in html:
        html = html.replace(
            "</head>",
            f'<link rel="stylesheet" href="/owner-customer-share.css?v={OWNER_SHARE_VERSION}" /></head>',
            1,
        )
    if "/owner-customer-share.js" not in html:
        html = html.replace(
            "</body>",
            f'<script src="/owner-customer-share.js?v={OWNER_SHARE_VERSION}"></script></body>',
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


stable_owner.stable_owner_page = stable_owner_page_with_share


@app.middleware("http")
async def serve_customer_login_share_assets(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if request.method == "GET" and path == "/customer-order.js":
        return Response(
            CUSTOMER_ORDER_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers=headers,
        )
    if request.method == "GET" and path == "/owner-customer-share.js":
        return Response(
            OWNER_SHARE_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers=headers,
        )
    if request.method == "GET" and path == "/owner-customer-share.css":
        return Response(
            OWNER_SHARE_CSS.read_text(encoding="utf-8"),
            media_type="text/css",
            headers=headers,
        )
    return await call_next(request)


# Replace every older customer-login route and place these APIs ahead of the SPA fallback.
_selected_routes = []
for route in list(app.router.routes):
    path = getattr(route, "path", None)
    endpoint = getattr(route, "endpoint", None)
    if path == "/api/customer/login":
        app.router.routes.remove(route)
        if endpoint is customer_shop_login:
            _selected_routes.append(route)
    elif path == "/api/customer/share-info":
        app.router.routes.remove(route)
        if endpoint is customer_share_info:
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
