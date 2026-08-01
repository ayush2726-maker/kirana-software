from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from backend.app import app
from backend.owner_session_ext import COOKIE_NAME, _dashboard_page, _session_row


@app.middleware("http")
async def render_authenticated_owner_dashboard(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method != "GET" or path != "/":
        return await call_next(request)

    handoff_token = request.query_params.get("handoff")
    cookie_token = request.cookies.get(COOKIE_NAME)
    session = _session_row(handoff_token) or _session_row(cookie_token)
    if not session:
        return await call_next(request)

    response = _dashboard_page(str(session["token"]))
    page = bytes(response.body).decode("utf-8", errors="replace")

    # Authenticated users must never see the login card again while the
    # dashboard bundle starts. Show the app shell immediately on the server.
    page = page.replace(
        '<section id="auth-screen" class="auth-screen">',
        '<section id="auth-screen" class="auth-screen hidden">',
        1,
    )
    page = page.replace(
        '<div id="app-shell" class="app-shell hidden">',
        '<div id="app-shell" class="app-shell">',
        1,
    )
    page = page.replace(
        "</head>",
        '<style id="owner-session-first-paint">#auth-screen{display:none!important}#app-shell{display:block!important}</style></head>',
        1,
    )

    headers = dict(response.headers)
    headers.update(
        {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Owner-Dashboard-Session": "direct-073",
        }
    )
    direct = HTMLResponse(page, status_code=response.status_code, headers=headers)
    # Preserve the secure session cookie set by _dashboard_page.
    for raw_cookie in response.headers.getlist("set-cookie"):
        direct.headers.append("set-cookie", raw_cookie)
    return direct
