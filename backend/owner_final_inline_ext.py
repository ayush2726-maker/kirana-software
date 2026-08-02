from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import COOKIE_NAME, _session_row, _set_session_cookie
import backend.stable_owner_app_ext as stable_owner


BUILD = "118"

HTML_FILE = STATIC_DIR / "owner-stable.html"

CSS_FILES = [
    STATIC_DIR / "owner-stable.css",
    STATIC_DIR / "owner-transactions.css",
    STATIC_DIR / "owner-credit-payments.css",
    STATIC_DIR / "owner-bulk-items.css",
    STATIC_DIR / "owner-customer-catalog.css",
    STATIC_DIR / "owner-customer-share.css",
    STATIC_DIR / "owner-customer-otp.css",
]

JS_FILES = [
    STATIC_DIR / "owner-transactions.js",
    STATIC_DIR / "owner-credit-defaults.js",
    STATIC_DIR / "owner-linked-payments.js",
    STATIC_DIR / "owner-bulk-items.js",
    STATIC_DIR / "owner-bulk-errors.js",
    STATIC_DIR / "owner-back-navigation.js",
    STATIC_DIR / "owner-customer-catalog.js",
    STATIC_DIR / "owner-customer-share.js",
    STATIC_DIR / "owner-customer-otp.js",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _safe_script(script: str) -> str:
    # Do not let script-like text inside a JavaScript string terminate the
    # surrounding inline script element.
    return script.replace("</script", "<\\/script")


def _base_owner_script() -> str:
    script = stable_owner.patched_owner_js()

    # Make the shell interactive before waiting for APIs. The earlier page
    # stayed forever on the loading card whenever the external script or
    # /api/me request failed.
    old_boot = """  async function boot() {
    bindEvents();
    try {
      state.me = await api('/api/me');"""
    new_boot = """  async function boot() {
    try {
      bindEvents();
      var earlyApp = one('#app');
      var earlyLoading = one('#app-loading');
      if (earlyApp) earlyApp.classList.remove('hidden');
      if (earlyLoading) earlyLoading.classList.add('hidden');
      state.me = await api('/api/me');"""
    script = script.replace(old_boot, new_boot, 1)

    old_error = """    } catch (error) {
      one('#app-loading').innerHTML = '<div class=\"loading-logo\">K</div><strong>App could not start</strong><span>' + escapeHtml(error.message) + '</span><button id=\"retry-boot\" class=\"primary-small\">Retry</button>';
      one('#retry-boot').addEventListener('click', function () { window.location.reload(); });
    }
  }"""
    new_error = """    } catch (error) {
      console.error('Owner app boot failed', error);
      var failedApp = one('#app');
      var failedLoading = one('#app-loading');
      if (failedApp) failedApp.classList.remove('hidden');
      if (failedLoading) failedLoading.classList.add('hidden');
      toast(error && error.message ? error.message : 'Some business data could not load', true);
    }
  }"""
    script = script.replace(old_error, new_error, 1)

    return script


def final_owner_html() -> str:
    html = _read(HTML_FILE).replace("__OWNER_VERSION__", BUILD)

    # Remove every external local asset. Android WebView was visibly receiving
    # HTML/CSS but remained on the loading screen while the external owner JS
    # request never completed. All assets below are now delivered in this one
    # authenticated HTML response.
    html = html.replace(
        f'<link rel="stylesheet" href="/owner-stable.css?v={BUILD}" />',
        "",
        1,
    )
    html = html.replace(
        f'<script src="/owner-stable.js?v={BUILD}"></script>',
        "",
        1,
    )

    css_blocks = []
    for path in CSS_FILES:
        css = _read(path)
        if css:
            css_blocks.append(f'<style data-owner-inline="{path.name}">\n{css}\n</style>')

    startup_guard = """
<script id="owner-inline-startup-guard">
(function () {
  window.__kiranaOwnerBuild = '118';
  function reveal() {
    var app = document.getElementById('app');
    var loading = document.getElementById('app-loading');
    if (app) app.classList.remove('hidden');
    if (loading) loading.classList.add('hidden');
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', reveal, { once: true });
  } else {
    reveal();
  }
  setTimeout(reveal, 1200);
})();
</script>
"""

    html = html.replace(
        "</head>",
        "\n".join(css_blocks)
        + f'<meta name="kirana-owner-build" content="{BUILD}" />'
        + startup_guard
        + "</head>",
        1,
    )

    script_blocks = [
        '<script data-owner-inline="owner-stable.js">\n'
        + _safe_script(_base_owner_script())
        + "\n</script>"
    ]
    for path in JS_FILES:
        script = _read(path)
        if script:
            # Separate script elements are intentional. A syntax/runtime error
            # in one optional feature cannot prevent the base owner app from
            # booting and binding navigation.
            script_blocks.append(
                f'<script data-owner-inline="{path.name}">\n{_safe_script(script)}\n</script>'
            )

    html = html.replace("</body>", "\n".join(script_blocks) + "</body>", 1)
    return html


def _headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Kirana-Owner-Final": BUILD,
    }


@app.middleware("http")
async def serve_final_inline_owner(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/":
        handoff = request.query_params.get("handoff")
        cookie = request.cookies.get(COOKIE_NAME)
        session = _session_row(handoff) or _session_row(cookie)
        if session:
            response = HTMLResponse(final_owner_html(), headers=_headers())
            _set_session_cookie(response, str(session["token"]))
            return response
    return await call_next(request)
