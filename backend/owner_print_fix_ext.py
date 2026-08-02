from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import (
    COOKIE_NAME,
    _replace_authorization_header,
    _session_row,
)
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "127"
ASSET = STATIC_DIR / "owner-print-fix.js"
ASSET_URL = f"/owner-print-fix.js?v={VERSION}"


if ASSET_URL not in native_owner.OPTIONAL_JS_URLS:
    native_owner.OPTIONAL_JS_URLS.append(ASSET_URL)
if ASSET not in final_owner.JS_FILES:
    final_owner.JS_FILES.append(ASSET)

native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION


_previous_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_print_fix(token: str) -> HTMLResponse:
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


stable_owner.stable_owner_page = stable_owner_page_with_print_fix


@app.middleware("http")
async def owner_print_session_and_asset_fix(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if request.method == "GET" and path == "/owner-print-fix.js":
        return Response(
            ASSET.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Kirana-Print-Fix": VERSION,
            },
        )

    # /owner/bulk-print is an HTML route, not an /api route. The normal owner
    # session middleware historically injected the bearer token only for
    # /api/*, causing an authenticated print request to fail with
    # {"detail":"Login required"}. Reuse the secure owner cookie here before
    # FastAPI resolves the current_user dependency.
    if path == "/owner/bulk-print":
        cookie_token = request.cookies.get(COOKIE_NAME)
        session = _session_row(cookie_token)
        if session:
            _replace_authorization_header(request, str(session["token"]))

    response = await call_next(request)
    if path == "/owner/bulk-print":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["X-Kirana-Print-Fix"] = VERSION
    return response
