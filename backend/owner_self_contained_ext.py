from __future__ import annotations

import re
from pathlib import PurePosixPath

from fastapi import Request
from fastapi.responses import HTMLResponse

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.stable_owner_app_ext as stable_owner


SELF_CONTAINED_VERSION = "114"
_ASSEMBLED_OWNER_PAGE = stable_owner.stable_owner_page

_STYLESHEET_RE = re.compile(
    r'<link\s+rel=["\']stylesheet["\']\s+href=["\']/([^"\'?]+)(?:\?[^"\']*)?["\']\s*/?>',
    re.IGNORECASE,
)
_SCRIPT_RE = re.compile(
    r'<script\s+src=["\']/([^"\'?]+)(?:\?[^"\']*)?["\']\s*>\s*</script>',
    re.IGNORECASE,
)


def _safe_static_path(asset_name: str):
    clean = PurePosixPath(asset_name)
    if clean.is_absolute() or ".." in clean.parts or len(clean.parts) != 1:
        return None
    path = STATIC_DIR / clean.name
    if not path.is_file():
        return None
    return path


def _inline_owner_assets(html: str) -> str:
    def replace_css(match: re.Match[str]) -> str:
        path = _safe_static_path(match.group(1))
        if path is None:
            return match.group(0)
        css = path.read_text(encoding="utf-8")
        return f'<style data-kirana-inline="{path.name}">\n{css}\n</style>'

    def replace_js(match: re.Match[str]) -> str:
        path = _safe_static_path(match.group(1))
        if path is None:
            return match.group(0)
        script = path.read_text(encoding="utf-8").replace("</script", "<\\/script")
        return f'<script data-kirana-inline="{path.name}">\n{script}\n</script>'

    html = _STYLESHEET_RE.sub(replace_css, html)
    html = _SCRIPT_RE.sub(replace_js, html)
    html = html.replace(
        "</head>",
        (
            '<meta name="kirana-owner-build" content="114" />'
            '<script>'
            'window.__kiranaSelfContainedBuild="114";'
            'window.setTimeout(function(){'
            'var loading=document.getElementById("app-loading");'
            'var app=document.getElementById("app");'
            'if(loading&&app&&!loading.classList.contains("hidden")&&app.classList.contains("hidden")){' 
            'loading.innerHTML="<div class=\\"loading-logo\\">K</div><strong>App could not start</strong><span>Please retry the app or sign in again.</span><div style=\\"display:grid;gap:12px;width:min(300px,82vw);margin-top:10px\\"><button id=\\"inline-retry\\" class=\\"primary-small\\" type=\\"button\\">Retry App</button><button id=\\"inline-login\\" class=\\"primary-small\\" type=\\"button\\" style=\\"background:#fff;color:#087fbf;border:2px solid #087fbf\\">Login Again</button></div>";'
            'document.getElementById("inline-retry").onclick=function(){location.replace("/?mobile=1&inline=114&t="+Date.now())};'
            'document.getElementById("inline-login").onclick=function(){location.replace("/owner-login?inline=114&t="+Date.now())};'
            '}'
            '},12000);'
            '</script>'
            '</head>'
        ),
        1,
    )
    return html


def _copy_headers(original) -> dict[str, str]:
    return {
        key: value
        for key, value in original.headers.items()
        if key.lower() not in {"content-length", "content-type", "set-cookie", "content-encoding"}
    }


@app.middleware("http")
async def serve_self_contained_owner_page(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/":
        handoff = request.query_params.get("handoff")
        cookie = request.cookies.get(COOKIE_NAME)
        session = _session_row(handoff) or _session_row(cookie)
        if session:
            original = _ASSEMBLED_OWNER_PAGE(str(session["token"]))
            html = _inline_owner_assets(original.body.decode("utf-8"))
            headers = _copy_headers(original)
            headers.update(
                {
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                    "X-Kirana-Self-Contained": SELF_CONTAINED_VERSION,
                }
            )
            response = HTMLResponse(html, status_code=original.status_code, headers=headers)
            cookie_header = original.headers.get("set-cookie")
            if cookie_header:
                response.headers.append("set-cookie", cookie_header)
            return response

    return await call_next(request)
