from __future__ import annotations

import hashlib
import hmac
from datetime import datetime

from fastapi import HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.app import app, db, hash_password, now_iso


RECOVERY_CODE_HASH = "65627589679c2361740dbe75a96c3e6285fde97edebc4f2c4f3e04940421b00f"
RECOVERY_EXPIRES_AT = "2026-08-03T00:00:00"


class OwnerRecoveryIn(BaseModel):
    code: str = Field(min_length=10, max_length=120)
    username: str = Field(default="admin", min_length=1, max_length=120)
    new_password: str = Field(min_length=4, max_length=128)


def ensure_owner_recovery_schema() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS owner_recovery_uses (
                code_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                used_at TEXT NOT NULL
            )
            """
        )


def code_hash(code: str) -> str:
    return hashlib.sha256(str(code or "").encode("utf-8")).hexdigest()


def recovery_available(code: str) -> bool:
    supplied = code_hash(code)
    if not hmac.compare_digest(supplied, RECOVERY_CODE_HASH):
        return False
    if datetime.now() >= datetime.fromisoformat(RECOVERY_EXPIRES_AT):
        return False
    ensure_owner_recovery_schema()
    with db() as conn:
        used = conn.execute(
            "SELECT 1 FROM owner_recovery_uses WHERE code_hash=?",
            (RECOVERY_CODE_HASH,),
        ).fetchone()
    return not bool(used)


@app.on_event("startup")
def owner_recovery_startup() -> None:
    ensure_owner_recovery_schema()


@app.get("/owner-recovery", include_in_schema=False)
def owner_recovery_page(code: str = Query(default="")) -> HTMLResponse:
    valid = recovery_available(code)
    if not valid:
        return HTMLResponse(
            """<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
            <style>body{font-family:Arial;background:#eef7fd;padding:28px;color:#243242}.box{max-width:430px;margin:70px auto;background:#fff;padding:28px;border-radius:20px;box-shadow:0 12px 36px #0b7bc122}h2{margin-top:0;color:#b42318}</style></head>
            <body><div class='box'><h2>The reset link is invalid or has already been used</h2><p>A new recovery link is required.</p></div></body></html>""",
            status_code=403,
            headers={"Cache-Control": "no-store"},
        )

    safe_code = code.replace("\\", "\\\\").replace("'", "\\'")
    html = f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Owner PIN Reset</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,sans-serif;background:linear-gradient(180deg,#087fbf 0 34%,#eef7fd 34%);min-height:100vh;padding:24px;color:#243242}}
.card{{max-width:460px;margin:105px auto 30px;background:#fff;border-radius:24px;padding:28px;box-shadow:0 18px 50px #073b5d35}}
h1{{margin:0 0 8px;font-size:30px}}p{{color:#667684;line-height:1.5}}label{{display:block;font-weight:700;margin-top:18px}}input{{width:100%;margin-top:8px;padding:15px;border:2px solid #d6e1e8;border-radius:14px;font-size:18px}}button{{width:100%;margin-top:22px;padding:16px;border:0;border-radius:14px;background:#0b82c2;color:#fff;font-size:18px;font-weight:800}}#msg{{margin-top:16px;padding:12px;border-radius:12px;display:none}}.ok{{display:block!important;background:#e7f8ee;color:#157347}}.err{{display:block!important;background:#ffe9e7;color:#b42318}}
</style></head>
<body><main class='card'><h1>Owner PIN Reset</h1><p>Set a new PIN for the admin account. This secure link works only once.</p>
<form id='reset-form'><label>Username<input name='username' value='admin' required></label><label>New PIN / Password<input name='new_password' type='password' minlength='4' required autocomplete='new-password' inputmode='numeric'></label><label>Confirm PIN<input name='confirm_password' type='password' minlength='4' required autocomplete='new-password' inputmode='numeric'></label><button type='submit'>Save New PIN</button></form><div id='msg'></div></main>
<script>
const code='{safe_code}';
document.querySelector('#reset-form').addEventListener('submit',async e=>{{e.preventDefault();const f=new FormData(e.target),p=f.get('new_password'),c=f.get('confirm_password'),msg=document.querySelector('#msg');if(p!==c){{msg.className='err';msg.textContent='Both PIN entries must match.';return}}try{{const r=await fetch('/api/owner-recovery/reset',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{code,username:f.get('username'),new_password:p}})}});const d=await r.json().catch(()=>({{}}));if(!r.ok)throw new Error(d.detail||'Reset failed');msg.className='ok';msg.textContent='PIN reset successfully. Opening the owner login page...';setTimeout(()=>location.href='/?recovered=1&v=068',1200)}}catch(err){{msg.className='err';msg.textContent=err.message}}}});
</script></body></html>"""
    return HTMLResponse(html, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.post("/api/owner-recovery/reset")
def owner_recovery_reset(payload: OwnerRecoveryIn) -> dict[str, bool]:
    if not recovery_available(payload.code):
        raise HTTPException(status_code=403, detail="The recovery link is invalid, expired, or already used")

    username = payload.username.strip().lower()
    with db() as conn:
        row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Owner username was not found")
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(payload.new_password), row["id"]),
        )
        conn.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
        conn.execute(
            "INSERT INTO owner_recovery_uses(code_hash,username,used_at) VALUES(?,?,?)",
            (RECOVERY_CODE_HASH, username, now_iso()),
        )
    return {"ok": True}


# Keep recovery routes before the SPA catch-all.
_recovery_paths = {"/owner-recovery", "/api/owner-recovery/reset"}
_recovery_routes = [route for route in list(app.router.routes) if getattr(route, "path", None) in _recovery_paths]
for route in _recovery_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (i for i, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _recovery_routes
