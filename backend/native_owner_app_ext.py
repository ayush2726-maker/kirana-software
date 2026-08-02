from __future__ import annotations

import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import (
    COOKIE_NAME,
    _login_page,
    _session_row,
    _set_session_cookie,
)
import backend.stable_owner_app_ext as stable_owner


BUILD = "119"
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

OPTIONAL_JS_URLS = [
    f"/owner-transactions.js?v={BUILD}",
    f"/owner-credit-defaults.js?v={BUILD}",
    f"/owner-linked-payments.js?v={BUILD}",
    f"/owner-bulk-items.js?v={BUILD}",
    f"/owner-bulk-errors.js?v={BUILD}",
    f"/owner-back-navigation.js?v={BUILD}",
    f"/owner-customer-catalog.js?v={BUILD}",
    f"/owner-customer-share.js?v={BUILD}",
    f"/owner-customer-otp.js?v={BUILD}",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _safe_script(script: str) -> str:
    return script.replace("</script", "<\\/script")


def _core_script() -> str:
    script = stable_owner.patched_owner_js()

    # Bind the core navigation first and show the shell immediately. API calls
    # then hydrate data in the background. A slow /api/me must never leave the
    # Android owner app on a blank or loading-only screen.
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
      console.error('Native owner boot failed', error);
      var failedApp = one('#app');
      var failedLoading = one('#app-loading');
      if (failedApp) failedApp.classList.remove('hidden');
      if (failedLoading) failedLoading.classList.add('hidden');
      toast(error && error.message ? error.message : 'Some business data could not load', true);
    }
  }"""
    script = script.replace(old_error, new_error, 1)
    return script


def _optional_loader() -> str:
    urls = json.dumps(OPTIONAL_JS_URLS)
    return f"""
(function () {{
  'use strict';
  var urls = {urls};
  var index = 0;

  function loadNext() {{
    if (index >= urls.length) {{
      window.__kiranaNativeModulesReady = true;
      return;
    }}
    var url = urls[index++];
    var script = document.createElement('script');
    var finished = false;
    var timer = setTimeout(function () {{
      if (finished) return;
      finished = true;
      try {{ script.remove(); }} catch (ignore) {{}}
      console.warn('Optional owner module timed out', url);
      loadNext();
    }}, 5000);

    script.src = url;
    script.async = true;
    script.onload = script.onerror = function () {{
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      loadNext();
    }};
    document.body.appendChild(script);
  }}

  function begin() {{
    setTimeout(loadNext, 900);
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', begin, {{ once: true }});
  }} else {{
    begin();
  }}
}})();
"""


def native_owner_html() -> str:
    html = _read(HTML_FILE).replace("__OWNER_VERSION__", BUILD)
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

    css = "\n".join(_read(path) for path in CSS_FILES if path.is_file())
    first_paint = """
<style id="native-owner-first-paint">
  #app-loading{display:none!important}
  #app.app.hidden{display:block!important}
</style>
"""
    html = html.replace(
        "</head>",
        f"<style data-native-owner-css=\"{BUILD}\">{css}</style>"
        + first_paint
        + f'<meta name="kirana-native-owner-build" content="{BUILD}" />'
        + "</head>",
        1,
    )

    core = _safe_script(_core_script())
    optional = _safe_script(_optional_loader())
    html = html.replace(
        "</body>",
        f'<script data-native-core="{BUILD}">{core}</script>'
        f'<script data-native-optional-loader="{BUILD}">{optional}</script>'
        "</body>",
        1,
    )
    return html


def _headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Kirana-Native-Owner": BUILD,
    }


def _native_login_page() -> HTMLResponse:
    original = _login_page()
    html = original.body.decode("utf-8")
    html = html.replace(
        'action="/owner/session-login"',
        'action="/owner/session-login?native=1"',
        1,
    )
    return HTMLResponse(html, status_code=original.status_code, headers=_headers())


@app.middleware("http")
async def serve_native_owner_app(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/native-owner":
        handoff = request.query_params.get("handoff")
        cookie = request.cookies.get(COOKIE_NAME)
        session = _session_row(handoff) or _session_row(cookie)
        if not session:
            return _native_login_page()
        response = HTMLResponse(native_owner_html(), headers=_headers())
        _set_session_cookie(response, str(session["token"]))
        return response
    return await call_next(request)
