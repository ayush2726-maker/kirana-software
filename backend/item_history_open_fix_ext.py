from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "129"
ASSET = STATIC_DIR / "owner-item-bill-open.js"
ASSET_URL = f"/owner-item-bill-open.js?v={VERSION}"


if ASSET_URL not in native_owner.OPTIONAL_JS_URLS:
    native_owner.OPTIONAL_JS_URLS.append(ASSET_URL)
if ASSET not in final_owner.JS_FILES:
    final_owner.JS_FILES.append(ASSET)

native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION


_previous_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_item_bill_open(token: str) -> HTMLResponse:
    original = _previous_stable_owner_page(token)
    page = original.body.decode("utf-8")
    if ASSET_URL not in page:
        page = page.replace("</body>", f'<script src="{ASSET_URL}"></script></body>', 1)
    headers = {
        key: value
        for key, value in original.headers.items()
        if key.lower() not in {"content-length", "content-type", "set-cookie"}
    }
    response = HTMLResponse(page, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie:
        response.headers.append("set-cookie", cookie)
    return response


stable_owner.stable_owner_page = stable_owner_page_with_item_bill_open


@app.middleware("http")
async def serve_item_bill_open_asset(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-item-bill-open.js":
        return Response(
            ASSET.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Kirana-Item-Bill-Open": VERSION,
            },
        )
    return await call_next(request)
