from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import COOKIE_NAME, _session_row, _set_session_cookie


OWNER_HTML = STATIC_DIR / "owner-stable.html"
OWNER_CSS = STATIC_DIR / "owner-stable.css"
OWNER_JS = STATIC_DIR / "owner-stable.js"
VERSION = "101"

CACHE_CLEANUP = r"""
<script id="kirana-cache-cleanup">
(function () {
  try {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations().then(function (rows) {
        rows.forEach(function (row) { row.unregister(); });
      }).catch(function () {});
    }
    if ('caches' in window) {
      caches.keys().then(function (keys) {
        return Promise.all(keys.map(function (key) { return caches.delete(key); }));
      }).catch(function () {});
    }
  } catch (ignore) {}
})();
</script>
"""


def no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


def stable_owner_page(token: str) -> HTMLResponse:
    page = OWNER_HTML.read_text(encoding="utf-8")
    page = page.replace("__OWNER_VERSION__", VERSION)
    page = page.replace("</head>", CACHE_CLEANUP + "</head>", 1)
    response = HTMLResponse(
        page,
        headers={
            **no_cache_headers(),
            "Clear-Site-Data": '"cache"',
            "X-Kirana-Owner-UI": VERSION,
        },
    )
    _set_session_cookie(response, token)
    return response


@app.middleware("http")
async def serve_isolated_stable_owner_app(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if request.method == "GET" and path == "/owner-stable.css":
        return Response(
            OWNER_CSS.read_text(encoding="utf-8"),
            media_type="text/css",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/owner-stable.js":
        return Response(
            OWNER_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/":
        handoff = request.query_params.get("handoff")
        cookie = request.cookies.get(COOKIE_NAME)
        session = _session_row(handoff) or _session_row(cookie)
        if session:
            return stable_owner_page(str(session["token"]))

    return await call_next(request)
