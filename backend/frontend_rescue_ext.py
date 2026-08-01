from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.app import STATIC_DIR, app, db
from backend.customer_link_fix_ext import default_customer_business
from backend.customer_self_register_ext import customer_registration_html
from backend.saas_ext import ensure_saas_schema
from backend.ui_shell_v2_ext import BATCH_REMOVE_CARD, DUPLICATE_CARD


FRONTEND_VERSION = "068"


HTML_ENGLISH_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Billing, Stock aur Khata — Sab Ek Jagah", "Billing, Inventory & Accounts — All in One"),
    ("Apni dukaan shuru karein", "Set Up Your Business"),
    ("Dukaan ka naam", "Business Name"),
    ("Apni Dukaan Ka Account Banayein", "Create Your Business Account"),
    ("30 din free trial · Alag customer order link · Koi card nahi", "30-day free trial · Separate customer ordering link · No card required"),
    ("Parties & Khata", "Parties & Accounts"),
    ("PARTY KHATA", "PARTY ACCOUNT"),
    ("Customer receivable aur supplier payable", "Customer receivables and supplier payables"),
    ("CSV ya Excel upload karke preview aur import karein", "Upload a CSV or Excel file to preview and import"),
    ("Vyapar export file choose karein", "Choose a Vyapar export file"),
    ("Product master pehle upload karein.", "Upload the product master first."),
    ("Customers aur suppliers import karein.", "Import customers and suppliers."),
    ("Invoice line reports upload karein.", "Upload invoice line reports."),
    ("Stock aur outstanding compare karein.", "Compare stock and outstanding balances."),
    ("Sale minus purchase total. Exact item-wise cost history se calculation aur accurate hogi.", "Sales minus purchases. Accuracy improves with item-level cost history."),
    ("Data ko phone/laptop par safe rakhein", "Keep your data safely on your phone or laptop"),
    ("Automatic duplicate check optional hai. Direct import remove karne ke liye neeche Sales Import Batches use karein.", "Automatic duplicate checking is optional. Use Sales Import Batches below to remove an imported batch directly."),
    ("Galat item-wise SaleReport ko direct remove karein. Sirf selected import batch delete hoga.", "Remove an incorrect item-wise SaleReport import directly. Only the selected import batch will be deleted."),
    ("Sales import batches load ho rahe hain…", "Loading sales import batches..."),
    ("Dukaan ka customer link galat hai", "The customer link is invalid"),
    ("Database wala mobile number", "Registered mobile number"),
    ("WhatsApp OTP Request Karein", "Request WhatsApp OTP"),
    ("Request dukaan ko jayegi. Dukaan WhatsApp par OTP bhejegi.", "The request will go to the business. The business will send the OTP on WhatsApp."),
    ("Product search karein", "Search products"),
    ("Cart me Add", "Add to Cart"),
    ("Order Request", "Request Order"),
    ("Current Rate", "Your Rate"),
)


def apply_english_ui(html: str) -> str:
    for old, new in HTML_ENGLISH_REPLACEMENTS:
        html = html.replace(old, new)
    return html


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
    note.textContent = message || 'The app retried loading. Please sign in.';
  };

  window.addEventListener('error', event => {
    if (String(event?.filename || '').includes('owner-core.js')) {
      forceLoginVisible('The app script did not load. Reload the page.');
    }
  });
  window.addEventListener('unhandledrejection', () => {
    setTimeout(() => forceLoginVisible('The app had a startup error. The login screen was restored.'), 100);
  });
  setTimeout(() => forceLoginVisible('The app did not load. The login screen was restored.'), 4000);
})();
</script>
"""


def fixed_owner_core() -> str:
    core = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    # Keep this explicit repair until the base bundle is regenerated. The
    # original compressed line relied on automatic semicolon insertion and
    # was unreliable in some Android browser builds.
    broken = "if(metaEl)metaEl.textContent=`${line.size?`${line.size} · `:''}${line.unit||'pcs'} · GST ${line.gst_rate}%`}updateCartTotals(k)}"
    repaired = "if(metaEl){metaEl.textContent=`${line.size?`${line.size} · `:''}${line.unit||'pcs'} · GST ${line.gst_rate}%`;}updateCartTotals(k)}"
    return core.replace(broken, repaired, 1)


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

    # Never ship a page where both the auth screen and app shell start hidden.
    # Login is visible immediately; the core script switches to setup/dashboard.
    html = html.replace(
        '<section id="auth-screen" class="auth-screen hidden">',
        '<section id="auth-screen" class="auth-screen">',
        1,
    )
    html = html.replace(
        '<div id="login-box" class="hidden">',
        '<div id="login-box">',
        1,
    )
    html = html.replace(
        "/styles.css?v=040",
        f"/owner-core.css?v={FRONTEND_VERSION}",
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
    html = html.replace(
        '<script src="/app.js?v=040"></script>',
        f'<script src="/owner-login-rescue.js?v={FRONTEND_VERSION}"></script>'
        + OWNER_BOOT_GUARD
        + f'<script src="/owner-core.js?v={FRONTEND_VERSION}"></script>',
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
        '<script src="/saas-onboarding.js?v=062"></script>'
        f'<script src="/english-ui.js?v={FRONTEND_VERSION}"></script></body>',
        1,
    )
    return apply_english_ui(html)


def customer_html() -> str:
    html = customer_registration_html()
    html = html.replace("/customer-order.js?v=060", f"/customer-order.js?v={FRONTEND_VERSION}")
    html = html.replace("/customer-order.css?v=060", f"/customer-order.css?v={FRONTEND_VERSION}")
    html = html.replace(
        "</body>",
        f'<script src="/english-ui.js?v={FRONTEND_VERSION}"></script></body>',
        1,
    )
    return apply_english_ui(html)


def static_javascript(filename: str) -> Response:
    return Response(
        content=(STATIC_DIR / filename).read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers=no_cache_headers(),
    )


@app.get("/owner-core.js", include_in_schema=False)
def raw_owner_core_javascript() -> Response:
    return Response(
        content=fixed_owner_core(),
        media_type="application/javascript",
        headers=no_cache_headers(),
    )


@app.get("/owner-core.css", include_in_schema=False)
def raw_owner_core_stylesheet() -> Response:
    return Response(
        content=(STATIC_DIR / "styles.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers=no_cache_headers(),
    )


@app.get("/owner-login-rescue.js", include_in_schema=False)
def owner_login_rescue_javascript() -> Response:
    return static_javascript("owner-login-rescue.js")


@app.get("/english-ui.js", include_in_schema=False)
def english_ui_javascript() -> Response:
    return static_javascript("english-ui.js")


@app.middleware("http")
async def stable_frontend_routes(request: Request, call_next):
    if request.method != "GET":
        return await call_next(request)

    path = request.url.path.rstrip("/") or "/"
    if path == "/owner-core.js":
        return Response(
            content=fixed_owner_core(),
            media_type="application/javascript",
            headers=no_cache_headers(),
        )
    if path == "/owner-core.css":
        return Response(
            content=(STATIC_DIR / "styles.css").read_text(encoding="utf-8"),
            media_type="text/css",
            headers=no_cache_headers(),
        )
    if path == "/owner-login-rescue.js":
        return static_javascript("owner-login-rescue.js")
    if path == "/english-ui.js":
        return static_javascript("english-ui.js")
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


# Keep rescue assets ahead of backend.app's generic SPA fallback as a second
# line of defence; the outer middleware serves them directly in production.
_owner_asset_routes = [
    route for route in list(app.router.routes)
    if getattr(route, "path", None) in {
        "/owner-core.js",
        "/owner-core.css",
        "/owner-login-rescue.js",
        "/english-ui.js",
    }
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
