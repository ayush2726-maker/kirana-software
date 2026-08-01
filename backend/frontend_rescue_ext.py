from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.app import STATIC_DIR, app, db
from backend.customer_link_fix_ext import default_customer_business
from backend.customer_self_register_ext import customer_registration_html
from backend.saas_ext import ensure_saas_schema
from backend.ui_shell_v2_ext import BATCH_REMOVE_CARD, DUPLICATE_CARD


def no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


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
        "</head>",
        '<link rel="stylesheet" href="/settings-v2.css?v=042" />'
        '<link rel="stylesheet" href="/order-center.css?v=060" />'
        '<link rel="stylesheet" href="/customer-otp-owner.css?v=062" />'
        '<link rel="stylesheet" href="/saas-onboarding.css?v=062" /></head>',
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
    html = html.replace("/customer-order.js?v=060", "/customer-order.js?v=063")
    html = html.replace("/customer-order.css?v=060", "/customer-order.css?v=063")
    return html


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
