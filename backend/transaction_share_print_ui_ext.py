from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "123"
ACTIONS_JS = STATIC_DIR / "owner-transaction-actions.js"
ASSET_URL = f"/owner-transaction-actions.js?v={VERSION}"


_original_patched_owner_js = stable_owner.patched_owner_js


def patched_owner_js_with_transaction_ids() -> str:
    script = _original_patched_owner_js()
    old = "return '<article class=\"transaction-card\">' +"
    new = (
        "return '<article class=\"transaction-card\" data-transaction-id=\"' + "
        "Number(row.id || 0) + '\" data-transaction-kind=\"' + escapeHtml(kind) + '\">' +"
    )
    if old in script and "data-transaction-id" not in script:
        script = script.replace(old, new, 1)
    return script


stable_owner.patched_owner_js = patched_owner_js_with_transaction_ids
stable_owner.VERSION = VERSION
final_owner.BUILD = VERSION

if ASSET_URL not in native_owner.OPTIONAL_JS_URLS:
    native_owner.OPTIONAL_JS_URLS.append(ASSET_URL)
if ACTIONS_JS not in final_owner.JS_FILES:
    final_owner.JS_FILES.append(ACTIONS_JS)


_original_stable_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_transaction_actions(token: str) -> HTMLResponse:
    original = _original_stable_owner_page(token)
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


stable_owner.stable_owner_page = stable_owner_page_with_transaction_actions


@app.middleware("http")
async def serve_transaction_action_asset(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/owner-transaction-actions.js":
        return Response(
            ACTIONS_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return await call_next(request)
