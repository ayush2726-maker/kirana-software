from __future__ import annotations

import re
from pathlib import PurePosixPath

from fastapi import Request
from fastapi.responses import HTMLResponse

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.owner_boot_recovery_ext as boot_recovery
import backend.stable_owner_app_ext as stable_owner


SELF_CONTAINED_VERSION = "115"
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


def _patched_owner_script() -> str:
    script = boot_recovery.patched_owner_script()

    # The old boot called bindEvents() outside try/catch. A single optional
    # missing control could therefore stop all JavaScript while leaving the
    # loading screen visible forever. Keep event binding inside the guarded
    # boot and reveal the shell before waiting for /api/me.
    script = script.replace(
        "  async function boot() {\n    bindEvents();\n    try {",
        "  async function boot() {\n    try {\n      bindEvents();\n      var earlyApp = one('#app');\n      var earlyLoading = one('#app-loading');\n      if (earlyApp) earlyApp.classList.remove('hidden');\n      if (earlyLoading) earlyLoading.classList.add('hidden');",
        1,
    )

    # Do not let a missing optional node make the error handler fail too.
    script = script.replace(
        "      one('#app-loading').innerHTML = '<div class=\"loading-logo\">K</div><strong>App could not start</strong><span>' + escapeHtml(error.message) + '</span><button id=\"retry-boot\" class=\"primary-small\">Retry</button>';\n      one('#retry-boot').addEventListener('click', function () { window.location.reload(); });",
        "      console.error('Owner boot failed', error);\n      var loadingNode = one('#app-loading');\n      var appNode = one('#app');\n      if (appNode) appNode.classList.remove('hidden');\n      if (loadingNode) loadingNode.classList.add('hidden');\n      toast(error && error.message ? error.message : 'Some data could not be loaded', true);",
        1,
    )
    return script


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
        if path.name == "owner-stable.js":
            script = _patched_owner_script()
        else:
            script = path.read_text(encoding="utf-8")
        script = script.replace("</script", "<\\/script")
        return f'<script data-kirana-inline="{path.name}">\n{script}\n</script>'

    # The owner shell must be usable even before JavaScript or API requests
    # finish. This permanently removes the infinite-loading failure mode.
    html = html.replace(
        '<div id="app-loading" class="app-loading">',
        '<div id="app-loading" class="app-loading hidden">',
        1,
    )
    html = html.replace(
        '<div id="app" class="app hidden">',
        '<div id="app" class="app">',
        1,
    )

    html = _STYLESHEET_RE.sub(replace_css, html)
    html = _SCRIPT_RE.sub(replace_js, html)
    html = html.replace(
        "</head>",
        (
            '<meta name="kirana-owner-build" content="115" />'
            '<script>'
            'window.__kiranaSelfContainedBuild="115";'
            'document.addEventListener("DOMContentLoaded",function(){'
            'var loading=document.getElementById("app-loading");'
            'var app=document.getElementById("app");'
            'if(app)app.classList.remove("hidden");'
            'if(loading)loading.classList.add("hidden");'
            '});'
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
