from __future__ import annotations

import base64
import hashlib
import html
import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.app import app, db, now_iso, verify_password

CLIENT_ID = os.getenv("ALEXA_OAUTH_CLIENT_ID", "kirana-software-alexa")
CLIENT_SECRET = os.getenv("ALEXA_OAUTH_CLIENT_SECRET", "")
AUTH_CODE_MINUTES = 5
SESSION_DAYS = 30
REFRESH_DAYS = 180
ACCESS_TOKEN_SECONDS = SESSION_DAYS * 24 * 60 * 60


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _valid_redirect_uri(uri: str) -> bool:
    try:
        parsed = urlparse(uri)
    except Exception:
        return False
    if parsed.scheme != "https":
        return False
    return (parsed.hostname or "").lower() in {"layla.amazon.com", "pitangui.amazon.com", "alexa.amazon.co.jp"} and parsed.path.startswith("/api/skill/link/")


def _ensure_schema() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alexa_oauth_codes (
                code_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                redirect_uri TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alexa_oauth_refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def _login_page(*, client_id: str, redirect_uri: str, state: str, scope: str, error: str = "", username: str = "") -> HTMLResponse:
    error_box = f'<div class="err">{html.escape(error)}</div>' if error else ""
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Link Kirana Software</title><style>
body{{margin:0;background:#eef7fd;color:#263545;font-family:Arial,sans-serif;padding:24px}}
.card{{max-width:430px;margin:7vh auto;background:white;padding:28px;border-radius:20px;box-shadow:0 16px 45px #075b8c2b}}
h1{{color:#087fbf;margin:0 0 8px}}p{{color:#667684;line-height:1.45}}label{{display:block;margin:18px 0 7px;font-weight:800}}
input{{box-sizing:border-box;width:100%;padding:14px;border:1px solid #cbd9e2;border-radius:11px;font-size:16px}}
button{{width:100%;margin-top:22px;padding:15px;border:0;border-radius:11px;background:#087fbf;color:white;font-weight:900;font-size:16px}}
.err{{background:#fff0ef;color:#b42318;padding:12px;border-radius:10px;margin:14px 0}}.small{{font-size:12px;color:#7c8a95}}
</style></head><body><div class="card"><h1>Kirana Software</h1>
<p>Sign in with your shop owner account. Alexa will be linked only to this business.</p>{error_box}
<form method="post" action="/alexa/oauth/authorize">
<input type="hidden" name="client_id" value="{html.escape(client_id, quote=True)}"><input type="hidden" name="redirect_uri" value="{html.escape(redirect_uri, quote=True)}"><input type="hidden" name="state" value="{html.escape(state, quote=True)}"><input type="hidden" name="scope" value="{html.escape(scope, quote=True)}">
<label>Username</label><input name="username" autocomplete="username" value="{html.escape(username, quote=True)}" required>
<label>PIN / Password</label><input name="password" type="password" autocomplete="current-password" required>
<button type="submit">Link Alexa</button></form><p class="small">Your PIN/password stays with Kirana Software and is not shared with Amazon.</p>
</div></body></html>""",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/alexa/oauth/authorize")
def kirana_alexa_authorize_get(client_id: str, redirect_uri: str, state: str = "", scope: str = "alexa", response_type: str = "code"):
    if response_type != "code":
        raise HTTPException(status_code=400, detail="unsupported response_type")
    if client_id != CLIENT_ID:
        raise HTTPException(status_code=400, detail="invalid client_id")
    if not _valid_redirect_uri(redirect_uri):
        raise HTTPException(status_code=400, detail="invalid redirect_uri")
    return _login_page(client_id=client_id, redirect_uri=redirect_uri, state=state, scope=scope)


@app.post("/alexa/oauth/authorize")
async def kirana_alexa_authorize_post(request: Request):
    body = (await request.body()).decode("utf-8", errors="replace")
    form = parse_qs(body, keep_blank_values=True)
    value = lambda key, default="": (form.get(key, [default])[0] or default).strip()
    client_id = value("client_id")
    redirect_uri = value("redirect_uri")
    state = value("state")
    scope = value("scope", "alexa")
    username = value("username").lower()
    password = value("password")
    if client_id != CLIENT_ID or not _valid_redirect_uri(redirect_uri):
        raise HTTPException(status_code=400, detail="invalid OAuth request")

    with db() as conn:
        user = conn.execute("SELECT id,username,password_hash,business_id FROM users WHERE lower(username)=?", (username,)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        return _login_page(client_id=client_id, redirect_uri=redirect_uri, state=state, scope=scope, error="Incorrect username or PIN/password.", username=username)

    _ensure_schema()
    code = secrets.token_urlsafe(40)
    with db() as conn:
        conn.execute(
            "INSERT INTO alexa_oauth_codes(code_hash,user_id,redirect_uri,expires_at,created_at) VALUES(?,?,?,?,?)",
            (_hash(code), int(user["id"]), redirect_uri, _iso(datetime.now() + timedelta(minutes=AUTH_CODE_MINUTES)), now_iso()),
        )
    params = {"code": code}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(redirect_uri + sep + urlencode(params), status_code=303)


def _client_credentials(request: Request, form: dict[str, list[str]]) -> tuple[str, str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        try:
            raw = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
            first, second = raw.split(":", 1)
            return first, second
        except Exception:
            return "", ""
    return (form.get("client_id", [""])[0], form.get("client_secret", [""])[0])


def _verify_client(client_id: str, secret: str) -> None:
    if not CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="OAuth client secret is not configured on server")
    if not secrets.compare_digest(client_id, CLIENT_ID) or not secrets.compare_digest(secret, CLIENT_SECRET):
        raise HTTPException(status_code=401, detail="invalid_client")


def _issue_tokens(user_id: int) -> dict:
    access_token = secrets.token_urlsafe(40)
    refresh_token = secrets.token_urlsafe(48)
    session_expires = _iso(datetime.now() + timedelta(days=SESSION_DAYS))
    refresh_expires = _iso(datetime.now() + timedelta(days=REFRESH_DAYS))
    with db() as conn:
        user = conn.execute("SELECT id,business_id FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="invalid user")
        conn.execute("DELETE FROM sessions WHERE expires_at<=?", (now_iso(),))
        conn.execute("INSERT INTO sessions(token,user_id,expires_at,created_at) VALUES(?,?,?,?)", (access_token, user_id, session_expires, now_iso()))
        conn.execute("INSERT INTO alexa_oauth_refresh_tokens(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)", (_hash(refresh_token), user_id, refresh_expires, now_iso()))
    return {"access_token": access_token, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_SECONDS, "refresh_token": refresh_token, "scope": "alexa"}


@app.post("/alexa/oauth/token")
async def kirana_alexa_token(request: Request):
    _ensure_schema()
    body = (await request.body()).decode("utf-8", errors="replace")
    form = parse_qs(body, keep_blank_values=True)
    client_id, secret = _client_credentials(request, form)
    _verify_client(client_id, secret)
    grant_type = (form.get("grant_type", [""])[0] or "").strip()

    if grant_type == "authorization_code":
        code = (form.get("code", [""])[0] or "").strip()
        redirect_uri = (form.get("redirect_uri", [""])[0] or "").strip()
        with db() as conn:
            row = conn.execute("SELECT * FROM alexa_oauth_codes WHERE code_hash=?", (_hash(code),)).fetchone()
            if not row or row["used_at"] or row["expires_at"] <= now_iso() or row["redirect_uri"] != redirect_uri:
                raise HTTPException(status_code=400, detail="invalid_grant")
            conn.execute("UPDATE alexa_oauth_codes SET used_at=? WHERE code_hash=?", (now_iso(), _hash(code)))
            user_id = int(row["user_id"])
        return JSONResponse(_issue_tokens(user_id), headers={"Cache-Control": "no-store"})

    if grant_type == "refresh_token":
        old_token = (form.get("refresh_token", [""])[0] or "").strip()
        with db() as conn:
            row = conn.execute("SELECT * FROM alexa_oauth_refresh_tokens WHERE token_hash=?", (_hash(old_token),)).fetchone()
            if not row or row["revoked_at"] or row["expires_at"] <= now_iso():
                raise HTTPException(status_code=400, detail="invalid_grant")
            conn.execute("UPDATE alexa_oauth_refresh_tokens SET revoked_at=? WHERE token_hash=?", (now_iso(), _hash(old_token)))
            user_id = int(row["user_id"])
        return JSONResponse(_issue_tokens(user_id), headers={"Cache-Control": "no-store"})

    raise HTTPException(status_code=400, detail="unsupported_grant_type")


@app.get("/alexa/oauth/health")
def kirana_alexa_oauth_health():
    return {"status": "ok", "client_id": CLIENT_ID, "client_secret_configured": bool(CLIENT_SECRET)}
