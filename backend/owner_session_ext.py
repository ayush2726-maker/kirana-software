from __future__ import annotations

import html
import json
import secrets
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from backend.app import app, db, now_iso, verify_password


COOKIE_NAME = "ks_owner_session"
SESSION_DAYS = 30
FRONTEND_VERSION = "075"


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
    .auth-divider{{display:flex;align-items:center;gap:12px;margin:23px 0 16px;color:#8a98a1;font-size:13px;font-weight:750}}
    .auth-divider::before,.auth-divider::after{{content:"";height:1px;background:#dfe7ec;flex:1}}
    .register-link{{display:grid;place-items:center;width:100%;min-height:62px;border:2px solid #0b82c2;border-radius:16px;background:#fff;color:#0875ad;text-decoration:none;font-size:18px;font-weight:900;touch-action:manipulation;-webkit-tap-highlight-color:transparent}}
    .register-link:active{{background:#eef8fd;transform:translateY(1px)}}
    .register-help{{margin:10px 0 0;text-align:center;color:#6d7a86;font-size:13px;line-height:1.45}}
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
    <div class="auth-divider"><span>New shop owner?</span></div>
    <a class="register-link" href="/owner-register">New Registration</a>
    <p class="register-help">Create a separate owner account for your shop.</p>
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


def _registration_page(
    error: str = "",
    values: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    values = values or {}

    def field(name: str) -> str:
        return html.escape(values.get(name, ""), quote=True)

    error_box = (
        f'<div class="message error" role="alert">{html.escape(error)}</div>'
        if error
        else '<div class="message info">Enter your shop and owner details to create a new account.</div>'
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <meta name="theme-color" content="#087fbf" />
  <title>New Registration · Kirana Software</title>
  <style>
    *{{box-sizing:border-box}}
    html,body{{margin:0;min-height:100%;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:#eef7fd;color:#263545}}
    body{{min-height:100vh;background:linear-gradient(180deg,#087fbf 0 280px,#eef7fd 280px);padding:env(safe-area-inset-top) 18px calc(28px + env(safe-area-inset-bottom))}}
    .brand{{max-width:620px;margin:42px auto 28px;display:flex;align-items:center;gap:18px;color:#fff}}
    .logo{{width:76px;height:76px;border-radius:23px;background:linear-gradient(145deg,#1596d7,#5bbcf0);display:grid;place-items:center;font-size:46px;font-weight:900;box-shadow:0 16px 35px rgba(0,0,0,.14)}}
    .brand h1{{font-size:34px;line-height:1.05;margin:0 0 8px}}
    .brand p{{font-size:16px;margin:0;opacity:.92}}
    .card{{max-width:620px;margin:0 auto;background:#fff;border-radius:28px;padding:34px;box-shadow:0 18px 55px rgba(8,74,112,.18)}}
    .back{{display:inline-flex;align-items:center;color:#0875ad;text-decoration:none;font-size:15px;font-weight:850;margin-bottom:22px}}
    .eyebrow{{font-size:13px;letter-spacing:1.8px;font-weight:900;color:#0876ae}}
    h2{{font-size:36px;line-height:1.08;margin:12px 0 22px}}
    .message{{margin:0 0 18px;padding:13px 15px;border-radius:13px;font-size:14px;font-weight:750;line-height:1.45}}
    .message.info{{background:#e9f5fc;color:#075f91;border:1px solid #b7dcf1}}
    .message.error{{background:#fff0ef;color:#b42318;border:1px solid #ffc9c5}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}}
    label{{display:block;font-size:14px;font-weight:800;margin:14px 0 7px;color:#56616d}}
    label.full{{grid-column:1/-1}}
    input,textarea{{display:block;width:100%;min-height:56px;border:2px solid #d7e1e7;border-radius:14px;background:#fff;padding:13px 15px;font-size:17px;color:#1f2e3a;outline:none}}
    textarea{{min-height:82px;resize:vertical}}
    input:focus,textarea:focus{{border-color:#0b82c2;box-shadow:0 0 0 4px rgba(11,130,194,.12)}}
    button{{display:block;width:100%;min-height:64px;margin-top:24px;border:0;border-radius:16px;background:#0b82c2;color:#fff;font-size:19px;font-weight:900;touch-action:manipulation}}
    button:active{{transform:translateY(1px);background:#086fa7}}
    .required{{color:#b42318}}
    .help{{margin:14px 0 0;text-align:center;color:#6d7a86;font-size:13px;line-height:1.45}}
    @media(max-width:620px){{
      body{{padding-left:0;padding-right:0}}
      .brand{{margin:34px 28px 24px}}
      .logo{{width:66px;height:66px;font-size:40px;border-radius:20px;flex:0 0 auto}}
      .brand h1{{font-size:28px}}
      .brand p{{font-size:14px}}
      .card{{margin:0 12px;padding:27px 22px;border-radius:25px}}
      h2{{font-size:32px}}
      .grid{{grid-template-columns:1fr}}
      label.full{{grid-column:auto}}
    }}
  </style>
</head>
<body>
  <header class="brand">
    <div class="logo">K</div>
    <div><h1>Kirana Software</h1><p>Billing, Inventory & Accounts — All in One</p></div>
  </header>
  <main class="card">
    <a class="back" href="/owner-login">← Back to Login</a>
    <div class="eyebrow">NEW OWNER REGISTRATION</div>
    <h2>Create your shop account</h2>
    {error_box}
    <form action="/owner/session-register" method="post" autocomplete="on">
      <div class="grid">
        <label class="full">Shop / Firm Name <span class="required">*</span>
          <input name="business_name" value="{field('business_name')}" minlength="2" required autofocus />
        </label>
        <label>Owner Name
          <input name="owner_name" value="{field('owner_name')}" autocomplete="name" />
        </label>
        <label>Mobile Number <span class="required">*</span>
          <input name="phone" value="{field('phone')}" inputmode="numeric" autocomplete="tel" minlength="10" maxlength="10" pattern="[0-9]{{10}}" required />
        </label>
        <label class="full">Address
          <textarea name="address" rows="2">{html.escape(values.get('address', ''))}</textarea>
        </label>
        <label class="full">GSTIN (Optional)
          <input name="gstin" value="{field('gstin')}" autocomplete="off" />
        </label>
        <label>Login Username <span class="required">*</span>
          <input name="username" value="{field('username')}" minlength="3" autocomplete="username" required />
        </label>
        <label>PIN / Password <span class="required">*</span>
          <input name="password" type="password" inputmode="numeric" minlength="4" autocomplete="new-password" required />
        </label>
        <label class="full">Confirm PIN / Password <span class="required">*</span>
          <input name="confirm_password" type="password" inputmode="numeric" minlength="4" autocomplete="new-password" required />
        </label>
      </div>
      <button type="submit">Create Account</button>
    </form>
    <p class="help">After registration, this shop will open automatically in the owner app.</p>
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

    if request.method == "GET" and path == "/owner-register":
        return _registration_page()

    if request.method == "POST" and path == "/owner/session-register":
        body = (await request.body()).decode("utf-8", errors="replace")
        raw_fields = parse_qs(body, keep_blank_values=True)
        values = {
            name: (raw_fields.get(name, [""])[0] or "").strip()
            for name in (
                "business_name",
                "owner_name",
                "phone",
                "address",
                "gstin",
                "username",
            )
        }
        password = raw_fields.get("password", [""])[0]
        confirm_password = raw_fields.get("confirm_password", [""])[0]

        if password != confirm_password:
            return _registration_page("Both PIN / Password entries must match.", values, 400)

        try:
            from backend.saas_ext import BusinessSignupIn, register_business

            signup = register_business(BusinessSignupIn(**values, password=password))
        except ValidationError:
            return _registration_page(
                "Please complete all required fields correctly.", values, 400
            )
        except HTTPException as exc:
            if exc.status_code == 409:
                message = "This username is already in use. Choose another username."
            elif exc.status_code == 400:
                message = "Enter a valid 10-digit mobile number."
            else:
                message = str(exc.detail or "Registration could not be completed.")
            return _registration_page(message, values, exc.status_code)

        response = RedirectResponse(
            url=f"/?handoff={quote(str(signup['token']))}&v={FRONTEND_VERSION}",
            status_code=303,
            headers={"Cache-Control": "no-store"},
        )
        _set_session_cookie(response, str(signup["token"]))
        return response

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
