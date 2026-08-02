from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app
import backend.stable_owner_app_ext as stable_owner


CATALOG_CSS = STATIC_DIR / "owner-customer-catalog.css"
CATALOG_JS = STATIC_DIR / "owner-customer-catalog.js"
CATALOG_VERSION = "107"
_original_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_catalog(token: str) -> HTMLResponse:
    original = _original_stable_owner_page(token)
    html = original.body.decode("utf-8")
    if "/owner-customer-catalog.css" not in html:
        html = html.replace(
            "</head>",
            f'<link rel="stylesheet" href="/owner-customer-catalog.css?v={CATALOG_VERSION}" /></head>',
            1,
        )
    if "/owner-customer-catalog.js" not in html:
        html = html.replace(
            "</body>",
            f'<script src="/owner-customer-catalog.js?v={CATALOG_VERSION}"></script></body>',
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


# The stable owner middleware resolves this module global at request time.
stable_owner.stable_owner_page = stable_owner_page_with_catalog


@app.middleware("http")
async def serve_customer_catalog_owner_assets(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if request.method == "GET" and path == "/owner-customer-catalog.css":
        return Response(CATALOG_CSS.read_text(encoding="utf-8"), media_type="text/css", headers=headers)
    if request.method == "GET" and path == "/owner-customer-catalog.js":
        return Response(CATALOG_JS.read_text(encoding="utf-8"), media_type="application/javascript", headers=headers)
    return await call_next(request)
