from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "124"
IMPORT_JS = STATIC_DIR / "owner-import-center.js"
IMPORT_URL = f"/owner-import-center.js?v={VERSION}"

if IMPORT_URL not in native_owner.OPTIONAL_JS_URLS:
    native_owner.OPTIONAL_JS_URLS.append(IMPORT_URL)
if IMPORT_JS not in final_owner.JS_FILES:
    final_owner.JS_FILES.append(IMPORT_JS)
final_owner.BUILD = VERSION


_original_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_import_center(token: str) -> HTMLResponse:
    original = _original_stable_owner_page(token)
    html = original.body.decode("utf-8")
    if IMPORT_URL not in html:
        html = html.replace("</body>", f'<script src="{IMPORT_URL}"></script></body>', 1)
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


stable_owner.stable_owner_page = stable_owner_page_with_import_center


@app.middleware("http")
async def serve_owner_import_center_asset(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-import-center.js":
        return Response(
            IMPORT_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return await call_next(request)
