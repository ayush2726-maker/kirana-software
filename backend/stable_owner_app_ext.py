from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from backend.app import STATIC_DIR, app
from backend.owner_session_ext import COOKIE_NAME, _session_row, _set_session_cookie


OWNER_HTML = STATIC_DIR / "owner-stable.html"
OWNER_CSS = STATIC_DIR / "owner-stable.css"
OWNER_JS = STATIC_DIR / "owner-stable.js"
TXN_CSS = STATIC_DIR / "owner-transactions.css"
TXN_JS = STATIC_DIR / "owner-transactions.js"
BULK_CSS = STATIC_DIR / "owner-bulk-items.css"
BULK_JS = STATIC_DIR / "owner-bulk-items.js"
BACK_JS = STATIC_DIR / "owner-back-navigation.js"
VERSION = "103"

CACHE_CLEANUP = r"""
<script id="kirana-cache-cleanup">
(function () {
  try {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations().then(function (rows) {
        rows.forEach(function (row) { row.unregister(); });
      }).catch(function () {});
    }
    if ('caches' in window) {
      caches.keys().then(function (keys) {
        return Promise.all(keys.map(function (key) { return caches.delete(key); }));
      }).catch(function () {});
    }
  } catch (ignore) {}
})();
</script>
"""

KEYBOARD_TOTALS_HELPER = r"""
  function updateSaleTotalsWithoutRerender() {
    var totals = saleTotals();
    setText('#sale-subtotal', money(totals.subtotal));
    setText('#sale-tax', money(totals.tax));
    setText('#sale-total', money(totals.total));
    if (one('#sale-payment-mode').value !== 'credit' && number(one('#sale-paid').value) === 0 && totals.total > 0) {
      one('#sale-paid').value = totals.total.toFixed(2);
    }
  }

"""

OLD_LINE_INPUT_HANDLER = r"""    document.addEventListener('input', function (event) {
      var index = event.target.getAttribute('data-sale-index');
      var field = event.target.getAttribute('data-sale-field');
      if (index == null || !field || !state.saleLines[Number(index)]) return;
      state.saleLines[Number(index)][field] = Math.max(field === 'qty' ? 0.01 : 0, number(event.target.value));
      renderSaleLines();
    });"""

NEW_LINE_INPUT_HANDLER = r"""    document.addEventListener('input', function (event) {
      var index = event.target.getAttribute('data-sale-index');
      var field = event.target.getAttribute('data-sale-field');
      if (index == null || !field || !state.saleLines[Number(index)]) return;
      var line = state.saleLines[Number(index)];
      line[field] = Math.max(field === 'qty' ? 0.01 : 0, number(event.target.value));
      var card = event.target.closest('.sale-line');
      if (card) {
        var base = number(line.qty) * number(line.rate);
        var lineTotal = base + (base * number(line.gst_rate) / 100);
        var totalNode = card.querySelector('.sale-line-total strong');
        if (totalNode) totalNode.textContent = money(lineTotal);
      }
      updateSaleTotalsWithoutRerender();
    });"""


def no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


def patched_owner_js() -> str:
    script = OWNER_JS.read_text(encoding="utf-8")
    if "function updateSaleTotalsWithoutRerender()" not in script:
        script = script.replace("  function renderSaleLines() {", KEYBOARD_TOTALS_HELPER + "  function renderSaleLines() {", 1)
    script = script.replace(
        "    one('#sale-discount').addEventListener('input', renderSaleLines);",
        "    one('#sale-discount').addEventListener('input', updateSaleTotalsWithoutRerender);",
        1,
    )
    script = script.replace(OLD_LINE_INPUT_HANDLER, NEW_LINE_INPUT_HANDLER, 1)
    return script


def stable_owner_page(token: str) -> HTMLResponse:
    page = OWNER_HTML.read_text(encoding="utf-8")
    page = page.replace("__OWNER_VERSION__", VERSION)
    page = page.replace(
        "</head>",
        f'<link rel="stylesheet" href="/owner-transactions.css?v={VERSION}" />'
        f'<link rel="stylesheet" href="/owner-bulk-items.css?v={VERSION}" />'
        + CACHE_CLEANUP
        + "</head>",
        1,
    )
    page = page.replace(
        "</body>",
        f'<script src="/owner-transactions.js?v={VERSION}"></script>'
        f'<script src="/owner-bulk-items.js?v={VERSION}"></script>'
        f'<script src="/owner-back-navigation.js?v={VERSION}"></script>'
        "</body>",
        1,
    )
    response = HTMLResponse(
        page,
        headers={
            **no_cache_headers(),
            "Clear-Site-Data": '"cache"',
            "X-Kirana-Owner-UI": VERSION,
        },
    )
    _set_session_cookie(response, token)
    return response


@app.middleware("http")
async def serve_isolated_stable_owner_app(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"

    if request.method == "GET" and path == "/owner-stable.css":
        return Response(
            OWNER_CSS.read_text(encoding="utf-8"),
            media_type="text/css",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/owner-stable.js":
        return Response(
            patched_owner_js(),
            media_type="application/javascript",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/owner-transactions.css":
        return Response(
            TXN_CSS.read_text(encoding="utf-8"),
            media_type="text/css",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/owner-transactions.js":
        return Response(
            TXN_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/owner-bulk-items.css":
        return Response(
            BULK_CSS.read_text(encoding="utf-8"),
            media_type="text/css",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/owner-bulk-items.js":
        return Response(
            BULK_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/owner-back-navigation.js":
        return Response(
            BACK_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers=no_cache_headers(),
        )

    if request.method == "GET" and path == "/":
        handoff = request.query_params.get("handoff")
        cookie = request.cookies.get(COOKIE_NAME)
        session = _session_row(handoff) or _session_row(cookie)
        if session:
            return stable_owner_page(str(session["token"]))

    return await call_next(request)
