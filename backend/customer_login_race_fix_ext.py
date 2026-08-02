from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from backend.app import STATIC_DIR, app
import backend.customer_self_register_ext as customer_register


CUSTOMER_ORDER_JS = STATIC_DIR / "customer-order.js"
CUSTOMER_LOGIN_VERSION = "112"


_original_registration_html = customer_register.customer_registration_html


def customer_registration_html_v112() -> str:
    html = _original_registration_html()
    for old_version in ("060", "061", "062", "109", "110", "111"):
        html = html.replace(
            f"/customer-order.js?v={old_version}",
            f"/customer-order.js?v={CUSTOMER_LOGIN_VERSION}",
        )
    return html


customer_register.customer_registration_html = customer_registration_html_v112


@app.middleware("http")
async def serve_shop_isolated_customer_login(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/customer-order.js":
        return Response(
            CUSTOMER_ORDER_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return await call_next(request)
