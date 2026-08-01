from __future__ import annotations

import html
import json
import secrets
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.app import app, db, now_iso, verify_password


COOKIE_NAME = "ks_owner_session"
SESSION_DAYS = 30
FRONTEND_VERSION = "074"


def _session_row(token: str | None):
    if not token:
        return None
    with db() as conn:
        return conn.execute(
            """
            SELECT s.token, s.user_id, s.expires_at, u.username, u.business_id
            FROM sessions s
            JOIN users u ON u.id=s.user_id
            WHERE s.token=? AND s.expires_at>?
            """,
            (token, now_iso()),
        ).fetchone()


def _set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        expires=SESSION_DAYS * 24 * 60 * 60,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _login_page(error: str = "", username: str = "admin", status_code: int = 200) -> HTMLResponse:
    safe_error = html.escape(error)
    safe_username = html.escape(username or "admin", quote=True)
    error_box = (
        f'<div class="message error" role="alert">{safe_error}</div>'
        if safe_error
        else '<div class="message info">Enter your owner PIN to continue.</div>'
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <meta name="theme-color" content="#087fbf" />
  <title>Kirana Software Login</title>
  <style>
    *{{box-sizing:border-box}}
    html,body{{margin:0;min-height:100%;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:#eef7fd;color:#263545}}
    body{{min-height:100vh;background:linear-gradient(180deg,#087fbf 0 38%,#eef7fd 38%);padding:env(safe-area-inset-top) 18px calc(28px + env(safe-area-inset-bottom))}}
    .brand{{max-width:560px;margin:64px auto 38px;display:flex;align-items:center;gap:20px;color:#fff}}
    .logo{{width:86px;height:86px;border-radius:26px;background:linear-gradient(145deg,#1596d7,#5bbcf0);display:grid;place-items:center;font-size:52px;font-weight:900;box-shadow:0 16px 35px rgba(0,0,0,.14)}}
    .brand h1{{font-size:38px;line-height:1.05;margin:0 0 10px}}
    .brand p{{font-size:18px;margin:0;opacity:.92}}
    .card{{max-width:560px;margin:0 auto;background:#fff;border-radius:28px;padding:34px;box-shadow:0 18px 55px rgba(8,74,112,.18)}}
    .eyebrow{{font-size:13px;letter-spacing:1.8px;font-weight:900;color:#0876ae}}
    h2{{font-size:40px;line-height:1.05;margin:14px 0 30px}}
    label{{display:block;font-size:16px;font-weight:800;margin:18px 0 8px;color:#56616d}}
    input{{display:block;width:100%;min-height:66px;border:2px solid #d7e1e7;border-radius:16px;background:#fff;padding:15px 18px;font-size:20px;color:#1f2e3a;outline:none;touch-action:manipulation}}
    input:focus{{border-color:#0b82c2;box-shadow:0 0 0 4px rgba(11,130,194,.12)}}
    button{{display:block;width:100%;min-height:68px;margin-top:28px;border:0;border-radius:16px;background:#0b82c2;color:#fff;font-size:20px;font-weight:900;touch-action:manipulation;-webkit-tap-highlight-color:transparent}}
    button:active{{transform:translateY(1px);background:#086fa7}}
    .message{{margin:0 0 18px;padding:13px 15px;border-radius:13px;font-size:14px;font-weight:750;line-height:1.45}}
    .message.info{{background:#e9f5fc;color:#075f91;border:1px solid #b7dcf1}}
    .message.error{{background:#fff0ef;color:#b42318;border:1px solid #ffc9c5}}
    .help{{margin:20px 0 0;text-align:center;color:#6d7a86;font-size:14px}}
    @media(max-width:620px){{
      body{{padding-left:0;padding-right:0}}
      .brand{{margin:58px 28px 34px}}
      .logo{{width:74px;height:74px;font-size:45px;border-radius:22px;flex:0 0 auto}}
      .brand h1{{font-size:31px}}
      .brand p{{font-size:15px}}
      .card{{margin:0 18px;padding:28px 24px;border-radius:25px}}
      h2{{font-size:36px}}
    }}
  </style>
</head>
<body>
  <header class="brand">
    <div class="logo">K</div>
    <div><h1>Kirana Software</h1><p>Billing, Inventory & Accounts — All in One</p></div>
  </header>
  <main class="card">
    <div class="eyebrow">SECURE OWNER LOGIN</div>
    <h2>Welcome back</h2>
    {error_box}
    <form action="/owner/session-login" method="post" autocomplete="on">
      <label for="username">Username</label>
      <input id="username" name="username" value="{safe_username}" autocomplete="username" required />
      <label for="password">PIN / Password</label>
      <input id="password" name="password" type="password" inputmode="numeric" autocomplete="current-password" minlength="4" required autofocus />
      <button type="submit">Login</button>
    </form>
    <p class="help">Secure server login for the Kirana Software owner app.</p>
  </main>
</body>
</html>"""
    return HTMLResponse(
        page,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def _dashboard_page(token: str) -> HTMLResponse:
    # Import lazily to avoid module import cycles during startup.
    from backend.frontend_rescue_ext import no_cache_headers, owner_html

    token_json = json.dumps(token)
    bootstrap = f"""
<script>
(() => {{
  const token = {token_json};
  try {{ localStorage.setItem('ks_token', token); }} catch (_) {{}}
  try {{ history.replaceState(null, '', '/?session=1&v={FRONTEND_VERSION}'); }} catch (_) {{}}
}})();
</script>
<style id="owner-authenticated-first-paint">
  #auth-screen{{display:none!important}}
  #app-shell{{display:block!important}}
</style>
"""
    page = owner_html()
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
    page = page.replace("</head>", bootstrap + "</head>", 1)
    response = HTMLResponse(page, headers=no_cache_headers())
    response.headers["X-Owner-Session-Version"] = FRONTEND_VERSION
    _set_session_cookie(response, token)
    return response


def _replace_authorization_header(request: Request, token: str) -> None:
    headers = [
        (key, value)
        for key, value in request.scope.get("headers", [])
        if key.lower() != b"authorization"
    ]
    headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))
    request.scope["headers"] = headers


@app.middleware("http")
async def owner_server_session(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if request.method == "POST" and path == "/owner/session-login":
        body = (await request.body()).decode("utf-8", errors="replace")
        fields = parse_qs(body, keep_blank_values=True)
        username = (fields.get("username", ["admin"])[0] or "admin").strip().lower()
        password = fields.get("password", [""])[0]

        if not password:
            return _login_page("Enter your PIN or password.", username, 400)

        with db() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.username, u.password_hash, u.business_id
                FROM users u
                WHERE u.username=?
                """,
                (username,),
            ).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return _login_page("The username or PIN is incorrect.", username, 401)

            token = secrets.token_urlsafe(40)
            expires_at = (datetime.now() + timedelta(days=SESSION_DAYS)).replace(microsecond=0).isoformat()
            conn.execute("DELETE FROM sessions WHERE expires_at<=?", (now_iso(),))
            conn.execute(
                "INSERT INTO sessions(token,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                (token, row["id"], expires_at, now_iso()),
            )

        response = RedirectResponse(
            url=f"/?handoff={quote(token)}&v={FRONTEND_VERSION}",
            status_code=303,
            headers={"Cache-Control": "no-store"},
        )
        _set_session_cookie(response, token)
        return response

    cookie_token = request.cookies.get(COOKIE_NAME)
    handoff_token = request.query_params.get("handoff") if path == "/" else None
    session = _session_row(handoff_token) or _session_row(cookie_token)

    if request.method == "GET" and path == "/owner-login":
        if session:
            return RedirectResponse(f"/?session=1&v={FRONTEND_VERSION}", status_code=303)
        return _login_page()

    if request.method == "GET" and path == "/":
        if not session:
            return _login_page()
        return _dashboard_page(str(session["token"]))

    if session and path.startswith("/api/"):
        _replace_authorization_header(request, str(session["token"]))

    response = await call_next(request)

    if path == "/api/logout":
        response.delete_cookie(COOKIE_NAME, path="/")

    return response
