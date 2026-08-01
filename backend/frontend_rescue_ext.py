from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.app import STATIC_DIR, app, db
from backend.customer_link_fix_ext import default_customer_business
from backend.customer_self_register_ext import customer_registration_html
from backend.saas_ext import ensure_saas_schema
from backend.ui_shell_v2_ext import BATCH_REMOVE_CARD, DUPLICATE_CARD


FRONTEND_VERSION = "066"


def no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


OWNER_BOOT_GUARD = r"""
<script>
(() => {
  try {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations().then(rows => rows.forEach(row => row.unregister())).catch(() => {});
    }
    if ('caches' in window) {
      caches.keys().then(keys => Promise.all(keys.map(key => caches.delete(key)))).catch(() => {});
    }
  } catch (_) {}

  const forceLoginVisible = message => {
    const auth = document.querySelector('#auth-screen');
    const shell = document.querySelector('#app-shell');
    const setup = document.querySelector('#setup-box');
    const login = document.querySelector('#login-box');
    if (!auth || !shell || !login) return;
    if (!auth.classList.contains('hidden') || !shell.classList.contains('hidden')) return;
    shell.classList.add('hidden');
    auth.classList.remove('hidden');
    setup?.classList.add('hidden');
    login.classList.remove('hidden');
    let note = document.querySelector('#owner-boot-note');
    if (!note) {
      note = document.createElement('div');
      note.id = 'owner-boot-note';
      note.style.cssText = 'margin:0 0 12px;padding:10px 12px;border-radius:10px;background:#fff4d6;color:#6d4b00;font-size:13px;font-weight:700;';
      login.prepend(note);
    }
    note.textContent = message || 'App loading retry hua. Login karein.';
  };

  window.addEventListener('error', event => {
    if (String(event?.filename || '').includes('owner-core.js')) {
      forceLoginVisible('App script load nahi hua. Page reload karein.');
    }
  });
  window.addEventListener('unhandledrejection', () => {
    setTimeout(() => forceLoginVisible('App startup mein dikkat aayi. Login screen restore ki gayi.'), 100);
  });
  setTimeout(() => forceLoginVisible('App load nahi hui, login screen restore kar di gayi.'), 4000);
})();
</script>
"""


def owner_html() -> str:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    history_card = '<article class="card"><div class="section-title"><h2>Import History</h2></div><div id="import-history" class="simple-list"></div></article>'
    cleanup_area = DUPLICATE_CARD + BATCH_REMOVE_CARD
    if history_card in html:
        html = html.replace(history_card, cleanup_area + history_card, 1)
    else:
        html = html.replace(
            '<div id="import-history" class="simple-list"></div>',
            cleanup_area + '<div id="import-history" class="simple-list"></div>',
            1,
        )
    html = html.replace(
        "/styles.css?v=040",
        f"/styles.css?v={FRONTEND_VERSION}",
        1,
    )
    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="/settings-v2.css?v=042" />'
        '<link rel="stylesheet" href="/order-center.css?v=060" />'
        '<link rel="stylesheet" href="/customer-otp-owner.css?v=062" />'
        '<link rel="stylesheet" href="/saas-onboarding.css?v=062" /></head>',
        1,
    )
    # Bypass backend.items_ext's wrapped /app.js response. The raw owner core
    # is served below with strict no-cache headers to avoid Android stale PWA assets.
    html = html.replace(
        '<script src="/app.js?v=040"></script>',
        OWNER_BOOT_GUARD + f'<script src="/owner-core.js?v={FRONTEND_VERSION}"></script>',
        1,
    )
    html = html.replace(
        "</body>",
        '<script src="/settings-v2.js?v=042"></script>'
        '<script src="/import-fix.js?v=044"></script>'
        '<script src="/activity-navigation.js?v=046"></script>'
        '<script src="/sale-item-picker.js?v=044"></script>'
        '<script src="/manual-sale-cleanup-v2.js?v=051"></script>'
        '<script src="/payment-link-v2.js?v=050"></script>'
        '<script src="/import-batch-remove.js?v=051"></script>'
        '<script src="/password-change.js?v=052"></script>'
        '<script src="/order-center.js?v=060"></script>'
        '<script src="/customer-link-fix.js?v=063"></script>'
        '<script src="/customer-otp-owner.js?v=062"></script>'
        '<script src="/saas-onboarding.js?v=062"></script></body>',
        1,
    )
    return html


def customer_html() -> str:
    html = customer_registration_html()
    html = html.replace("/customer-order.js?v=060", f"/customer-order.js?v={FRONTEND_VERSION}")
    html = html.replace("/customer-order.css?v=060", f"/customer-order.css?v={FRONTEND_VERSION}")
    return html


@app.get("/owner-core.js", include_in_schema=False)
def raw_owner_core_javascript() -> Response:
    return Response(
        content=(STATIC_DIR / "app.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers=no_cache_headers(),
    )


@app.middleware("http")
async def stable_frontend_routes(request: Request, call_next):
    if request.method != "GET":
        return await call_next(request)

    path = request.url.path.rstrip("/") or "/"
    if path == "/":
        return HTMLResponse(owner_html(), headers=no_cache_headers())

    if path == "/customer":
        if not request.query_params.get("shop"):
            ensure_saas_schema()
            with db() as conn:
                row = default_customer_business(conn)
            if row:
                target = request.url.include_query_params(shop=row["slug"])
                return RedirectResponse(url=str(target), status_code=307, headers=no_cache_headers())
        return HTMLResponse(customer_html(), headers=no_cache_headers())

    return await call_next(request)


# Ensure the raw core asset route is evaluated before backend.app's SPA fallback.
_owner_asset_routes = [
    route for route in list(app.router.routes)
    if getattr(route, "path", None) == "/owner-core.js"
]
for route in _owner_asset_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (
        index for index, route in enumerate(app.router.routes)
        if getattr(route, "path", None) == "/{path:path}"
    ),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _owner_asset_routes
