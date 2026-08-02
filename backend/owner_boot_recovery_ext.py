from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app
import backend.stable_owner_app_ext as stable_owner


OWNER_BOOT_VERSION = "113"
OWNER_JS = STATIC_DIR / "owner-stable.js"


BOOT_WATCHDOG = r"""
<script id="kirana-owner-boot-watchdog">
(function () {
  'use strict';

  var retryInjected = false;
  var finished = false;

  function loadingState() {
    var loading = document.getElementById('app-loading');
    var app = document.getElementById('app');
    return {
      loading: loading,
      app: app,
      waiting: Boolean(
        loading && app &&
        !loading.classList.contains('hidden') &&
        app.classList.contains('hidden')
      )
    };
  }

  function showRecovery(message) {
    if (finished) return;
    var current = loadingState();
    if (!current.loading || !current.waiting) return;
    if (document.getElementById('retry-boot')) return;
    finished = true;
    current.loading.innerHTML =
      '<div class="loading-logo">K</div>' +
      '<strong>App could not finish loading</strong>' +
      '<span>' + String(message || 'Please retry the connection.') + '</span>' +
      '<div style="display:grid;gap:12px;width:min(300px,82vw);margin-top:8px">' +
        '<button id="retry-boot" class="primary-small" type="button">Retry App</button>' +
        '<button id="owner-login-again" class="primary-small" type="button" style="background:#ffffff;color:#087fbf;border:2px solid #087fbf">Login Again</button>' +
      '</div>';
    document.getElementById('retry-boot').onclick = function () {
      location.replace('/?mobile=1&recovery=' + Date.now());
    };
    document.getElementById('owner-login-again').onclick = function () {
      location.replace('/owner-login?recovery=' + Date.now());
    };
  }

  function checkStartup() {
    var current = loadingState();
    if (!current.waiting || window.__kiranaOwnerBootReady) {
      finished = true;
      return;
    }

    // If the main bundle did not execute at all, load one fresh cache-busted copy.
    if (!window.__kiranaOwnerBundleLoaded && !retryInjected) {
      retryInjected = true;
      var script = document.createElement('script');
      script.src = '/owner-stable.js?v=113&recovery=' + Date.now();
      script.async = false;
      script.onerror = function () {
        showRecovery('The app file could not be downloaded. Check the internet connection and retry.');
      };
      document.body.appendChild(script);
      window.setTimeout(checkStartup, 9000);
      return;
    }

    showRecovery('The server is taking too long to respond. Retry the app or sign in again.');
  }

  window.addEventListener('error', function (event) {
    var source = String(event && event.filename || '');
    if (source.indexOf('owner-stable.js') >= 0) {
      window.setTimeout(function () {
        showRecovery('The app file could not start correctly. Retry with a fresh copy.');
      }, 250);
    }
  });

  window.setTimeout(checkStartup, 9000);
})();
</script>
"""


FETCH_HELPER = r"""
  async function fetchWithTimeout(path, options) {
    var config = options || {};
    var method = String(config.method || 'GET').toUpperCase();
    var attempts = method === 'GET' ? 2 : 1;
    var lastError = null;

    for (var attempt = 0; attempt < attempts; attempt += 1) {
      var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var timer = window.setTimeout(function () {
        if (controller) controller.abort();
      }, 7000);
      try {
        var requestOptions = Object.assign({}, config);
        if (controller) requestOptions.signal = controller.signal;
        var response = await fetch(path, requestOptions);
        window.clearTimeout(timer);
        return response;
      } catch (error) {
        window.clearTimeout(timer);
        lastError = error;
        if (attempt + 1 < attempts) {
          await new Promise(function (resolve) { window.setTimeout(resolve, 350); });
        }
      }
    }

    var message = lastError && lastError.name === 'AbortError'
      ? 'Server response timed out. Please retry.'
      : 'Could not connect to the server. Please retry.';
    throw new Error(message);
  }

"""


def patched_owner_script() -> str:
    script = OWNER_JS.read_text(encoding="utf-8")
    if "window.__kiranaOwnerBundleLoaded = true;" not in script:
        script = script.replace(
            "  'use strict';",
            "  'use strict';\n\n  window.__kiranaOwnerBundleLoaded = true;",
            1,
        )
    if "async function fetchWithTimeout" not in script:
        script = script.replace("  async function api(path, options) {", FETCH_HELPER + "  async function api(path, options) {", 1)
    script = script.replace(
        "var response = await fetch(path, Object.assign({}, config, {",
        "var response = await fetchWithTimeout(path, Object.assign({}, config, {",
        1,
    )
    if "window.__kiranaOwnerBootReady = true;" not in script:
        script = script.replace(
            "      one('#app-loading').classList.add('hidden');",
            "      one('#app-loading').classList.add('hidden');\n      window.__kiranaOwnerBootReady = true;",
            1,
        )
    return script


_original_owner_page = stable_owner.stable_owner_page


def stable_owner_page_with_boot_recovery(token: str) -> HTMLResponse:
    original = _original_owner_page(token)
    html = original.body.decode("utf-8")
    html = html.replace("/owner-stable.js?v=105", f"/owner-stable.js?v={OWNER_BOOT_VERSION}")
    html = html.replace("/owner-stable.js?v=106", f"/owner-stable.js?v={OWNER_BOOT_VERSION}")
    html = html.replace("/owner-stable.js?v=112", f"/owner-stable.js?v={OWNER_BOOT_VERSION}")
    if "kirana-owner-boot-watchdog" not in html:
        marker = f'<script src="/owner-stable.js?v={OWNER_BOOT_VERSION}"></script>'
        if marker in html:
            html = html.replace(marker, BOOT_WATCHDOG + marker, 1)
        else:
            html = html.replace("</body>", BOOT_WATCHDOG + "</body>", 1)

    headers = {
        key: value
        for key, value in original.headers.items()
        if key.lower() not in {"content-length", "content-type", "set-cookie"}
    }
    headers["X-Kirana-Boot-Recovery"] = OWNER_BOOT_VERSION
    response = HTMLResponse(html, status_code=original.status_code, headers=headers)
    cookie = original.headers.get("set-cookie")
    if cookie:
        response.headers.append("set-cookie", cookie)
    return response


stable_owner.stable_owner_page = stable_owner_page_with_boot_recovery


@app.middleware("http")
async def serve_recoverable_owner_bundle(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path == "/owner-stable.js":
        return Response(
            patched_owner_script(),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Kirana-Owner-Bundle": OWNER_BOOT_VERSION,
            },
        )
    return await call_next(request)
