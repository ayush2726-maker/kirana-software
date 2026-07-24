from __future__ import annotations

from fastapi.responses import HTMLResponse

from backend.app import STATIC_DIR, app


DUPLICATE_CARD = """
<article id="duplicate-sale-cleanup-card" class="card">
  <div class="duplicate-cleanup-status">
    <h2>Duplicate Sale Bills Cleanup</h2>
    <p>Automatic duplicate check optional hai. Direct import remove karne ke liye neeche Sales Import Batches use karein.</p>
  </div>
  <button data-manual-cleanup-sales-v2 class="btn secondary" type="button">Automatic Duplicate Check</button>
</article>
"""


BATCH_REMOVE_CARD = """
<article id="sales-import-batches-card" class="card">
  <h2>Sales Import Batches</h2>
  <p>Galat item-wise SaleReport ko direct remove karein. Sirf selected import batch delete hoga.</p>
  <div id="removable-sales-batches" class="removable-batch-list">
    <div class="removable-batch-message">Sales import batches load ho rahe hain…</div>
  </div>
</article>
"""


@app.middleware("http")
async def serve_ui_shell_v2(request, call_next):
    if request.method == "GET" and request.url.path == "/":
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
            '<link rel="stylesheet" href="/settings-v2.css?v=042" /></head>',
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
            '<script src="/password-change.js?v=052"></script></body>',
        )
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return await call_next(request)
